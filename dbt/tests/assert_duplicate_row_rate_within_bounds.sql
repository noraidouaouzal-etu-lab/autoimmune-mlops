-- assert_duplicate_row_rate_within_bounds
--
-- Context (see TRANSFORMATION_LOGIC.md, section "duplicats"):
-- stg_patients currently contains 13,812 fully-duplicated rows out of
-- 27,624 (~50%). This is a KNOWN, ACCEPTED issue upstream in the source
-- data / dlt ingestion -- the team decided not to deduplicate unilaterally
-- in dbt (see notebook fidelity discussion with Data Transformation
-- Engineer). This test does not fail the build over the duplicates
-- themselves; instead it fails if the duplicate rate drifts outside the
-- expected band, which would mean either:
--   a) the ingestion was fixed and this test (and the related contract
--      note) is now stale and should be relaxed, or
--   b) something upstream got worse and is producing far more duplicate
--      rows than expected.
--
-- Fails (returns rows) when the observed duplicate rate is outside
-- [40%, 60%]. Adjust the bounds if the team makes an explicit, documented
-- decision to change this behavior upstream.

with hashed as (

    select
        patient_id,
        md5(
            concat_ws(
                '|',
                cast(age as varchar),
                gender,
                diagnosis,
                cast(sickness_duration_months as varchar),
                cast(rbc_count as varchar),
                cast(hemoglobin as varchar),
                cast(hematocrit as varchar),
                cast(wbc_count as varchar),
                cast(plt_count as varchar),
                cast(esr as varchar),
                cast(crp as varchar)
            )
        ) as row_fingerprint
    from {{ ref('stg_patients') }}

),

summary as (

    select
        count(*) as total_rows,
        count(distinct row_fingerprint) as distinct_rows,
        1.0 - (count(distinct row_fingerprint)::double / nullif(count(*), 0)) as duplicate_rate

    from hashed

)

select *
from summary
<<<<<<< HEAD
where duplicate_rate != 0
=======
where duplicate_rate < 0.40 or duplicate_rate > 0.60
>>>>>>> 1acd299ed8cbde9ad3436c15fd256aeac33dd72b
