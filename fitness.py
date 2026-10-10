from datetime import date, datetime, timedelta
from json import JSONDecodeError
from pathlib import Path
import json
import math

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from forms import (
    BMIForm,
    BodyMetricForm,
    GOAL_UNITS,
    GoalForm,
    ProfileForm,
    ResetDataForm,
    StepLogForm,
    WaterLogForm,
    WaterResetForm,
    WaterTotalForm,
    WorkoutForm,
    set_activity_choices,
)
from models import BodyMetric, Goal, StepLog, WaterLog, Workout, db


fitness_bp = Blueprint("fitness", __name__)


DEFAULT_SPORTS = {
    "Running": {"calories_per_min": 10, "steps_per_min": 120},
    "Walking": {"calories_per_min": 5, "steps_per_min": 100},
    "Cycling": {"calories_per_min": 8, "steps_per_min": 0},
    "Swimming": {"calories_per_min": 11, "steps_per_min": 0},
    "Strength Training": {"calories_per_min": 7, "steps_per_min": 0},
    "Yoga": {"calories_per_min": 3, "steps_per_min": 0},
    "Football": {"calories_per_min": 9, "steps_per_min": 90},
    "Basketball": {"calories_per_min": 8, "steps_per_min": 80},
    "Dancing": {"calories_per_min": 6, "steps_per_min": 70},
}

FITNESS_TIPS = [
    "Start with five minutes of mobility before intense exercise.",
    "Drink water steadily through the day instead of catching up at night.",
    "A brisk 10-minute walk after meals can help build a reliable habit.",
    "Keep hard workouts hard and recovery days easy.",
    "Sleep is part of training. Aim for a consistent bedtime.",
    "Protein at each meal can support muscle recovery.",
    "Small weekly progress beats one perfect workout.",
]


def load_sports():
    sports_path = Path(current_app.root_path) / "sports.json"
    try:
        raw_text = sports_path.read_text(encoding="utf-8").strip()
        raw_sports = json.loads(raw_text) if raw_text else {}
    except (FileNotFoundError, JSONDecodeError, UnicodeDecodeError):
        raw_sports = {}

    normalized = {}
    if isinstance(raw_sports, dict):
        for activity, values in raw_sports.items():
            if not isinstance(values, dict) or not str(activity).strip():
                continue
            try:
                calories_per_min = float(values.get("calories_per_min", 0))
                steps_per_min = float(values.get("steps_per_min", 0))
            except (TypeError, ValueError):
                continue
            if not (
                math.isfinite(calories_per_min)
                and math.isfinite(steps_per_min)
                and calories_per_min > 0
                and steps_per_min >= 0
            ):
                continue
            normalized[str(activity).strip()] = {
                "calories_per_min": calories_per_min,
                "steps_per_min": steps_per_min,
            }

    return normalized or DEFAULT_SPORTS


def apply_sports_choices(form, sports):
    set_activity_choices(form, sports)


def commit_or_flash(success_message, error_message):
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception(error_message)
        flash(error_message, "error")
        return False
    flash(success_message, "success")
    return True


def latest_metric():
    return (
        BodyMetric.query.filter_by(user_id=current_user.id)
        .order_by(BodyMetric.recorded_on.desc(), BodyMetric.created_at.desc())
        .first()
    )


def safe_metric_weight(metric):
    if not metric:
        return None
    weight = metric.weight_kg
    if weight is None:
        return None
    try:
        weight = float(weight)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(weight) or weight <= 0:
        return None
    return weight


def bmi_category(bmi):
    if bmi is None:
        return ("Not calculated", "Enter height and weight to calculate BMI.")
    if bmi < 18.5:
        return ("Underweight", "Consider discussing healthy weight gain with a clinician.")
    if bmi < 25:
        return ("Healthy range", "Your BMI is in the commonly recommended range.")
    if bmi < 30:
        return ("Overweight", "Small changes to activity and food habits can help over time.")
    return ("Obesity range", "Consider a health professional's guidance for a safe plan.")


