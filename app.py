from pathlib import Path
import json
from json import JSONDecodeError
from flask import Flask, flash, redirect, render_template, url_for
from flask_login import LoginManager, current_user
from sqlalchemy import inspect, text

from config import Config
from models import BodyMetric, User, db, is_encrypted_health_value


login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"


SECURITY_COLUMNS = {
    "user": {
        "premium_started_at": "premium_started_at DATETIME",
        "premium_expires_at": "premium_expires_at DATETIME",
        "height_cm": "height_cm FLOAT",
        "weight_goal_kg": "weight_goal_kg FLOAT",
        "current_bmi": "current_bmi FLOAT",
        "daily_water_goal_ml": "daily_water_goal_ml INTEGER NOT NULL DEFAULT 2000",
        "daily_step_goal": "daily_step_goal INTEGER NOT NULL DEFAULT 10000",
        "daily_workout_goal_minutes": (
            "daily_workout_goal_minutes INTEGER NOT NULL DEFAULT 30"
        ),
        "allow_third_party_tracking": (
            "allow_third_party_tracking BOOLEAN NOT NULL DEFAULT 0"
        ),
        "privacy_zones_enabled": "privacy_zones_enabled BOOLEAN NOT NULL DEFAULT 1",
        "privacy_zone_name": "privacy_zone_name VARCHAR(120) DEFAULT ''",
        "privacy_zone_latitude": "privacy_zone_latitude FLOAT",
        "privacy_zone_longitude": "privacy_zone_longitude FLOAT",
        "privacy_zone_radius_meters": (
            "privacy_zone_radius_meters INTEGER NOT NULL DEFAULT 250"
        ),
    },
    "workout": {
        "start_latitude": "start_latitude FLOAT",
        "start_longitude": "start_longitude FLOAT",
        "end_latitude": "end_latitude FLOAT",
        "end_longitude": "end_longitude FLOAT",
    },
}


FALLBACK_COUNTRIES = [
    {"name": "United States", "currency_code": "USD", "currency_symbol": "$"},
    {"name": "India", "currency_code": "INR", "currency_symbol": "&#8377;"},
    {"name": "United Kingdom", "currency_code": "GBP", "currency_symbol": "&pound;"},
    {"name": "Canada", "currency_code": "CAD", "currency_symbol": "CA$"},
    {"name": "Australia", "currency_code": "AUD", "currency_symbol": "A$"},
    {"name": "Germany", "currency_code": "EUR", "currency_symbol": "&euro;"},
    {"name": "France", "currency_code": "EUR", "currency_symbol": "&euro;"},
    {"name": "Italy", "currency_code": "EUR", "currency_symbol": "&euro;"},
    {"name": "Spain", "currency_code": "EUR", "currency_symbol": "&euro;"},
    {"name": "Japan", "currency_code": "JPY", "currency_symbol": "&yen;"},
    {"name": "Brazil", "currency_code": "BRL", "currency_symbol": "R$"},
    {"name": "Mexico", "currency_code": "MXN", "currency_symbol": "MX$"},
    {"name": "South Africa", "currency_code": "ZAR", "currency_symbol": "R"},
    {"name": "Singapore", "currency_code": "SGD", "currency_symbol": "S$"},
    {"name": "United Arab Emirates", "currency_code": "AED", "currency_symbol": "AED "},
]

PREMIUM_PRICE_BY_CURRENCY = {
    "USD": {"symbol": "$", "amount": "2.99", "suffix": ""},
    "INR": {"symbol": "&#8377;", "amount": "299", "suffix": " approx"},
    "GBP": {"symbol": "&pound;", "amount": "2.49", "suffix": " approx"},
    "EUR": {"symbol": "&euro;", "amount": "2.99", "suffix": " approx"},
    "CAD": {"symbol": "CA$", "amount": "3.99", "suffix": " approx"},
    "AUD": {"symbol": "A$", "amount": "4.49", "suffix": " approx"},
    "JPY": {"symbol": "&yen;", "amount": "450", "suffix": " approx"},
    "BRL": {"symbol": "R$", "amount": "14.90", "suffix": " approx"},
    "MXN": {"symbol": "MX$", "amount": "55", "suffix": " approx"},
    "ZAR": {"symbol": "R", "amount": "55", "suffix": " approx"},
    "SGD": {"symbol": "S$", "amount": "3.99", "suffix": " approx"},
    "AED": {"symbol": "AED ", "amount": "10.99", "suffix": " approx"},
}


def normalize_country_entry(entry):
    if isinstance(entry, str):
        name = entry.strip()
        if not name:
            return None
        return {
            "name": name,
            "currency_code": "USD",
            "currency_symbol": "$",
        }

    if not isinstance(entry, dict):
        return None

    name = (
        entry.get("name")
        or entry.get("country")
        or entry.get("country_name")
        or entry.get("common")
    )
    if not name or not str(name).strip():
        return None

    currency = entry.get("currency") or entry.get("currencies") or {}
    currency_code = entry.get("currency_code") or entry.get("currencyCode")
    currency_symbol = entry.get("currency_symbol") or entry.get("currencySymbol")

    if isinstance(currency, str):
        currency_code = currency_code or currency
    elif isinstance(currency, dict):
        currency_code = currency_code or currency.get("code")
        currency_symbol = currency_symbol or currency.get("symbol")
        if not currency_code and len(currency) == 1:
            currency_code = next(iter(currency.keys()))
            nested = currency.get(currency_code)
            if isinstance(nested, dict):
                currency_symbol = currency_symbol or nested.get("symbol")

    currency_code = (currency_code or "USD").strip().upper()
    return {
        "name": str(name).strip(),
        "currency_code": currency_code,
        "currency_symbol": currency_symbol or "$",
    }


