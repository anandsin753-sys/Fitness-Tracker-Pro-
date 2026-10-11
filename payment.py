"""Razorpay checkout and payment confirmation routes."""

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import secrets

from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from forms import PaymentVerificationForm, PremiumForm
from models import PaymentTransaction, User, db


payments_bp = Blueprint("payments", __name__)
PREMIUM_DAYS = 30
CURRENCY_EXPONENTS = {"JPY": 0}


def gateway_is_configured():
    key_id = current_app.config.get("RAZORPAY_KEY_ID", "")
    key_secret = current_app.config.get("RAZORPAY_KEY_SECRET", "")
    webhook_secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET", "")
    mode = current_app.config.get("RAZORPAY_MODE", "test")
    app_secret = current_app.config.get("SECRET_KEY", "")
    return (
        mode in {"test", "live"}
        and bool(key_id)
        and bool(key_secret)
        and bool(webhook_secret)
        and key_id.startswith(f"rzp_{mode}_")
        and len(app_secret) >= 32
        and app_secret != "change-this-secret-key"
    )


def _razorpay_client():
    if not gateway_is_configured():
        raise RuntimeError("Razorpay is not configured.")

    import razorpay

    return razorpay.Client(
        auth=(
            current_app.config["RAZORPAY_KEY_ID"],
            current_app.config["RAZORPAY_KEY_SECRET"],
        )
    )


def _price_for_user():
    country = current_app.config["COUNTRY_MAP"].get(
        (current_user.country or "").casefold(),
    )
    requested_currency = (country or {}).get("currency_code", "USD").upper()
    prices = current_app.config["PREMIUM_PRICE_BY_CURRENCY"]
    currency = requested_currency if requested_currency in prices else "USD"
    price = prices[currency]

    try:
        decimal_amount = Decimal(price["amount"])
        exponent = CURRENCY_EXPONENTS.get(currency, 2)
        minor_amount = decimal_amount * (10 ** exponent)
    except (InvalidOperation, TypeError, KeyError):
        raise ValueError("The configured Premium price is invalid.")

    if minor_amount != minor_amount.to_integral_value() or minor_amount <= 0:
        raise ValueError("The configured Premium price is invalid.")

    return int(minor_amount), currency


def _verify_payment_matches(transaction, payment):
    try:
        amount = int(payment.get("amount"))
    except (TypeError, ValueError):
        return False

    return (
        payment.get("status") == "captured"
        and payment.get("order_id") == transaction.order_id
        and amount == transaction.amount_subunits
        and str(payment.get("currency", "")).upper() == transaction.currency
        and bool(payment.get("id"))
    )


def _extend_premium(user, now):
    # Preserve any legacy, non-expiring Premium entitlement.
    if user.is_premium and user.premium_expires_at is None:
        return

    if user.is_premium and user.premium_expires_at and user.premium_expires_at > now:
        starts_from = user.premium_expires_at
    else:
        starts_from = now
        user.premium_started_at = now

    user.is_premium = True
    user.premium_expires_at = starts_from + timedelta(days=PREMIUM_DAYS)


def _fulfill_captured_payment(transaction, payment):
    if not _verify_payment_matches(transaction, payment):
        return False

    payment_id = str(payment["id"])
    if transaction.status == "paid":
        return transaction.payment_id == payment_id
    if transaction.status != "pending":
        return False

    now = datetime.utcnow()
    claimed = PaymentTransaction.query.filter_by(
        id=transaction.id,
        status="pending",
    ).update(
        {
            "status": "paid",
            "payment_id": payment_id,
            "paid_at": now,
        },
        synchronize_session=False,
    )
    if claimed != 1:
        db.session.rollback()
        latest = db.session.get(PaymentTransaction, transaction.id)
        return bool(
            latest
            and latest.status == "paid"
            and latest.payment_id == payment_id
        )

    user = db.session.get(User, transaction.user_id)
    if user is None:
        db.session.rollback()
        return False

    _extend_premium(user, now)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return False
    return True


