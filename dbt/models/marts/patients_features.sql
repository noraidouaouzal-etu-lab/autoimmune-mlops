-- patients_features
-- Feature engineering layer: adds derived features on top of the cleaned
-- data. Currently one engineered feature, mirroring the notebook's
-- "Features extraction" section:
--
--   clinical_symptoms_count = count of clinical symptoms present, summed
--   across the 10 binary symptom flags (Low-grade fever, Fatigue or
--   chronic tiredness, Dizziness, Weight loss, Rashes and skin lesions,
--   Stiffness in the joints, Brittle hair or hair loss, Dry eyes and/or
--   mouth, General 'unwell' feeling, Joint pain).
--
-- This table is patient-grain, still human-readable (gender/diagnosis as
-- text), and useful for EDA / data-quality checks. The ML-ready, fully
-- numeric version lives in ml_patients_dataset.

with base as (

    select * from {{ ref('int_patients_cleaned') }}

),

feature_engineered as (

    select
        *,
        low_grade_fever
            + fatigue_or_chronic_tiredness
            + dizziness
            + weight_loss
            + rashes_and_skin_lesions
            + stiffness_in_the_joints
            + brittle_hair_or_hair_loss
            + dry_eyes_and_or_mouth
            + general_unwell_feeling
            + joint_pain as clinical_symptoms_count
    from base

)

select * from feature_engineered
