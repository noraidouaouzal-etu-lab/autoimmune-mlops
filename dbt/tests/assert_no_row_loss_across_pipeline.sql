-- assert_no_row_loss_across_pipeline
--
-- The pipeline is meant to be patient-grain and row-preserving end to end:
-- stg_patients -> int_patients_cleaned -> patients_features ->
-- ml_patients_dataset all drop/transform COLUMNS but must never drop or
-- duplicate ROWS. This test fails if any layer's row count diverges from
-- the raw source, which would indicate an unintended join fan-out, a
-- filter that crept into a model, or a silent row loss/duplication bug.

with counts as (

    select 'raw_medical_data.patients'   as layer, count(*) as row_count from {{ source('raw_medical_data', 'patients') }}
    union all
    select 'stg_patients'                as layer, count(*) as row_count from {{ ref('stg_patients') }}
    union all
    select 'int_patients_cleaned'        as layer, count(*) as row_count from {{ ref('int_patients_cleaned') }}
    union all
    select 'patients_features'           as layer, count(*) as row_count from {{ ref('patients_features') }}
    union all
    select 'ml_patients_dataset'         as layer, count(*) as row_count from {{ ref('ml_patients_dataset') }}

),

baseline as (

    select row_count as raw_count
    from counts
    where layer = 'raw_medical_data.patients'

)

select counts.*
from counts
cross join baseline
where counts.row_count != baseline.raw_count
