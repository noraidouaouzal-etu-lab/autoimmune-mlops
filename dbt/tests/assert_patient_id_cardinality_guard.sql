-- assert_patient_id_cardinality_guard
--
-- Context: patient_id is NOT a reliable primary key. Profiling of the
-- current table found only 643 distinct patient_id values across 27,624
-- rows (i.e. every patient_id repeats, on average ~43 times). This is
-- flagged for the team (see stg_patients.patient_id description) but not
-- resolved upstream yet.
--
-- Since we can't enforce uniqueness on patient_id today, this test instead
-- guards against SILENT drift: if a future data load changes the number of
-- distinct patient_id values by a large margin, that's a signal the source
-- data or the dlt ingestion changed in a way the team should know about
-- (new patient batch loaded, ID scheme changed, partial load, etc.),
-- rather than something we want passing unnoticed.
--
-- Fails (returns a row) if distinct patient_id count is outside
-- [500, 800] -- a generous band around the current baseline of 643.
-- Tighten this once the team confirms expected growth.

with counts as (

    select count(distinct patient_id) as distinct_patient_ids
    from {{ ref('stg_patients') }}

)

select *
from counts
where distinct_patient_ids < 500 or distinct_patient_ids > 800