@payments_bp.post("/payments/create-order")
@login_required
def create_order():
    form = PremiumForm()
    if not form.validate_on_submit():
        return jsonify(error="Refresh the page and try again."), 400
    if not gateway_is_configured():
        return jsonify(error="Online payments are not configured yet."), 503

    try:
        amount, currency = _price_for_user()
        receipt = f"ftp_{current_user.id}_{secrets.token_hex(8)}"
        order = _razorpay_client().order.create(
            data={
                "amount": amount,
                "currency": currency,
                "receipt": receipt,
                "notes": {"plan": "premium_30_days"},
            }
        )
        order_id = str(order.get("id", ""))
        if (
            not order_id
            or int(order.get("amount", -1)) != amount
            or str(order.get("currency", "")).upper() != currency
        ):
            raise ValueError("Razorpay returned an unexpected order.")

        transaction = PaymentTransaction(
            user_id=current_user.id,
            order_id=order_id,
            amount_subunits=amount,
            currency=currency,
            status="pending",
        )
        db.session.add(transaction)
        db.session.commit()
    except (ValueError, TypeError):
        db.session.rollback()
        current_app.logger.error("Could not create a valid Razorpay order.")
        return jsonify(error="We could not start checkout. Please try again."), 502
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.error("Could not save the Razorpay order.")
        return jsonify(error="We could not start checkout. Please try again."), 500
    except Exception:
        db.session.rollback()
        current_app.logger.error("Razorpay order creation failed.")
        return jsonify(error="We could not start checkout. Please try again."), 502

    return jsonify(
        key_id=current_app.config["RAZORPAY_KEY_ID"],
        order_id=order_id,
        amount=amount,
        currency=currency,
        name="FitnessTrackerPro.com",
        description="30 days of Premium access",
        prefill={"name": current_user.name, "email": current_user.email},
        redirect_url=url_for("premium.premium"),
        verify_url=url_for("payments.verify_payment"),
    ), 201


@payments_bp.post("/payments/verify")
@login_required
def verify_payment():
    form = PaymentVerificationForm()
    if not form.validate_on_submit():
        return jsonify(error="The payment confirmation was invalid."), 400
    if not gateway_is_configured():
        return jsonify(error="Online payments are not configured yet."), 503

    transaction = PaymentTransaction.query.filter_by(
        order_id=form.razorpay_order_id.data,
        user_id=current_user.id,
    ).first_or_404()

    try:
        client = _razorpay_client()
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": form.razorpay_order_id.data,
                "razorpay_payment_id": form.razorpay_payment_id.data,
                "razorpay_signature": form.razorpay_signature.data,
            }
        )
        payment = client.payment.fetch(form.razorpay_payment_id.data)
    except Exception:
        current_app.logger.warning("Razorpay payment verification failed.")
        return jsonify(error="We could not verify that payment. Contact support if charged."), 400

    if not _verify_payment_matches(transaction, payment):
        return jsonify(error="Payment is not captured yet. You can retry the confirmation."), 409
    if not _fulfill_captured_payment(transaction, payment):
        return jsonify(error="We could not activate Premium. Please contact support."), 409

    return jsonify(
        success=True,
        message="Payment confirmed. Premium is active for your account.",
        redirect_url=url_for("premium.premium"),
    )


@payments_bp.post("/payments/webhook")
def razorpay_webhook():
    webhook_secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return jsonify(error="Webhook is not configured."), 503

    body = request.get_data(cache=True)
    supplied_signature = request.headers.get("X-Razorpay-Signature", "")
    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, supplied_signature):
        return jsonify(error="Invalid webhook signature."), 400

    try:
        event = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify(error="Invalid webhook body."), 400

    if event.get("event") != "payment.captured":
        return jsonify(received=True)

    payment = (
        event.get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )
    order_id = payment.get("order_id")
    if not order_id:
        return jsonify(error="Payment event is missing its order."), 400

    transaction = PaymentTransaction.query.filter_by(order_id=order_id).first()
    if transaction is None:
        return jsonify(received=True)
    if not _verify_payment_matches(transaction, payment):
        current_app.logger.warning("Ignored an unmatched Razorpay payment event.")
        return jsonify(received=True)
    if not _fulfill_captured_payment(transaction, payment):
        current_app.logger.error("Could not apply a captured Razorpay payment.")
        return jsonify(error="Payment event could not be applied."), 500

    return jsonify(received=True)
