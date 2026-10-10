import base64
from datetime import date, datetime, timedelta
import hashlib
import math

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def _get_health_data_cipher():
    key = current_app.config.get("HEALTH_DATA_ENCRYPTION_KEY")
    if key:
        try:
            return Fernet(key.encode("utf-8"))
        except (TypeError, ValueError):
            current_app.logger.warning(
                "Invalid HEALTH_DATA_ENCRYPTION_KEY; deriving a key from SECRET_KEY."
            )

    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(derived_key)


def encrypt_health_value(value):
    if value is None:
        return None

    payload = str(float(value)).encode("utf-8")
    return _get_health_data_cipher().encrypt(payload).decode("utf-8")


def decrypt_health_value(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value)
    try:
        return float(_get_health_data_cipher().decrypt(value.encode("utf-8")).decode("utf-8"))
    except InvalidToken:
        try:
            return float(value)
        except ValueError:
            return None


def is_encrypted_health_value(value):
    if not value or isinstance(value, (int, float)):
        return False

    try:
        _get_health_data_cipher().decrypt(str(value).encode("utf-8"))
    except InvalidToken:
        return False

    return True


def _format_coordinates(latitude, longitude):
    if latitude is None or longitude is None:
        return "-"
    return f"{latitude:.5f}, {longitude:.5f}"


def _distance_meters(start_latitude, start_longitude, end_latitude, end_longitude):
    earth_radius_meters = 6371000
    start_lat = math.radians(start_latitude)
    end_lat = math.radians(end_latitude)
    delta_lat = math.radians(end_latitude - start_latitude)
    delta_lon = math.radians(end_longitude - start_longitude)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(start_lat) * math.cos(end_lat) * math.sin(delta_lon / 2) ** 2
    )
    return earth_radius_meters * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    country = db.Column(db.String(120), default="")
    password_hash = db.Column(db.String(255), nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    premium_started_at = db.Column(db.DateTime)
    premium_expires_at = db.Column(db.DateTime)
    height_cm = db.Column(db.Float)
    weight_goal_kg = db.Column(db.Float)
    current_bmi = db.Column(db.Float)
    daily_water_goal_ml = db.Column(db.Integer, default=2000, nullable=False)
    daily_step_goal = db.Column(db.Integer, default=10000, nullable=False)
    daily_workout_goal_minutes = db.Column(db.Integer, default=30, nullable=False)
    allow_third_party_tracking = db.Column(db.Boolean, default=False, nullable=False)
    privacy_zones_enabled = db.Column(db.Boolean, default=True, nullable=False)
    privacy_zone_name = db.Column(db.String(120), default="")
    privacy_zone_latitude = db.Column(db.Float)
    privacy_zone_longitude = db.Column(db.Float)
    privacy_zone_radius_meters = db.Column(db.Integer, default=250, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    workouts = db.relationship("Workout", backref="user", cascade="all, delete-orphan")
    metrics = db.relationship("BodyMetric", backref="user", cascade="all, delete-orphan")
    water_logs = db.relationship("WaterLog", backref="user", cascade="all, delete-orphan")
    step_logs = db.relationship("StepLog", backref="user", cascade="all, delete-orphan")
    goals = db.relationship("Goal", backref="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def premium_is_active(self):
        if not self.is_premium:
            return False
        if not self.premium_expires_at:
            return True
        return datetime.utcnow() <= self.premium_expires_at

    @property
    def premium_days_remaining(self):
        if not self.premium_is_active or not self.premium_expires_at:
            return 0
        remaining = self.premium_expires_at.date() - date.today()
        return max(0, remaining.days)

    @property
    def premium_expiring_soon(self):
        return self.premium_is_active and 0 <= self.premium_days_remaining <= 10

    def activate_premium(self, days=30):
        now = datetime.utcnow()
        self.is_premium = True
        self.premium_started_at = now
        self.premium_expires_at = now + timedelta(days=days)

    def expire_premium_if_needed(self):
        if self.is_premium and self.premium_expires_at:
            if datetime.utcnow() > self.premium_expires_at:
                self.is_premium = False
                return True
        return False

    def update_current_bmi(self, weight_kg=None):
        if self.height_cm is None or weight_kg is None:
            return None
        if self.height_cm <= 0 or not math.isfinite(float(self.height_cm)):
            return None
        if weight_kg <= 0 or not math.isfinite(float(weight_kg)):
            return None

        height_m = self.height_cm / 100
        self.current_bmi = round(weight_kg / (height_m * height_m), 1)
        return self.current_bmi

    def privacy_zone_is_configured(self):
        return (
            self.privacy_zones_enabled
            and self.privacy_zone_latitude is not None
            and self.privacy_zone_longitude is not None
            and self.privacy_zone_radius_meters
        )

    def point_is_inside_privacy_zone(self, latitude, longitude):
        if latitude is None or longitude is None or not self.privacy_zone_is_configured():
            return False

        distance = _distance_meters(
            self.privacy_zone_latitude,
            self.privacy_zone_longitude,
            latitude,
            longitude,
        )
        return distance <= self.privacy_zone_radius_meters


class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    activity = db.Column(db.String(120), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    calories = db.Column(db.Integer, default=0)
    steps = db.Column(db.Integer, default=0)
    workout_date = db.Column(db.Date, default=date.today)
    start_latitude = db.Column(db.Float)
    start_longitude = db.Column(db.Float)
    end_latitude = db.Column(db.Float)
    end_longitude = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def public_start_location(self, user):
        if user.point_is_inside_privacy_zone(self.start_latitude, self.start_longitude):
            return "Hidden by privacy zone"
        return _format_coordinates(self.start_latitude, self.start_longitude)

    def public_end_location(self, user):
        if user.point_is_inside_privacy_zone(self.end_latitude, self.end_longitude):
            return "Hidden by privacy zone"
        return _format_coordinates(self.end_latitude, self.end_longitude)


class BodyMetric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    weight_kg_ciphertext = db.Column("weight_kg", db.Text, nullable=False)
    body_fat_percent_ciphertext = db.Column("body_fat_percent", db.Text)
    recorded_on = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def weight_kg(self):
        return decrypt_health_value(self.weight_kg_ciphertext)

    @weight_kg.setter
    def weight_kg(self, value):
        self.weight_kg_ciphertext = encrypt_health_value(value)

    @property
    def body_fat_percent(self):
        return decrypt_health_value(self.body_fat_percent_ciphertext)

    @body_fat_percent.setter
    def body_fat_percent(self, value):
        self.body_fat_percent_ciphertext = encrypt_health_value(value)


class WaterLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    water_ml = db.Column(db.Integer, nullable=False)
    recorded_on = db.Column(db.Date, default=date.today, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StepLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    steps = db.Column(db.Integer, nullable=False)
    recorded_on = db.Column(db.Date, default=date.today, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    goal_type = db.Column(db.String(40), nullable=False)
    target_value = db.Column(db.Float, nullable=False)
    start_value = db.Column(db.Float)
    unit = db.Column(db.String(40), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