def calculate_bmi(height_cm, weight_kg):
    if height_cm is None or weight_kg is None:
        return None
    if not (math.isfinite(float(height_cm)) and math.isfinite(float(weight_kg))):
        return None
    if height_cm <= 0 or weight_kg <= 0:
        return None
    height_m = height_cm / 100
    return round(weight_kg / (height_m * height_m), 1)


def progress_percent(current, target):
    if target is None or target <= 0:
        return 0
    return min(100, max(0, round((current / target) * 100)))


def daily_tip():
    return FITNESS_TIPS[date.today().toordinal() % len(FITNESS_TIPS)]


def get_today_workouts(today):
    return Workout.query.filter_by(user_id=current_user.id, workout_date=today).all()


def get_today_water(today):
    return sum(
        log.water_ml
        for log in WaterLog.query.filter_by(user_id=current_user.id, recorded_on=today)
    )


def get_today_steps(today):
    step_log = StepLog.query.filter_by(
        user_id=current_user.id,
        recorded_on=today,
    ).first()
    return step_log.steps if step_log else 0


def build_weight_progress(metrics):
    ordered_metrics = [metric for metric in reversed(metrics) if safe_metric_weight(metric)]
    latest = ordered_metrics[-1] if ordered_metrics else None
    previous = ordered_metrics[-2] if len(ordered_metrics) > 1 else None
    first = ordered_metrics[0] if ordered_metrics else None
    latest_weight = safe_metric_weight(latest)
    previous_weight = safe_metric_weight(previous)
    goal_weight = current_user.weight_goal_kg

    goal_percent = 0
    if latest_weight is not None and goal_weight is not None and first:
        start_weight = safe_metric_weight(first)
        total_distance = abs(start_weight - goal_weight)
        if total_distance < 0.1:
            goal_percent = 100 if abs(latest_weight - goal_weight) < 0.1 else 0
        else:
            progress = total_distance - abs(latest_weight - goal_weight)
            goal_percent = min(100, max(0, round((progress / total_distance) * 100)))

    change = None
    if latest_weight is not None and previous_weight is not None:
        change = round(latest_weight - previous_weight, 1)

    return {
        "latest": latest_weight,
        "previous": previous_weight,
        "goal": goal_weight,
        "change": change,
        "goal_percent": goal_percent,
    }


def goal_label(goal_type):
    labels = {
        "water": "Water intake",
        "steps": "Steps",
        "weight": "Weight",
        "workout_minutes": "Workout minutes",
        "workout_sessions": "Workout sessions",
        "calories": "Calories burned",
    }
    return labels.get(goal_type, goal_type.replace("_", " ").title())


def goal_progress(goal, context):
    current = 0
    percent = 0
    status = ""

    if goal.goal_type == "weight":
        current = context.get("latest_weight")
        if current is None:
            status = "Log your weight to track this goal."
        else:
            start = goal.start_value if goal.start_value is not None else current
            total_distance = abs(start - goal.target_value)
            if total_distance < 0.1:
                percent = 100 if abs(current - goal.target_value) < 0.1 else 0
            else:
                progress = total_distance - abs(current - goal.target_value)
                percent = min(100, max(0, round((progress / total_distance) * 100)))
            status = f"{current:.1f} kg now"
    else:
        current = context.get(goal.goal_type, 0)
        percent = progress_percent(current, goal.target_value)
        status = f"{int(current)} {goal.unit} today"

    return {
        "label": goal_label(goal.goal_type),
        "current": current,
        "target": goal.target_value,
        "unit": goal.unit,
        "percent": percent,
        "status": status,
    }


