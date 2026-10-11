# Razorpay payments

FitnessTrackerPro.com uses Razorpay Checkout for a one-time purchase of 30 days
of Premium. The server chooses the price from the existing country/currency
price table, creates each Razorpay order, verifies the checkout signature, and
checks that the provider reports a captured payment before granting Premium.
The app does not collect or store card details.

## Configure test checkout

1. Create and activate a Razorpay account, then obtain **test** API credentials.
2. Install the project dependencies with `pip install -r requirements.txt`.
3. Set these variables in the server environment (do not commit them or put them
   in browser JavaScript):

   - `RAZORPAY_MODE=test`
   - `RAZORPAY_KEY_ID=rzp_test_...`
   - `RAZORPAY_KEY_SECRET=...`
   - `RAZORPAY_WEBHOOK_SECRET=...`
   - `SECRET_KEY=...` (a separate, randomly generated value with at least 32 characters)

4. In the Razorpay dashboard, add a webhook pointing at
   `https://YOUR_HOST/payments/webhook`, subscribe to `payment.captured`, and
   use the same webhook secret in `RAZORPAY_WEBHOOK_SECRET`.
5. Start the Flask app and complete a Checkout using Razorpay's test payment
   details. Test payments do not transfer real money.

Checkout stays unavailable until a mode-matching key ID and secret, webhook
secret, and strong Flask `SECRET_KEY` are set.
The webhook secret is needed for webhook delivery, including fulfillment if a
customer closes the checkout window after paying.

## Production and domain

For live charges, complete Razorpay's account onboarding and payment-method
activation, set `RAZORPAY_MODE=live`, and use only live API credentials. Configure
HTTPS and the production webhook URL in the dashboard. International currencies
also require Razorpay to enable international payments for the merchant
account. Keep `SECRET_KEY` configured as a separate strong server-side secret.

This repository contains the site branding and payment integration; it does not
register `fitnesstrackerpro.com`, create hosting, or configure DNS. Replace
`YOUR_HOST` with the actual deployed host until that domain is registered and
pointed at the deployment.
