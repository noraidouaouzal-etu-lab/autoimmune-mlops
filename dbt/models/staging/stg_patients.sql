-- stg_patients
-- 1:1 with the raw source, light cleaning only:
--   * standardize gender casing/whitespace
--   * normalize the free-text Diagnosis label into a fixed vocabulary
--     (mirrors `diagnosis_naming()` in code/DataPreparation.ipynb)
-- No columns are dropped here except the dlt load-metadata columns.
-- Column pruning (constants, correlated features) happens downstream in
-- the intermediate layer, so staging always reflects the full raw shape.

with source as (

    select * from {{ source('raw_medical_data', 'patients') }}

),

renamed as (

    select
        patient_id,
        age,
        lower(trim(gender))                as gender,
        trim(diagnosis)                    as diagnosis_raw,
        sickness_duration_months,
        rbc_count,
        hemoglobin,
        hematocrit,
        mcv,
        mch,
        mchc,
        rdw,
        reticulocyte_count,
        wbc_count,
        neutrophils,
        lymphocytes,
        monocytes,
        eosinophils,
        basophils,
        plt_count,
        mpv,
        ana,
        esbach,
        mbl_level,
        esr,
        c3,
        c4,
        crp,
        anti_ds_dna,
        anti_sm,
        rheumatoid_factor,
        acpa,
        anti_tpo,
        anti_tg,
        anti_sma,
        low_grade_fever,
        fatigue_or_chronic_tiredness,
        dizziness,
        weight_loss,
        rashes_and_skin_lesions,
        stiffness_in_the_joints,
        brittle_hair_or_hair_loss,
        dry_eyes_and_or_mouth,
        general_unwell_feeling,
        joint_pain,
        anti_enterocyte_antibodies,
        anti_lkm1,
        anti_rnp,
        asca,
        anti_ro_ssa,
        anti_c_bir1,
        anti_bp230,
        anti_t_tg,
        dgp,
        anti_bp180,
        asma,
        anti_if,
        ig_g_ig_e_receptor,
        anti_srp,
        anti_desmoglein_3,
        anti_la_ssb,
        anti_jo1,
        anca,
        anti_centromere,
        anti_desmoglein_1,
        ema,
        anti_type_vii_collagen,
        c1_inhibitor,
        anti_tif1,
        anti_epidermal_basement_membrane_ig_a,
        anti_omp_c,
        p_anca,
        anti_tissue_transglutaminase,
        anti_scl_70,
        anti_mi2,
        anti_parietal_cell,
        progesterone_antibodies

    from source

),

diagnosis_normalized as (

    select
        * exclude (diagnosis_raw),

        -- Mirrors diagnosis_naming() from DataPreparation.ipynb.
        -- Any label not in this fixed vocabulary falls into
        -- 'other_autoimmune_disease' rather than failing the model, so a
        -- new/unexpected diagnosis in future loads doesn't break the run;
        -- accepted_values test on this column will surface it instead.
        case
            when diagnosis_raw = 'Normal' then 'normal'
            when lower(diagnosis_raw) = 'systemic lupus erythematosus (sle)' then 'systemic_lupus_erythematosus'
            when lower(diagnosis_raw) = 'sjögren syndrome' then 'sjogren_syndrome'
            when lower(diagnosis_raw) = 'graves'' disease' then 'graves_disease'
            when lower(diagnosis_raw) = 'rheumatoid arthritis' then 'rheumatoid_arthritis'
            when lower(diagnosis_raw) = 'autoimmune orchitis' then 'autoimmune_orchitis'
            else 'other_autoimmune_disease'
        end as diagnosis

    from renamed

)

select * from diagnosis_normalized