def build_dashboard_context():
    today = date.today()
    week_start = today - timedelta(days=6)

    recent_workouts = (
        Workout.query.filter_by(user_id=current_user.id)
        .order_by(Workout.workout_date.desc(), Workout.created_at.desc())
        .limit(8)
        .all()
    )
    weekly_workouts = Workout.query.filter(
        Workout.user_id == current_user.id,
        Workout.workout_date >= week_start,
    ).all()
    water_logs = (
        WaterLog.query.filter_by(user_id=current_user.id)
        .order_by(WaterLog.recorded_on.desc(), WaterLog.created_at.desc())
        .limit(7)
        .all()
    )
    weekly_water_logs = WaterLog.query.filter(
        WaterLog.user_id == current_user.id,
        WaterLog.recorded_on >= week_start,
    ).all()
    weekly_step_logs = StepLog.query.filter(
        StepLog.user_id == current_user.id,
        StepLog.recorded_on >= week_start,
    ).all()
    metrics = (
        BodyMetric.query.filter_by(user_id=current_user.id)
        .order_by(BodyMetric.recorded_on.desc(), BodyMetric.created_at.desc())
        .limit(10)
        .all()
    )

    today_workouts = [workout for workout in weekly_workouts if workout.workout_date == today]
    today_water_ml = sum(log.water_ml for log in weekly_water_logs if log.recorded_on == today)
    today_steps = get_today_steps(today)
    today_workout_minutes = sum(workout.duration_minutes for workout in today_workouts)
    today_calories = sum(workout.calories or 0 for workout in today_workouts)
    water_goal = max(1, current_user.daily_water_goal_ml or current_app.config["DAILY_WATER_TARGET_ML"])
    step_goal = max(1, current_user.daily_step_goal or 10000)
    workout_goal = max(1, current_user.daily_workout_goal_minutes or 30)
    latest = metrics[0] if metrics else None
    latest_weight = safe_metric_weight(latest)
    bmi = calculate_bmi(current_user.height_cm, latest_weight)
    category, bmi_explanation = bmi_category(bmi)

    active_goals = (
        Goal.query.filter_by(user_id=current_user.id, is_active=True)
        .order_by(Goal.updated_at.desc())
        .all()
    )
    goal_context = {
        "water": today_water_ml,
        "steps": today_steps,
        "workout_minutes": today_workout_minutes,
        "workout_sessions": len(today_workouts),
        "calories": today_calories,
        "latest_weight": latest_weight,
    }

    stats = {
        "minutes": sum(workout.duration_minutes for workout in weekly_workouts),
        "sessions": len(weekly_workouts),
        "calories": sum(workout.calories or 0 for workout in weekly_workouts),
        "steps": sum(log.steps for log in weekly_step_logs),
        "water_ml": sum(log.water_ml for log in weekly_water_logs),
        "today_water_ml": today_water_ml,
        "water_target_ml": water_goal,
        "water_percent": progress_percent(today_water_ml, water_goal),
        "today_steps": today_steps,
        "step_target": step_goal,
        "step_percent": progress_percent(today_steps, step_goal),
        "estimated_step_calories": round(today_steps * 0.04),
        "today_workout_minutes": today_workout_minutes,
        "workout_target": workout_goal,
        "workout_percent": progress_percent(today_workout_minutes, workout_goal),
        "today_calories": today_calories,
        "bmi": bmi,
        "bmi_category": category,
        "bmi_explanation": bmi_explanation,
    }

    return {
        "workouts": recent_workouts,
        "today_workouts": today_workouts,
        "water_logs": water_logs,
        "metrics": metrics,
        "stats": stats,
        "weight_progress": build_weight_progress(metrics),
        "daily_tip": daily_tip(),
        "goal_progress": [goal_progress(goal, goal_context) for goal in active_goals],
    }


def sync_goal_to_profile(goal_type, target_value):
    if goal_type == "water":
        current_user.daily_water_goal_ml = int(target_value)
    elif goal_type == "steps":
        current_user.daily_step_goal = int(target_value)
    elif goal_type == "workout_minutes":
        current_user.daily_workout_goal_minutes = int(target_value)
    elif goal_type == "weight":
        current_user.weight_goal_kg = float(target_value)


