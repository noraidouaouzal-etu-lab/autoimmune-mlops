-- int_patients_cleaned
-- Applies the data-quality decisions made in the EDA/cleaning sections of
-- DataPreparation.ipynb ("Data Quality Checks", "skewed distributions",
-- "Correlation"), against the profile of the current `patients` table:
--
--   1. Drop constant columns (single unique value across all 27,624 rows):
--      anti_t_tg, progesterone_antibodies.
--      (notebook cell: `constant_cols = [c for c in df.columns if
--       df[c].nunique() == 1]`)
--
--   2. Log-transform C4 to correct right-skew (raw skew 2.02 -> 0.07 after
--      log1p). The transformed column keeps the name `c4` so downstream
--      consumers (existing scaler/model artifacts trained on
--      data/CleanedDataset.csv) see the same column name.
--      (notebook: `df['C4_log'] = np.log1p(df['C4'])`, then column swap)
--
--   3. Drop features with pairwise |correlation| > 0.85 against another
--      retained numeric/binary feature. This list was computed by
--      replicating the notebook's correlation step against the live
--      `patients` table (see PR description / transformation-logic doc for
--      the exact method) rather than at dbt run time, since dbt models
--      should stay deterministic and declarative. If the source data
--      changes meaningfully, re-run the profiling and update this list.
--      (notebook cells under "## Correlation", threshold = 0.85)
--
-- Note on duplicates: the notebook detects 13,812 fully duplicated rows
-- (of 27,624) and 14 duplicate columns, but never actually drops them
-- (`df[df.duplicated(keep=False)].sum()` and the `duplicates = df.T[...]`
-- check are diagnostic-only in the notebook, with no matching `.drop()`
-- call). This model preserves that behavior for fidelity with the
-- notebook's actual output (data/CleanedDataset.csv still contains the
-- duplicate rows/columns). See the transformation-logic doc for a
-- recommended follow-up if the team wants deduplication going forward.

with constant_columns_dropped as (

    select
        * exclude (anti_t_tg, progesterone_antibodies)
    from {{ ref('stg_patients') }}

),

c4_log_transformed as (

    select
        * exclude (c4),
        ln(c4 + 1) as c4
    from constant_columns_dropped

),

decorrelated as (

    select
        * exclude (
            anti_sm,
            anti_ro_ssa,
            anti_c_bir1,
            anti_bp180,
            asma,
            anti_la_ssb,
            anti_jo1,
            anca,
            anti_desmoglein_1,
            ema,
            anti_tif1,
            anti_omp_c,
            anti_scl_70,
            anti_mi2,
            anti_parietal_cell
        )
    from c4_log_transformed

)

select * from decorrelated
