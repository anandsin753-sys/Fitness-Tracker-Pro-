from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from fitness import apply_sports_choices, load_sports
from forms import CalorieCalculatorForm, PremiumForm
from models import db


premium_bp = Blueprint("premium", __name__)


@premium_bp.route("/premium", methods=["GET", "POST"])
def premium():
    premium_form = PremiumForm()
    calculator_form = CalorieCalculatorForm()
    sports = load_sports()
    apply_sports_choices(calculator_form, sports)
    calorie_result = None

    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Log in before using Premium features.", "info")
            return redirect(url_for("auth.login"))

        form_name = request.form.get("form_name")
        if form_name == "activate" and premium_form.validate_on_submit():
            current_user.activate_premium(days=30)
            try:
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                flash("We could not activate Premium. Please try again.", "error")
            else:
                flash("Demo Premium started for 30 days. No payment was processed.", "success")
                return redirect(url_for("fitness.dashboard"))

        elif form_name == "calculator":
            if not current_user.premium_is_active:
                flash("The calorie calculator requires Premium.", "info")
                return redirect(url_for("premium.premium"))
            if calculator_form.validate_on_submit():
                activity = calculator_form.activity.data
                duration = calculator_form.duration_minutes.data
                if activity not in sports:
                    flash("Choose a supported activity.", "error")
                else:
                    calories = int(round(sports[activity]["calories_per_min"] * duration))
                    calorie_result = {
                        "activity": activity,
                        "duration": duration,
                        "calories": calories,
                    }
            else:
                flash("Enter a valid activity and duration.", "error")

    return render_template(
        "premium.html",
        form=premium_form,
        calculator_form=calculator_form,
        calorie_result=calorie_result,
    )