@fitness_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if request.method == "POST":
        form_name = request.form.get("form_name")
        routes = {
            "workout": "fitness.add_workout",
            "water": "fitness.add_water",
            "water_update": "fitness.update_water",
            "water_reset": "fitness.reset_today_water",
            "steps": "fitness.update_steps",
            "bmi": "fitness.update_bmi",
            "goal": "fitness.save_goal",
            "reset_data": "fitness.reset_data",
        }
        endpoint = routes.get(form_name)
        if endpoint:
            return redirect(url_for(endpoint), code=307)

    sports = load_sports()
    workout_form = WorkoutForm()
    apply_sports_choices(workout_form, sports)
    water_form = WaterLogForm()
    water_total_form = WaterTotalForm()
    water_reset_form = WaterResetForm()
    step_form = StepLogForm()
    bmi_form = BMIForm(height_cm=current_user.height_cm)
    goal_form = GoalForm()
    reset_form = ResetDataForm()
    context = build_dashboard_context()
    context.update(
        {
            "workout_form": workout_form,
            "water_form": water_form,
            "water_total_form": water_total_form,
            "water_reset_form": water_reset_form,
            "step_form": step_form,
            "bmi_form": bmi_form,
            "goal_form": goal_form,
            "reset_form": reset_form,
            "sports": sports,
        }
    )
    return render_template("dashboard.html", **context)


@fitness_bp.route("/workouts", methods=["POST"])
@login_required
def add_workout():
    sports = load_sports()
    form = WorkoutForm()
    apply_sports_choices(form, sports)
    if form.validate_on_submit():
        activity = form.activity.data
        if activity not in sports:
            flash("Choose a supported activity.", "error")
            return redirect(url_for("fitness.dashboard"))

        minutes = form.duration_minutes.data
        estimated_calories = int(round(sports[activity]["calories_per_min"] * minutes))
        estimated_steps = int(round(sports[activity]["steps_per_min"] * minutes))
        workout = Workout(
            user_id=current_user.id,
            activity=activity,
            duration_minutes=minutes,
            calories=form.calories.data if form.calories.data is not None else estimated_calories,
            steps=form.steps.data if form.steps.data is not None else estimated_steps,
            workout_date=form.workout_date.data,
            start_latitude=form.start_latitude.data,
            start_longitude=form.start_longitude.data,
            end_latitude=form.end_latitude.data,
            end_longitude=form.end_longitude.data,
        )
        db.session.add(workout)
        commit_or_flash("Workout added.", "We could not save the workout.")
    else:
        flash("Check the workout form and try again.", "error")
    return redirect(url_for("fitness.dashboard"))


@fitness_bp.route("/water/add", methods=["POST"])
@login_required
def add_water():
    form = WaterLogForm()
    if form.validate_on_submit():
        water_log = WaterLog(
            user_id=current_user.id,
            water_ml=form.water_ml.data,
            recorded_on=form.recorded_on.data,
        )
        db.session.add(water_log)
        commit_or_flash("Water intake saved.", "We could not save water intake.")
    else:
        flash("Enter a valid water amount.", "error")
    return redirect(url_for("fitness.dashboard"))


@fitness_bp.route("/water/update", methods=["POST"])
@login_required
def update_water():
    form = WaterTotalForm()
    today = date.today()
    if form.validate_on_submit():
        WaterLog.query.filter_by(user_id=current_user.id, recorded_on=today).delete()
        if form.total_ml.data > 0:
            db.session.add(
                WaterLog(
                    user_id=current_user.id,
                    water_ml=form.total_ml.data,
                    recorded_on=today,
                )
            )
        commit_or_flash("Today's water total updated.", "We could not update water intake.")
    else:
        flash("Enter a valid corrected water total.", "error")
    return redirect(url_for("fitness.dashboard"))


