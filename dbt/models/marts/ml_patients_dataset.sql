-- ml_patients_dataset
-- Final, fully-numeric table handed off to the ML team: one row per
-- patient, gender/diagnosis ordinally encoded, patient_id dropped (not a
-- feature). This is the dbt equivalent of data/CleanedDataset.csv.
--
-- IMPORTANT: the ordinal encodings below are hardcoded to match the
-- existing encoder/gender.json and encoder/diagnosis.json produced by
-- sklearn's LabelEncoder (alphabetical ordering) in the current notebook.
-- Keeping the same mapping here means the already-trained model and
-- scaler artifacts (models/*.pkl, scalers/*.pkl) stay compatible with
-- data produced by this dbt model. If the encoders are ever
-- retrained/regenerated, update the mappings below (and vice versa).
--
--   gender:    female -> 0, male -> 1
--   diagnosis: autoimmune_orchitis -> 0, graves_disease -> 1, normal -> 2,
--              rheumatoid_arthritis -> 3, sjogren_syndrome -> 4,
--              systemic_lupus_erythematosus -> 5
--
-- 'other_autoimmune_disease' (the staging fallback bucket) has no encoder
-- entry today; it is mapped to NULL here and should be caught by the
-- not_null test on ml_patients_dataset.diagnosis before it ever reaches
-- training data.

with features as (

    select * from {{ ref('patients_features') }}

),

encoded as (

    select
        * exclude (patient_id, gender, diagnosis),

        case gender
            when 'female' then 0
            when 'male'   then 1
        end as gender,

        case diagnosis
            when 'autoimmune_orchitis'         then 0
            when 'graves_disease'              then 1
            when 'normal'                      then 2
            when 'rheumatoid_arthritis'         then 3
            when 'sjogren_syndrome'             then 4
            when 'systemic_lupus_erythematosus' then 5
        end as diagnosis

    from features

),

-- Rename the 23 model-input features to the capitalized names expected by
-- the trained model artifacts (models/*.pkl), the FastAPI schema
-- (app/main.py PatientData), and the monitoring drift detector. All other
-- columns (antibodies, symptoms, engineered features, gender, diagnosis)
-- pass through unchanged.
renamed_for_model as (

    select
        age                        as "Age",
        sickness_duration_months   as "Sickness_Duration_Months",
        rbc_count                  as "RBC_Count",
        hemoglobin                 as "Hemoglobin",
        hematocrit                 as "Hematocrit",
        mcv                        as "MCV",
        mch                        as "MCH",
        mchc                       as "MCHC",
        rdw                        as "RDW",
        reticulocyte_count         as "Reticulocyte_Count",
        wbc_count                  as "WBC_Count",
        neutrophils                as "Neutrophils",
        lymphocytes                as "Lymphocytes",
        monocytes                  as "Monocytes",
        eosinophils                as "Eosinophils",
        basophils                  as "Basophils",
        plt_count                  as "PLT_Count",
        mpv                        as "MPV",
        esbach                     as "Esbach",
        mbl_level                  as "MBL_Level",
        esr                        as "ESR",
        c3                         as "C3",
        c4                         as "C4",

        -- everything else (antibodies, symptoms, engineered, target) unchanged
        * exclude (
            age, sickness_duration_months, rbc_count, hemoglobin, hematocrit,
            mcv, mch, mchc, rdw, reticulocyte_count, wbc_count, neutrophils,
            lymphocytes, monocytes, eosinophils, basophils, plt_count, mpv,
            esbach, mbl_level, esr, c3, c4
        )

    from encoded

)

select * from renamed_for_model
