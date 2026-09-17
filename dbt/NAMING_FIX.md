# Column naming fix (applied to ml_patients_dataset.sql)

## What changed
The final mart `ml_patients_dataset` now outputs the 23 model-input features
with **capitalized** names (Age, WBC_Count, Hemoglobin, ESR, ...) instead of
lowercase, to match:
- the trained model artifacts (models/*.pkl)
- the FastAPI schema (app/main.py -> PatientData)
- the monitoring drift detector (Member 7)

All other columns (antibodies, symptoms, clinical_symptoms_count, gender,
diagnosis) are unchanged. Only the final `renamed_for_model` CTE was added.

## Verified
- dbt run: OK (table rebuilt, 27,624 rows)
- All 23 features present with correct capitalized names
- The real trained model consumes the output and predicts successfully

## To re-apply after any future dbt change
Just `dbt run` again — the rename is part of the model, so it persists.