@fitness_bp.route("/water/reset-today", methods=["POST"])
@login_required
def reset_today_water():
    form = WaterResetForm()
    if form.validate_on_submit():
        today = date.today()
        WaterLog.query.filter_by(user_id=current_user.id, recorded_on=today).delete()
        commit_or_flash("Today's water data was reset.", "We could not reset water data.")
    else:
        flash("Water reset request was not valid.", "error")
    return redirect(url_for("fitness.dashboard"))


@fitness_bp.route("/steps", methods=["POST"])
@login_required
def update_steps():
    form = StepLogForm()
    if form.validate_on_submit():
        step_log = StepLog.query.filter_by(
            user_id=current_user.id,
            recorded_on=form.recorded_on.data,
        ).first()
        if not step_log:
            step_log = StepLog(
                user_id=current_user.id,
                recorded_on=form.recorded_on.data,
            )
            db.session.add(step_log)
        step_log.steps = form.steps.data
        commit_or_flash("Steps updated.", "We could not update steps.")
    else:
        flash("Enter a valid step count.", "error")
    return redirect(url_for("fitness.dashboard"))


@fitness_bp.route("/bmi", methods=["POST"])
@login_required
def update_bmi():
    form = BMIForm()
    if form.validate_on_submit():
        current_user.height_cm = form.height_cm.data
        metric = BodyMetric(
            user_id=current_user.id,
            weight_kg=form.weight_kg.data,
            recorded_on=form.recorded_on.data,
        )
        db.session.add(metric)
        current_user.update_current_bmi(form.weight_kg.data)
        commit_or_flash("BMI and weight saved.", "We could not save BMI data.")
    else:
        flash("Enter valid height and weight values.", "error")
    return redirect(url_for("fitness.dashboard"))


@fitness_bp.route("/goals", methods=["POST"])
@login_required
def save_goal():
    form = GoalForm()
    if form.validate_on_submit():
        goal_type = form.goal_type.data
        unit = GOAL_UNITS.get(goal_type, "")
        goal = Goal.query.filter_by(
            user_id=current_user.id,
            goal_type=goal_type,
            is_active=True,
        ).first()
        if not goal:
            goal = Goal(user_id=current_user.id, goal_type=goal_type, unit=unit)
            db.session.add(goal)
        goal.target_value = form.target_value.data
        goal.unit = unit
        if goal_type == "weight" and goal.start_value is None:
            metric = latest_metric()
            start_weight = safe_metric_weight(metric)
            goal.start_value = start_weight if start_weight is not None else form.target_value.data
        sync_goal_to_profile(goal_type, form.target_value.data)
        commit_or_flash("Goal saved.", "We could not save your goal.")
    else:
        flash("Enter a valid goal target.", "error")
    return redirect(url_for("fitness.dashboard"))


@fitness_bp.route("/weight", methods=["POST"])
@login_required
def save_weight():
    form = BodyMetricForm()
    if form.validate_on_submit():
        metric = BodyMetric(
            user_id=current_user.id,
            weight_kg=form.weight_kg.data,
            body_fat_percent=form.body_fat_percent.data,
            recorded_on=form.recorded_on.data,
        )
        db.session.add(metric)
        current_user.update_current_bmi(form.weight_kg.data)
        commit_or_flash("Weight saved.", "We could not save your weight.")
    else:
        flash("Enter valid weight data.", "error")
    return redirect(url_for("fitness.dashboard"))


@fitness_bp.route("/reset-data", methods=["POST"])
@login_required
def reset_data():
    form = ResetDataForm()
    if not form.validate_on_submit():
        flash("Confirm the reset before deleting fitness data.", "error")
        return redirect(url_for("fitness.dashboard"))

    for model in (Workout, WaterLog, StepLog, BodyMetric, Goal):
        model.query.filter_by(user_id=current_user.id).delete()
    current_user.current_bmi = None
    if commit_or_flash(
        "Fitness data reset. Your account and Premium status were kept.",
        "We could not reset your fitness data.",
    ):
        return redirect(url_for("fitness.dashboard"))
    return redirect(url_for("fitness.dashboard"))


