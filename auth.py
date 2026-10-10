from datetime import datetime
from email.message import EmailMessage
import smtplib

from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from forms import (
    LoginForm,
    ResendVerificationForm,
    SignupForm,
)
from models import BodyMetric, User, db


auth_bp = Blueprint("auth", __name__)


def get_email_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_verification_token(email):
    return get_email_serializer().dumps(
        email,
        salt=current_app.config["EMAIL_VERIFICATION_SALT"],
    )


def read_verification_token(token):
    try:
        email = get_email_serializer().loads(
            token,
            salt=current_app.config["EMAIL_VERIFICATION_SALT"],
            max_age=current_app.config["EMAIL_VERIFICATION_EXPIRATION_SECONDS"],
        )
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"

    return email, None


def send_verification_email(user):
    token = generate_verification_token(user.email)
    verification_url = url_for("auth.verify_email", token=token, _external=True)
    subject = "Verify your FitnessTrackerPro.com email"
    body = (
        f"Hi {user.name},\n\n"
        "Please verify your FitnessTrackerPro.com account by opening this link:\n"
        f"{verification_url}\n\n"
        "If you did not create this account, you can ignore this email.\n"
    )

    mail_server = current_app.config.get("MAIL_SERVER")
    if not mail_server:
        print(f"[DEV EMAIL] Verify {user.email}: {verification_url}")
        return "console"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
    message["To"] = user.email
    message.set_content(body)

    try:
        with smtplib.SMTP(mail_server, current_app.config["MAIL_PORT"]) as smtp:
            if current_app.config["MAIL_USE_TLS"]:
                smtp.starttls()
            if current_app.config.get("MAIL_USERNAME"):
                smtp.login(
                    current_app.config["MAIL_USERNAME"],
                    current_app.config["MAIL_PASSWORD"],
                )
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception("Failed to send verification email.")
        return "failed"

    return "email"


def flash_verification_delivery(delivery):
    if delivery == "failed":
        flash("We could not send the verification email. Try again later.", "error")
    elif delivery == "console":
        flash("Verification link generated. Check the server console.", "info")
    else:
        flash("Verification email sent. Check your inbox.", "info")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("fitness.dashboard"))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with that email already exists.", "error")
            return render_template("signup.html", form=form)

        user = User(
            name=form.name.data.strip(),
            email=email,
            country=(form.country.data or "").strip(),
            height_cm=form.height_cm.data,
            weight_goal_kg=form.weight_goal_kg.data,
            is_email_verified=not current_app.config["EMAIL_VERIFICATION_REQUIRED"],
        )
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.flush()
            initial_metric = BodyMetric(
                user_id=user.id,
                weight_kg=form.weight_kg.data,
                recorded_on=datetime.utcnow().date(),
            )
            db.session.add(initial_metric)
            user.update_current_bmi(form.weight_kg.data)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("An account with that email already exists.", "error")
            return render_template("signup.html", form=form)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Failed to create account.")
            flash("We could not create your account. Please try again.", "error")
            return render_template("signup.html", form=form)

        if current_app.config["EMAIL_VERIFICATION_REQUIRED"]:
            delivery = send_verification_email(user)
            flash("Account created. Verify your email before logging in.", "success")
            flash_verification_delivery(delivery)
        else:
            flash("Account created. You can log in now.", "success")
        return redirect(url_for("auth.login"))

    return render_template("signup.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("fitness.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(form.password.data):
            flash("Invalid email or password.", "error")
            return render_template("login.html", form=form)

        if current_app.config["EMAIL_VERIFICATION_REQUIRED"] and not user.is_email_verified:
            flash("Verify your email before logging in.", "error")
            return render_template("login.html", form=form)

        if user.expire_premium_if_needed():
            db.session.commit()

        login_user(user)
        flash("Logged in.", "success")
        return redirect(url_for("fitness.dashboard"))

    return render_template("login.html", form=form)


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    if current_user.is_authenticated:
        if current_user.is_email_verified:
            return redirect(url_for("fitness.dashboard"))
        logout_user()

    email, error = read_verification_token(token)
    if error == "expired":
        flash("Verification link expired. Request a new one.", "error")
        return redirect(url_for("auth.resend_verification"))
    if error == "invalid":
        flash("Invalid verification link.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Invalid verification link.", "error")
        return redirect(url_for("auth.login"))
    if user.is_email_verified:
        flash("Email already verified. You can log in.", "info")
        return redirect(url_for("auth.login"))

    user.is_email_verified = True
    db.session.commit()
    flash("Email verified. You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    if current_user.is_authenticated:
        return redirect(url_for("fitness.dashboard"))

    form = ResendVerificationForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and not user.is_email_verified:
            send_verification_email(user)
        flash(
            "If an unverified account exists for that email, a new verification email has been sent.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template("resend_verification.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("index"))
