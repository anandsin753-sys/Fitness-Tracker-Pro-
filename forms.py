from datetime import date
import math

from flask import current_app
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    EmailField,
    FloatField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)


GOAL_TYPE_CHOICES = [
    ("water", "Water intake"),
    ("steps", "Steps"),
    ("weight", "Weight"),
    ("workout_minutes", "Workout minutes"),
    ("workout_sessions", "Workout sessions"),
    ("calories", "Calories burned"),
]

GOAL_UNITS = {
    "water": "ml",
    "steps": "steps",
    "weight": "kg",
    "workout_minutes": "minutes",
    "workout_sessions": "sessions",
    "calories": "calories",
}


class FiniteNumber:
    def __call__(self, form, field):
        if field.data is None:
            return
        try:
            value = float(field.data)
        except (TypeError, ValueError):
            raise ValidationError("Enter a valid number.")
        if not math.isfinite(value):
            raise ValidationError("Enter a finite number.")


class PasswordStrength:
    def __call__(self, form, field):
        password = field.data or ""
        has_upper = any(character.isupper() for character in password)
        has_lower = any(character.islower() for character in password)
        has_digit = any(character.isdigit() for character in password)
        if not (has_upper and has_lower and has_digit):
            raise ValidationError(
                "Use at least one uppercase letter, one lowercase letter, and one number."
            )


def country_choices(selected=None):
    countries = current_app.config.get("COUNTRIES", [])
    choices = [("", "Select a country")]
    seen = {""}

    for country in countries:
        name = country.get("name", "").strip()
        if name and name not in seen:
            choices.append((name, name))
            seen.add(name)

    if selected and selected not in seen:
        choices.append((selected, selected))

    return choices


def set_country_choices(form, selected=None):
    if hasattr(form, "country"):
        form.country.choices = country_choices(selected)


def set_activity_choices(form, sports):
    if hasattr(form, "activity"):
        form.activity.choices = [(activity, activity) for activity in sports]


class SignupForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired(message="Enter your name."), Length(max=120)],
    )
    email = EmailField(
        "Email",
        validators=[
            DataRequired(message="Enter your email."),
            Email(message="Enter a valid email address."),
            Length(max=255),
        ],
    )
    country = SelectField(
        "Country",
        choices=[],
        validators=[DataRequired(message="Choose your country.")],
    )
    height_cm = FloatField(
        "Height (cm)",
        validators=[
            InputRequired(message="Enter your height."),
            FiniteNumber(),
            NumberRange(min=80, max=250),
        ],
    )
    weight_kg = FloatField(
        "Current weight (kg)",
        validators=[
            InputRequired(message="Enter your current weight."),
            FiniteNumber(),
            NumberRange(min=20, max=500),
        ],
    )
    weight_goal_kg = FloatField(
        "Weight goal (kg)",
        validators=[
            Optional(),
            FiniteNumber(),
            NumberRange(min=20, max=500),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Enter a password."),
            Length(min=8, message="Use at least 8 characters."),
            PasswordStrength(),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Confirm your password."),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    submit = SubmitField("Create Account")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_country_choices(self, self.country.data)


class LoginForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[
            DataRequired(message="Enter your email."),
            Email(message="Enter a valid email address."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Enter your password.")],
    )
    submit = SubmitField("Log In")


class ResendVerificationForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[
            DataRequired(message="Enter your email."),
            Email(message="Enter a valid email address."),
            Length(max=255),
        ],
    )
    submit = SubmitField("Resend Verification Email")


class ProfileForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired(message="Enter your name."), Length(max=120)],
    )
    country = SelectField(
        "Country",
        choices=[],
        validators=[DataRequired(message="Choose your country.")],
    )
    height_cm = FloatField(
        "Height (cm)",
        validators=[
            Optional(),
            FiniteNumber(),
            NumberRange(min=80, max=250),
        ],
    )
    weight_goal_kg = FloatField(
        "Weight goal (kg)",
        validators=[
            Optional(),
            FiniteNumber(),
            NumberRange(min=20, max=500),
        ],
    )
    daily_water_goal_ml = IntegerField(
        "Daily water goal (ml)",
        validators=[InputRequired(), NumberRange(min=250, max=10000)],
    )
    daily_step_goal = IntegerField(
        "Daily step goal",
        validators=[InputRequired(), NumberRange(min=100, max=100000)],
    )
    daily_workout_goal_minutes = IntegerField(
        "Daily workout goal (minutes)",
        validators=[InputRequired(), NumberRange(min=5, max=300)],
    )
    privacy_zones_enabled = BooleanField("Hide workouts inside privacy zone")
    privacy_zone_name = StringField(
        "Privacy Zone Name",
        validators=[Optional(), Length(max=120)],
    )
    privacy_zone_latitude = FloatField(
        "Privacy Zone Latitude",
        validators=[Optional(), FiniteNumber(), NumberRange(min=-90, max=90)],
    )
    privacy_zone_longitude = FloatField(
        "Privacy Zone Longitude",
        validators=[Optional(), FiniteNumber(), NumberRange(min=-180, max=180)],
    )
    privacy_zone_radius_meters = IntegerField(
        "Privacy Zone Radius (meters)",
        validators=[Optional(), NumberRange(min=50, max=5000)],
    )
    allow_third_party_tracking = BooleanField("Allow third-party ad tracking")
    submit = SubmitField("Save Profile")

    def __init__(self, *args, **kwargs):
        selected = kwargs.get("obj").country if kwargs.get("obj") else None
        super().__init__(*args, **kwargs)
        set_country_choices(self, selected or self.country.data)