@fitness_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        current_user.country = (form.country.data or "").strip()
        current_user.height_cm = form.height_cm.data
        current_user.weight_goal_kg = form.weight_goal_kg.data
        current_user.daily_water_goal_ml = form.daily_water_goal_ml.data
        current_user.daily_step_goal = form.daily_step_goal.data
        current_user.daily_workout_goal_minutes = form.daily_workout_goal_minutes.data
        current_user.privacy_zones_enabled = form.privacy_zones_enabled.data
        current_user.privacy_zone_name = (form.privacy_zone_name.data or "").strip()
        current_user.privacy_zone_latitude = form.privacy_zone_latitude.data
        current_user.privacy_zone_longitude = form.privacy_zone_longitude.data
        current_user.privacy_zone_radius_meters = (
            form.privacy_zone_radius_meters.data or 250
        )
        current_user.allow_third_party_tracking = form.allow_third_party_tracking.data
        metric = latest_metric()
        if metric:
            current_user.update_current_bmi(metric.weight_kg)
        commit_or_flash("Profile updated.", "We could not update your profile.")
        return redirect(url_for("fitness.profile"))

    return render_template("profile.html", form=form), (
        400 if request.method == "POST" else 200
    )


@fitness_bp.route("/metrics", methods=["GET", "POST"])
@login_required
def metrics():
    form = BodyMetricForm()
    if form.validate_on_submit():
        metric = BodyMetric(
            user_id=current_user.id,
            weight_kg=form.weight_kg.data,
            body_fat_percent=form.body_fat_percent.data,
            recorded_on=form.recorded_on.data,
        )
        db.session.add(metric)
        current_user.update_current_bmi(form.weight_kg.data)
        commit_or_flash("Metrics saved.", "We could not save metrics.")
        return redirect(url_for("fitness.metrics"))

    metric_history = (
        BodyMetric.query.filter_by(user_id=current_user.id)
        .order_by(BodyMetric.recorded_on.desc(), BodyMetric.created_at.desc())
        .limit(10)
        .all()
    )
    latest = metric_history[0] if metric_history else None
    previous = metric_history[1] if len(metric_history) > 1 else None
    weight_change = None
    if latest and previous:
        latest_weight = safe_metric_weight(latest)
        previous_weight = safe_metric_weight(previous)
        if latest_weight is not None and previous_weight is not None:
            weight_change = latest_weight - previous_weight

    return render_template(
        "metrics.html",
        form=form,
        metrics=metric_history,
        latest_metric=latest,
        weight_change=weight_change,
    )


