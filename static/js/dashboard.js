document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#workout-form");

  if (!form) {
    return;
  }

  const activity = form.querySelector("[name='activity']");
  const minutes = form.querySelector("[name='duration_minutes']");
  const caloriesInput = form.querySelector("[name='calories']");
  const stepsInput = form.querySelector("[name='steps']");
  const preview = document.querySelector("#workout-preview");
  let sports = {};

  try {
    sports = JSON.parse(form.dataset.sports || "{}");
  } catch (error) {
    sports = {};
  }

  function cleanNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 ? number : fallback;
  }

  function updatePreview() {
    if (!activity || !minutes || !preview) {
      return;
    }

    const sport = sports[activity.value] || {};
    const duration = cleanNumber(minutes.value);
    const estimatedCalories = Math.round(cleanNumber(sport.calories_per_min) * duration);
    const estimatedSteps = Math.round(cleanNumber(sport.steps_per_min) * duration);
    const calories = caloriesInput && caloriesInput.value !== ""
      ? cleanNumber(caloriesInput.value)
      : estimatedCalories;
    const steps = stepsInput && stepsInput.value !== ""
      ? cleanNumber(stepsInput.value)
      : estimatedSteps;

    preview.innerHTML = `
      Estimated calories to save: ${Math.round(calories)}<br>
      Estimated steps to save: ${Math.round(steps)}
    `;
  }

  activity.addEventListener("input", updatePreview);
  minutes.addEventListener("input", updatePreview);
  if (caloriesInput) {
    caloriesInput.addEventListener("input", updatePreview);
  }
  if (stepsInput) {
    stepsInput.addEventListener("input", updatePreview);
  }

  updatePreview();
});
