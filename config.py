import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    PUBLIC_BASE_URL = os.environ.get(
        "PUBLIC_BASE_URL",
        "https://fitnesstrackerpro.com",
    ).strip().rstrip("/")
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")
    HEALTH_DATA_ENCRYPTION_KEY = os.environ.get("HEALTH_DATA_ENCRYPTION_KEY")
    EMAIL_VERIFICATION_SALT = os.environ.get(
        "EMAIL_VERIFICATION_SALT",
        "email-verification",
    )
    EMAIL_VERIFICATION_EXPIRATION_SECONDS = int(
        os.environ.get("EMAIL_VERIFICATION_EXPIRATION_SECONDS", 86400)
    )
    EMAIL_VERIFICATION_REQUIRED = os.environ.get(
        "EMAIL_VERIFICATION_REQUIRED",
        "false",
    ).lower() in {"1", "true", "yes"}
    DAILY_WATER_TARGET_ML = int(os.environ.get("DAILY_WATER_TARGET_ML", 2000))
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        "noreply@fitness-app.local",
    )
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    RAZORPAY_MODE = os.environ.get("RAZORPAY_MODE", "test").strip().lower()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'fitness.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