@fitness_bp.route("/analytics")
@login_required
def analytics():
    start = date.today() - timedelta(days=6)
    days = [start + timedelta(days=offset) for offset in range(7)]
    minutes_by_day = {day: 0 for day in days}
    calories_by_day = {day: 0 for day in days}
    water_by_day = {day: 0 for day in days}
    steps_by_day = {day: 0 for day in days}
    activity_minutes = {}

    workouts = Workout.query.filter(
        Workout.user_id == current_user.id,
        Workout.workout_date >= start,
    ).all()
    for workout in workouts:
        if workout.workout_date in minutes_by_day:
            minutes_by_day[workout.workout_date] += workout.duration_minutes
            calories_by_day[workout.workout_date] += workout.calories or 0
        activity_minutes[workout.activity] = (
            activity_minutes.get(workout.activity, 0) + workout.duration_minutes
        )

    water_logs = WaterLog.query.filter(
        WaterLog.user_id == current_user.id,
        WaterLog.recorded_on >= start,
    ).all()
    for water_log in water_logs:
        if water_log.recorded_on in water_by_day:
            water_by_day[water_log.recorded_on] += water_log.water_ml

    step_logs = StepLog.query.filter(
        StepLog.user_id == current_user.id,
        StepLog.recorded_on >= start,
    ).all()
    for step_log in step_logs:
        if step_log.recorded_on in steps_by_day:
            steps_by_day[step_log.recorded_on] += step_log.steps

    weight_metrics = (
        BodyMetric.query.filter_by(user_id=current_user.id)
        .order_by(BodyMetric.recorded_on.asc(), BodyMetric.created_at.asc())
        .limit(30)
        .all()
    )

    weight_points = [
        (metric.recorded_on.strftime("%d %b"), round(weight, 1))
        for metric in weight_metrics
        for weight in [safe_metric_weight(metric)]
        if weight is not None
    ]

    chart_data = {
        "labels": [day.strftime("%a") for day in days],
        "minutes": [minutes_by_day[day] for day in days],
        "water": [water_by_day[day] for day in days],
        "steps": [steps_by_day[day] for day in days],
        "calories": [calories_by_day[day] for day in days],
        "weight_labels": [point[0] for point in weight_points],
        "weight": [point[1] for point in weight_points],
    }
    total_minutes = sum(chart_data["minutes"])
    total_calories = sum(chart_data["calories"])
    total_steps = sum(chart_data["steps"])
    total_water_ml = sum(chart_data["water"])
    average_water_ml = round(total_water_ml / len(days))
    best_day = "No workouts yet"
    if total_minutes:
        best_day = max(minutes_by_day, key=minutes_by_day.get).strftime("%A")

    favorite_activity = "No workouts yet"
    if activity_minutes:
        favorite_activity = max(activity_minutes, key=activity_minutes.get)

    if workouts or water_logs or step_logs:
        fitness_report = (
            f"In the last 7 days you logged {total_steps} steps, "
            f"{total_water_ml} ml of water, {total_minutes} workout minutes, "
            f"and about {total_calories} calories burned."
        )
    else:
        fitness_report = (
            "No fitness data has been logged in the last 7 days. Add entries "
            "from the dashboard to build your personal report."
        )

    active_goals = Goal.query.filter_by(user_id=current_user.id, is_active=True).all()
    latest = latest_metric()
    today = date.today()
    goal_context = {
        "water": water_by_day.get(today, 0),
        "steps": steps_by_day.get(today, 0),
        "workout_minutes": minutes_by_day.get(today, 0),
        "workout_sessions": len(get_today_workouts(today)),
        "calories": calories_by_day.get(today, 0),
        "latest_weight": safe_metric_weight(latest),
    }

    advanced_insights = []
    if current_user.premium_is_active:
        target_water_days = sum(
            1
            for value in chart_data["water"]
            if value >= (current_user.daily_water_goal_ml or 2000)
        )
        workout_goal_days = sum(
            1
            for value in chart_data["minutes"]
            if value >= (current_user.daily_workout_goal_minutes or 30)
        )
        advanced_insights = [
            f"Average daily steps: {round(total_steps / len(days))}.",
            f"Water goal reached on {target_water_days} of 7 days.",
            f"Workout goal reached on {workout_goal_days} of 7 days.",
        ]
        if len(weight_metrics) >= 2:
            first_weight = safe_metric_weight(weight_metrics[0])
            last_weight = safe_metric_weight(weight_metrics[-1])
            if first_weight is not None and last_weight is not None:
                change = last_weight - first_weight
                advanced_insights.append(f"Weight change across recorded history: {change:+.1f} kg.")

    totals = {
        "minutes": total_minutes,
        "calories": total_calories,
        "steps": total_steps,
        "water_ml": total_water_ml,
        "average_water_ml": average_water_ml,
        "best_day": best_day,
        "favorite_activity": favorite_activity,
    }
    return render_template(
        "analytics.html",
        chart_data=chart_data,
        fitness_report=fitness_report,
        totals=totals,
        goal_progress=[goal_progress(goal, goal_context) for goal in active_goals],
        advanced_insights=advanced_insights,
    )


@fitness_bp.route("/games")
@login_required
def games():
    return render_template("games.html")
