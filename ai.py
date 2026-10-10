import json
import math
import random
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, IntegerField, SelectField
from wtforms.validators import InputRequired, NumberRange


ai_bp = Blueprint("ai", __name__)

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "very_active": 1.725,
    "extra_active": 1.9,
}
GOAL_FACTORS = {
    "maintain": 1.0,
    "gradual_loss": 0.9,
    "gradual_gain": 1.05,
}
EQUATION_COEFFICIENTS = {"female": -161, "male": 5}
MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")
MEAL_DATA_PATH = Path(__file__).resolve().with_name("nutrition_data.json")


class NutritionForm(FlaskForm):
    age = IntegerField(
        "Age",
        validators=[InputRequired(), NumberRange(min=18, max=80)],
    )
    weight_kg = FloatField(
        "Weight",
        validators=[InputRequired(), NumberRange(min=35, max=250)],
    )
    height_cm = FloatField(
        "Height",
        validators=[InputRequired(), NumberRange(min=130, max=220)],
    )
    equation = SelectField(
        "Mifflin–St Jeor equation profile",
        choices=[
            ("", "Choose a profile or show a range"),
            ("female", "Female coefficient"),
            ("male", "Male coefficient"),
            ("range", "Show a range"),
        ],
        validators=[InputRequired()],
    )
    activity = SelectField(
        "Typical activity",
        choices=[
            ("", "Choose your usual activity"),
            ("sedentary", "Mostly sitting, little planned exercise"),
            ("light", "Light exercise 1–3 days per week"),
            ("moderate", "Moderate exercise 3–5 days per week"),
            ("very_active", "Hard exercise 6–7 days per week"),
            ("extra_active", "Very hard training or physical job"),
        ],
        validators=[InputRequired()],
    )
    goal = SelectField(
        "Your focus",
        choices=[
            ("", "Choose a focus"),
            ("maintain", "Maintain my weight"),
            ("gradual_loss", "Gradual weight loss"),
            ("gradual_gain", "Gradual weight gain"),
        ],
        validators=[InputRequired()],
    )
    dietary_style = SelectField(
        "Food preference",
        choices=[
            ("", "Choose a food preference"),
            ("omnivore", "No restriction"),
            ("vegetarian", "Vegetarian"),
            ("vegan", "Vegan"),
            ("pescatarian", "Pescatarian"),
        ],
        validators=[InputRequired()],
    )
    cuisine = SelectField(
        "Cuisine preference",
        choices=[
            ("", "Choose a cuisine preference"),
            ("flexible", "Flexible / any cuisine"),
            ("indian", "Indian-inspired"),
            ("mediterranean", "Mediterranean-inspired"),
            ("east_asian", "East Asian-inspired"),
            ("latin_american", "Latin American-inspired"),
        ],
        validators=[InputRequired()],
    )
    risk_factor = SelectField(
        "Does any special situation apply?",
        choices=[
            ("", "Choose one"),
            ("none", "None of these apply"),
            ("pregnancy", "Pregnant or breastfeeding"),
            ("medical", "Medical condition or prescribed diet"),
            ("eating_disorder", "History of disordered eating"),
            ("food_allergy", "Food allergy or food-safety restriction"),
        ],
        validators=[InputRequired()],
    )
class PlanUnavailable(Exception):
    """The local meal dataset cannot provide a plan."""


def _round_calories(value):
    return int(round(value / 10) * 10)


def calculate_calorie_estimate(data):
    """Return a transparent adult estimate using Mifflin–St Jeor."""
    age = int(data["age"])
    weight_kg = float(data["weight_kg"])
    height_cm = float(data["height_cm"])
    if not all(math.isfinite(value) for value in (weight_kg, height_cm)):
        raise ValueError("Enter a valid height and weight.")

    coefficients = (
        [EQUATION_COEFFICIENTS[data["equation"]]]
        if data["equation"] in EQUATION_COEFFICIENTS
        else list(EQUATION_COEFFICIENTS.values())
    )
    resting = [
        10 * weight_kg + 6.25 * height_cm - 5 * age + coefficient
        for coefficient in coefficients
    ]
    activity_factor = ACTIVITY_FACTORS[data["activity"]]
    goal_factor = GOAL_FACTORS[data["goal"]]
    maintenance = [value * activity_factor for value in resting]
    targets = [value * goal_factor for value in maintenance]

    rounded_targets = [_round_calories(value) for value in targets]
    if min(rounded_targets) < 1000:
        raise ValueError(
            "This estimate is below the 1,000 kcal/day minimum used by the NIDDK Body Weight Planner. Please consult a registered dietitian for a personalized plan."
        )

    bmi = weight_kg / ((height_cm / 100) ** 2)
    if data["goal"] == "gradual_loss" and bmi < 18.5:
        raise ValueError(
            "This tool cannot create a weight-loss plan at this estimated BMI. Please discuss your goal with a clinician or registered dietitian."
        )

    return {
        "resting": {
            "min": _round_calories(min(resting)),
            "max": _round_calories(max(resting)),
        },
        "maintenance": {
            "min": _round_calories(min(maintenance)),
            "max": _round_calories(max(maintenance)),
        },
        "target": {
            "min": min(rounded_targets),
            "max": max(rounded_targets),
        },
        "plan_target": _round_calories(sum(rounded_targets) / len(rounded_targets)),
        "goal": data["goal"],
        "is_range": len(rounded_targets) > 1,
    }