def load_country_options(root_path):
    countries_path = Path(root_path) / "countries.json"
    try:
        raw_text = countries_path.read_text(encoding="utf-8").strip()
        raw_countries = json.loads(raw_text) if raw_text else []
    except (FileNotFoundError, JSONDecodeError, UnicodeDecodeError):
        raw_countries = []

    if isinstance(raw_countries, dict):
        raw_countries = raw_countries.get("countries", [])

    countries = []
    seen = set()
    if isinstance(raw_countries, list):
        for entry in raw_countries:
            normalized = normalize_country_entry(entry)
            if not normalized:
                continue
            key = normalized["name"].casefold()
            if key not in seen:
                countries.append(normalized)
                seen.add(key)

    return countries or FALLBACK_COUNTRIES


def currency_for_country(country_name, country_map):
    country = country_map.get((country_name or "").casefold())
    if not country:
        return {"currency_code": "USD", "currency_symbol": "$"}
    return {
        "currency_code": country["currency_code"],
        "currency_symbol": country["currency_symbol"],
    }


def premium_price_for_currency(currency_code):
    price = PREMIUM_PRICE_BY_CURRENCY.get((currency_code or "USD").upper())
    if price:
        return {
            "currency_code": currency_code.upper(),
            "display": f"{price['symbol']}{price['amount']}{price['suffix']}",
        }
    return {
        "currency_code": (currency_code or "USD").upper(),
        "display": "$2.99 USD",
    }


def ensure_security_schema():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())

    with db.engine.begin() as connection:
        for table_name, columns in SECURITY_COLUMNS.items():
            if table_name not in table_names:
                continue

            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, column_definition in columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        text(f'ALTER TABLE "{table_name}" ADD COLUMN {column_definition}')
                    )
        if "user" in table_names:
            connection.execute(text('UPDATE "user" SET is_premium = 0 WHERE is_premium IS NULL'))
            connection.execute(
                text('UPDATE "user" SET daily_water_goal_ml = 2000 WHERE daily_water_goal_ml IS NULL')
            )
            connection.execute(
                text('UPDATE "user" SET daily_step_goal = 10000 WHERE daily_step_goal IS NULL')
            )
            connection.execute(
                text(
                    'UPDATE "user" SET daily_workout_goal_minutes = 30 '
                    "WHERE daily_workout_goal_minutes IS NULL"
                )
            )

    if "body_metric" in table_names:
        migrated = False
        for metric in BodyMetric.query.all():
            if (
                metric.weight_kg_ciphertext
                and not is_encrypted_health_value(metric.weight_kg_ciphertext)
                and not str(metric.weight_kg_ciphertext).startswith("gAAAA")
            ):
                metric.weight_kg = metric.weight_kg
                migrated = True
            if (
                metric.body_fat_percent_ciphertext
                and not is_encrypted_health_value(metric.body_fat_percent_ciphertext)
                and not str(metric.body_fat_percent_ciphertext).startswith("gAAAA")
            ):
                metric.body_fat_percent = metric.body_fat_percent
                migrated = True
        if migrated:
            db.session.commit()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    countries = load_country_options(app.root_path)
    app.config["COUNTRIES"] = countries
    app.config["COUNTRY_MAP"] = {
        country["name"].casefold(): country for country in countries
    }
    app.config["PREMIUM_PRICE_BY_CURRENCY"] = PREMIUM_PRICE_BY_CURRENCY

    db.init_app(app)
    login_manager.init_app(app)

    from auth import auth_bp
    from ai import ai_bp
    from fitness import fitness_bp
    from payment import payments_bp
    from premium import premium_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(fitness_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(premium_bp)

    with app.app_context():
        db.create_all()
        ensure_security_schema()

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.after_request
    def add_security_headers(response):
        permissions_policy = "camera=(), microphone=(), geolocation=()"
        tracking_allowed = (
            current_user.is_authenticated
            and current_user.allow_third_party_tracking
        )
        if not tracking_allowed:
            permissions_policy = f"{permissions_policy}, browsing-topics=()"

        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", permissions_policy)
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response

    @app.before_request
    def expire_premium_accounts():
        if current_user.is_authenticated and current_user.expire_premium_if_needed():
            db.session.commit()
            flash(
                "Your Premium access has expired. Your fitness history is still saved.",
                "info",
            )

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("fitness.dashboard"))
        return render_template("index.html")

    @app.cli.command("init-db")
    def init_db_command():
        db.create_all()
        ensure_security_schema()
        print("Initialized the fitness database.")

    @app.context_processor
    def inject_common_data():
        user_country = current_user.country if current_user.is_authenticated else ""
        user_currency = currency_for_country(user_country, app.config["COUNTRY_MAP"])
        premium_price = premium_price_for_currency(user_currency["currency_code"])
        return {
            "countries": app.config["COUNTRIES"],
            "email_verification_required": app.config["EMAIL_VERIFICATION_REQUIRED"],
            "user_currency": user_currency,
            "premium_price": premium_price,
        }

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
