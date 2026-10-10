(() => {
  const form = document.querySelector("#nutrition-form");
  if (!form) return;

  const status = document.querySelector("#nutrition-status");
  const submitButton = document.querySelector("#nutrition-submit");
  const results = document.querySelector("#nutrition-results");
  const empty = document.querySelector("#nutrition-empty");
  const planSection = document.querySelector("#nutrition-plan");
  const planUnavailable = document.querySelector("#nutrition-plan-unavailable");

  const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

  function formatRange(range) {
    if (!range || typeof range.min !== "number" || typeof range.max !== "number") return "—";
    if (range.min === range.max) return numberFormat.format(range.min);
    return `${numberFormat.format(range.min)}–${numberFormat.format(range.max)}`;
  }

  function addText(parent, tagName, className, value) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    element.textContent = value;
    parent.append(element);
    return element;
  }

  function showCalories(calories) {
    document.querySelector("#nutrition-target").textContent =
      `${formatRange(calories.target)} kcal / day`;
    document.querySelector("#nutrition-maintenance").textContent =
      `${formatRange(calories.maintenance)} kcal / day`;
    document.querySelector("#nutrition-resting").textContent =
      `${formatRange(calories.resting)} kcal / day`;

    const goalNames = {
      maintain: "Maintenance",
      gradual_loss: "Gradual loss",
      gradual_gain: "Gradual gain",
    };
    document.querySelector("#nutrition-goal-badge").textContent = goalNames[calories.goal] || "Estimate";
    results.hidden = false;
    empty.hidden = true;
  }

  function renderPlan(plan) {
    document.querySelector("#nutrition-summary").textContent = plan.summary;
    const daysContainer = document.querySelector("#nutrition-days");
    const shoppingList = document.querySelector("#nutrition-shopping-list");
    daysContainer.replaceChildren();
    shoppingList.replaceChildren();

    for (const day of plan.days) {
      const card = document.createElement("article");
      card.className = "nutrition-day";
      addText(card, "h4", "nutrition-day-title", `Day ${day.day}`);
      addText(card, "p", "nutrition-day-calories", `Approx. ${numberFormat.format(day.estimated_kcal)} kcal`);

      const mealGrid = document.createElement("div");
      mealGrid.className = "nutrition-meal-grid";
      for (const meal of day.meals) {
        const mealCard = document.createElement("section");
        mealCard.className = "nutrition-meal";
        addText(mealCard, "p", "nutrition-meal-type", meal.meal_type);
        addText(mealCard, "h5", "nutrition-meal-name", meal.name);
        addText(mealCard, "p", "nutrition-meal-portion", meal.portion);
        addText(mealCard, "p", "nutrition-meal-calories", `About ${numberFormat.format(meal.estimated_kcal)} kcal`);
        const ingredients = document.createElement("ul");
        ingredients.className = "nutrition-ingredients";
        for (const ingredient of meal.ingredients) {
          addText(ingredients, "li", "", ingredient);
        }
        mealCard.append(ingredients);
        mealGrid.append(mealCard);
      }
      card.append(mealGrid);
      daysContainer.append(card);
    }

    for (const item of plan.shopping_list) {
      addText(shoppingList, "li", "", item);
    }

    planSection.hidden = false;
    planUnavailable.hidden = true;
  }

  function showPlanError(error) {
    planSection.hidden = true;
    planUnavailable.hidden = false;
    document.querySelector("#nutrition-plan-error").textContent = error;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    status.textContent = "";
    results.hidden = true;
    empty.hidden = true;
    planSection.hidden = true;
    planUnavailable.hidden = true;

    if (!form.reportValidity()) return;

    submitButton.disabled = true;
    submitButton.setAttribute("aria-busy", "true");
    submitButton.querySelector("span:first-child").textContent = "Building your week…";
    status.className = "nutrition-status is-loading";
    status.textContent = "Calculating your estimate and matching meals from the local data file.";

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const data = await response.json().catch(() => ({}));

      if (data.calories) showCalories(data.calories);
      if (!response.ok) {
        if (data.calories) {
          showPlanError(data.error || "The meal plan is unavailable right now.");
          status.className = "nutrition-status is-warning";
          status.textContent = "Your calorie estimate is ready; the meal plan could not be built.";
        } else {
          empty.hidden = false;
          throw new Error(data.error || "Please check the form and try again.");
        }
        return;
      }

      showCalories(data.calories);
      renderPlan(data.plan);
      status.className = "nutrition-status is-success";
      status.textContent = "Your calorie estimate and seven-day meal plan are ready.";
    } catch (error) {
      empty.hidden = false;
      status.className = "nutrition-status is-error";
      status.textContent = error.message || "Something went wrong. Please try again.";
    } finally {
      submitButton.disabled = false;
      submitButton.removeAttribute("aria-busy");
      submitButton.querySelector("span:first-child").textContent = "Build my 7-day plan";
    }
  });
})();
