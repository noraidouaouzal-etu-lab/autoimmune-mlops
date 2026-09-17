-- assert_no_unmapped_diagnosis_labels
--
-- stg_patients.diagnosis falls back to 'other_autoimmune_disease' for any
-- raw label outside the 6 known categories, so an unexpected new label
-- never breaks the staging build (see stg_patients.sql). But
-- ml_patients_dataset has no encoder entry for that bucket -> it becomes
-- NULL there, currently only caught by a generic not_null test at the very
-- end of the pipeline.
--
-- This test moves the alarm upstream, to where the problem actually
-- starts (stg_patients), so a new/unexpected diagnosis label is surfaced
-- with its raw value context instead of just "diagnosis is null" three
-- models downstream.

select
    diagnosis,
    count(*) as row_count
from {{ ref('stg_patients') }}
where diagnosis = 'other_autoimmune_disease'
group by diagnosis
