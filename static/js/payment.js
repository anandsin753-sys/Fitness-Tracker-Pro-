(() => {
  const form = document.querySelector("#premium-checkout-form");
  if (!form) return;

  const status = document.querySelector("#payment-status");
  const button = form.querySelector("button[type='submit']");

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.className = isError ? "flash error" : "muted";
  }

  async function readResponse(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Checkout could not be started. Please try again.");
    }
    return data;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!window.Razorpay) {
      setStatus("Secure checkout could not load. Refresh the page and try again.", true);
      return;
    }

    button.disabled = true;
    setStatus("Starting secure checkout…");

    try {
      const orderResponse = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const order = await readResponse(orderResponse);

      const checkout = new window.Razorpay({
        key: order.key_id,
        order_id: order.order_id,
        amount: order.amount,
        currency: order.currency,
        name: order.name,
        description: order.description,
        prefill: order.prefill,
        theme: { color: "#167a55" },
        handler: async (payment) => {
          setStatus("Confirming your payment securely…");
          const verification = new FormData(form);
          verification.append("razorpay_order_id", payment.razorpay_order_id);
          verification.append("razorpay_payment_id", payment.razorpay_payment_id);
          verification.append("razorpay_signature", payment.razorpay_signature);

          try {
            const response = await fetch(order.verify_url, {
              method: "POST",
              body: verification,
              headers: { Accept: "application/json" },
              credentials: "same-origin",
            });
            const result = await readResponse(response);
            setStatus(result.message || "Payment confirmed.");
            window.location.assign(result.redirect_url || order.redirect_url);
          } catch (error) {
            setStatus(error.message || "Payment confirmation failed. Contact support if charged.", true);
            button.disabled = false;
          }
        },
        modal: {
          ondismiss: () => {
            setStatus("Checkout closed. No Premium access was added.");
            button.disabled = false;
          },
        },
      });

      checkout.on("payment.failed", () => {
        setStatus("Payment did not complete. You can try again.", true);
        button.disabled = false;
      });
      checkout.open();
    } catch (error) {
      setStatus(error.message || "Checkout could not be started. Please try again.", true);
      button.disabled = false;
    }
  });
})();