class WorkoutForm(FlaskForm):
    activity = SelectField(
        "Activity",
        choices=[],
        validators=[DataRequired(message="Choose an activity.")],
    )
    duration_minutes = IntegerField(
        "Minutes",
        validators=[
            InputRequired(message="Enter workout duration."),
            NumberRange(min=1, max=300),
        ],
    )
    workout_date = DateField(
        "Date",
        validators=[DataRequired()],
        default=date.today,
    )
    start_latitude = FloatField(
        "Start Latitude",
        validators=[Optional(), FiniteNumber(), NumberRange(min=-90, max=90)],
    )
    start_longitude = FloatField(
        "Start Longitude",
        validators=[Optional(), FiniteNumber(), NumberRange(min=-180, max=180)],
    )
    end_latitude = FloatField(
        "End Latitude",
        validators=[Optional(), FiniteNumber(), NumberRange(min=-90, max=90)],
    )
    end_longitude = FloatField(
        "End Longitude",
        validators=[Optional(), FiniteNumber(), NumberRange(min=-180, max=180)],
    )
    calories = IntegerField(
        "Calories (Optional)",
        validators=[Optional(), NumberRange(min=0, max=6000)],
    )
    steps = IntegerField(
        "Steps (Optional)",
        validators=[Optional(), NumberRange(min=0, max=100000)],
    )
    submit = SubmitField("Save Workout")


class BodyMetricForm(FlaskForm):
    weight_kg = FloatField(
        "Weight (kg)",
        validators=[
            InputRequired(message="Enter your weight."),
            FiniteNumber(),
            NumberRange(min=20, max=500),
        ],
    )
    body_fat_percent = FloatField(
        "Body Fat % (Optional)",
        validators=[Optional(), FiniteNumber(), NumberRange(min=0, max=75)],
    )
    recorded_on = DateField(
        "Date",
        validators=[DataRequired()],
        default=date.today,
    )
    submit = SubmitField("Save Metrics")


class WaterLogForm(FlaskForm):
    water_ml = IntegerField(
        "Water (ml)",
        validators=[
            InputRequired(message="Enter water amount."),
            NumberRange(min=1, max=10000),
        ],
    )
    recorded_on = DateField(
        "Date",
        validators=[DataRequired()],
        default=date.today,
    )
    submit = SubmitField("Add Water")


class WaterTotalForm(FlaskForm):
    total_ml = IntegerField(
        "Correct today's total (ml)",
        validators=[
            InputRequired(message="Enter the corrected total."),
            NumberRange(min=0, max=20000),
        ],
    )
    submit = SubmitField("Update Total")


class WaterResetForm(FlaskForm):
    submit = SubmitField("Reset Today's Water")


class StepLogForm(FlaskForm):
    steps = IntegerField(
        "Steps",
        validators=[
            InputRequired(message="Enter your steps."),
            NumberRange(min=0, max=100000),
        ],
    )
    recorded_on = DateField(
        "Date",
        validators=[DataRequired()],
        default=date.today,
    )
    submit = SubmitField("Update Steps")


class BMIForm(FlaskForm):
    height_cm = FloatField(
        "Height (cm)",
        validators=[
            InputRequired(message="Enter your height."),
            FiniteNumber(),
            NumberRange(min=80, max=250),
        ],
    )
    weight_kg = FloatField(
        "Weight (kg)",
        validators=[
            InputRequired(message="Enter your weight."),
            FiniteNumber(),
            NumberRange(min=20, max=500),
        ],
    )
    recorded_on = DateField(
        "Date",
        validators=[DataRequired()],
        default=date.today,
    )
    submit = SubmitField("Calculate BMI")


class GoalForm(FlaskForm):
    goal_type = SelectField(
        "Goal",
        choices=GOAL_TYPE_CHOICES,
        validators=[DataRequired()],
    )
    target_value = FloatField(
        "Target",
        validators=[
            InputRequired(message="Enter a target value."),
            FiniteNumber(),
            NumberRange(min=0.1, max=500000),
        ],
    )
    submit = SubmitField("Save Goal")


class ResetDataForm(FlaskForm):
    confirm_reset = BooleanField(
        "I understand this deletes my fitness history but keeps my account.",
        validators=[DataRequired(message="Confirm before resetting fitness data.")],
    )
    submit = SubmitField("Reset Fitness Data")


class PremiumForm(FlaskForm):
    submit = SubmitField("Pay securely with Razorpay")


class PaymentVerificationForm(FlaskForm):
    razorpay_order_id = StringField(
        validators=[DataRequired(), Length(max=64)],
    )
    razorpay_payment_id = StringField(
        validators=[DataRequired(), Length(max=64)],
    )
    razorpay_signature = StringField(
        validators=[DataRequired(), Length(min=64, max=64)],
    )


class CalorieCalculatorForm(FlaskForm):
    activity = SelectField(
        "Activity",
        choices=[],
        validators=[DataRequired(message="Choose an activity.")],
    )
    duration_minutes = IntegerField(
        "Duration (minutes)",
        validators=[
            InputRequired(message="Enter duration."),
            NumberRange(min=1, max=300),
        ],
    )
    submit = SubmitField("Calculate Calories")
