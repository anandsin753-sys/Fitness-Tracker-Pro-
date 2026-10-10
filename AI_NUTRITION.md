# Offline Nutrition Planner

The planner is available to signed-in users at `/ai`. It works without an API key or an internet connection to an AI provider.

## How it works

- Resting energy estimate: Mifflin–St Jeor equation.
- Maintenance estimate: resting estimate multiplied by a broad activity factor.
- Goal estimate: maintenance, a 10% reduction for gradual loss, or a 5% increase for gradual gain.
- Seven-day meal suggestions: selected from `nutrition_data.json` according to the chosen dietary style and cuisine. The planner adjusts displayed portions to aim near the estimated daily target and builds a shopping starter list from the selected meals.

The local planner is a data-based recommendation engine, not a generative AI model. Meal calorie values and scaled portions are approximate; ingredient brands, preparation, and actual serving weights change the result. The bundled data is a starter set, not a verified clinical nutrition database. Use food labels or USDA FoodData Central for product-specific values.

## Setup

Install the project dependencies from the `fitness_app` directory:

```powershell
pip install -r requirements.txt
python app.py
```

No API key or external AI service is required. To add meal options, edit `nutrition_data.json` and provide a unique `id`, `meal_type`, `cuisine`, compatible `dietary_styles`, name, base portion, estimated calories per serving, and ingredient list.

## Scope and privacy

This is general adult wellness information, not medical nutrition therapy. The form excludes under-18 users and users who select pregnancy/breastfeeding, a medical diet, disordered-eating support, or a food allergy. The app blocks calculated targets below 1,000 kcal/day. People with those needs should work with a clinician or registered dietitian.

The planner does not store form answers or generated plans. Calorie calculations and meal selection happen inside the app; the data is not sent to an external AI service.

## References

- Mifflin MD et al., “A new predictive equation for resting energy expenditure in healthy individuals,” *The American Journal of Clinical Nutrition* (1990): https://pubmed.ncbi.nlm.nih.gov/2305711/
- NIDDK Body Weight Planner: https://www.niddk.nih.gov/health-information/weight-management/body-weight-planner
- USDA FoodData Central: https://fdc.nal.usda.gov/