def _load_nutrition_data():
    try:
        dataset = json.loads(MEAL_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PlanUnavailable(
            "The local meal data file could not be loaded. Check nutrition_data.json."
        ) from error

    if not isinstance(dataset, dict) or not isinstance(dataset.get("recipes"), list):
        raise PlanUnavailable("The local meal data file has an invalid format.")
    return dataset


def generate_week_plan(calories, dietary_style, cuisine, preference_seed=""):
    """Build a seven-day plan from bundled data without network/API access."""
    dataset = _load_nutrition_data()
    recipes = [
        recipe
        for recipe in dataset["recipes"]
        if isinstance(recipe, dict)
        and recipe.get("meal_type") in MEAL_TYPES
        and dietary_style in recipe.get("dietary_styles", [])
    ]
    if not recipes:
        raise PlanUnavailable("No meals in the local data match this food preference.")

    cuisine_recipes = (
        recipes if cuisine == "flexible" else
        [recipe for recipe in recipes if recipe.get("cuisine") == cuisine]
    )
    cuisine_fallback = not cuisine_recipes
    if cuisine_fallback:
        cuisine_recipes = recipes

    shares = dataset.get(
        "meal_shares",
        {"breakfast": 0.25, "lunch": 0.30, "dinner": 0.30, "snack": 0.15},
    )
    rng = random.Random(f"{preference_seed}|{dietary_style}|{cuisine}|{calories}")
    used_by_type = {meal_type: set() for meal_type in MEAL_TYPES}
    days = []
    shopping_items = []

    for day_number in range(1, 8):
        meals = []
        for meal_type in MEAL_TYPES:
            candidates = [
                recipe for recipe in cuisine_recipes
                if recipe.get("meal_type") == meal_type
            ]
            if not candidates:
                candidates = [
                    recipe for recipe in recipes
                    if recipe.get("meal_type") == meal_type
                ]
            if not candidates:
                raise PlanUnavailable(f"The local data has no {meal_type} options.")

            unused = [
                recipe for recipe in candidates
                if recipe.get("id") not in used_by_type[meal_type]
            ]
            if not unused:
                used_by_type[meal_type].clear()
                unused = candidates

            target_meal_kcal = calories * float(shares.get(meal_type, 0))
            ranked = sorted(
                unused,
                key=lambda recipe: abs(
                    float(recipe.get("kcal_per_serving", 0)) - target_meal_kcal
                ),
            )
            finalists = ranked[:min(3, len(ranked))]
            recipe = rng.choice(finalists)
            recipe_kcal = float(recipe.get("kcal_per_serving", 0))
            if recipe_kcal <= 0:
                raise PlanUnavailable("A meal entry in the local data has invalid calories.")

            scale = target_meal_kcal / recipe_kcal
            displayed_kcal = _round_calories(recipe_kcal * scale)
            base_portion = recipe.get("portion", "one serving")
            portion = (
                base_portion if 0.95 <= scale <= 1.05
                else f"About {scale:.1f}× the listed portion ({base_portion})"
            )
            ingredients = recipe.get("ingredients", [])
            if not isinstance(ingredients, list):
                raise PlanUnavailable("A meal entry in the local data has invalid ingredients.")

            meals.append({
                "meal_type": meal_type,
                "name": recipe.get("name", "Meal idea"),
                "portion": portion,
                "estimated_kcal": displayed_kcal,
                "ingredients": ingredients,
            })
            used_by_type[meal_type].add(recipe.get("id"))
            shopping_items.extend(ingredients)

        days.append({
            "day": day_number,
            "estimated_kcal": sum(meal["estimated_kcal"] for meal in meals),
            "meals": meals,
        })

    shopping_list = list(dict.fromkeys(shopping_items))[:30]
    summary = (
        f"Built locally from {len(dataset['recipes'])} meal ideas. Portions are adjusted "
        f"toward an estimated target of about {calories:,} kcal/day."
    )
    if cuisine_fallback:
        summary += " The selected cuisine had no matching meals for this food preference, so the planner used other matching options."
    summary += " " + dataset.get(
        "calorie_notice",
        "Meal calories are approximate estimates, not exact measurements.",
    )

    return {"summary": summary, "days": days, "shopping_list": shopping_list}


@ai_bp.get("/ai")
@login_required
def nutrition():
    return render_template("ai.html", form=NutritionForm())


@ai_bp.post("/api/nutrition-plan")
@login_required
def generate_plan():
    form = NutritionForm()
    if not form.validate_on_submit():
        first_error = next(
            (errors[0] for errors in form.errors.values() if errors),
            "Check the form and try again.",
        )
        return jsonify({"error": first_error}), 400

    if form.risk_factor.data != "none":
        return jsonify(
            {
                "error": (
                    "This planner is for general adult wellness only. For pregnancy, "
                    "medical conditions, food allergies, or eating-disorder support, "
                    "please ask a registered dietitian or clinician."
                )
            }
        ), 422
    data = {
        "age": form.age.data,
        "weight_kg": form.weight_kg.data,
        "height_cm": form.height_cm.data,
        "equation": form.equation.data,
        "activity": form.activity.data,
        "goal": form.goal.data,
    }
    try:
        calories = calculate_calorie_estimate(data)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        return jsonify({"error": str(error)}), 422

    plan_target = calories["plan_target"]
    calorie_summary = {
        key: value for key, value in calories.items() if key != "plan_target"
    }
    try:
        plan = generate_week_plan(
            plan_target,
            form.dietary_style.data,
            form.cuisine.data,
            preference_seed="|".join(str(data[key]) for key in ("age", "weight_kg", "height_cm", "equation", "activity", "goal")),
        )
    except PlanUnavailable as error:
        current_app.logger.info("Nutrition plan unavailable: %s", error)
        return jsonify({"error": str(error), "calories": calorie_summary}), 503
    except Exception:
        current_app.logger.exception("Unexpected nutrition planning error.")
        return jsonify(
            {
                "error": "The nutrition planner hit an unexpected error. Please try again.",
                "calories": calorie_summary,
            }
        ), 500

    return jsonify({"calories": calorie_summary, "plan": plan})

