document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".password-row input").forEach((input) => {
    const form = input.closest("form");
    const createsPassword = form && form.querySelector("[name='confirm_password']");
    input.setAttribute("autocomplete", createsPassword ? "new-password" : "current-password");
  });
});
