# dbt/ — Autoimmune MLOps · Data Transformation

Projet dbt du **Data Transformation Engineer** (Malak BOUSSETA) du projet
Autoimmune Disease Prediction. Ce dossier remplace la logique de nettoyage /
feature engineering du notebook `code/DataPreparation.ipynb` par des
modèles SQL versionnés, testés et exécutables en pipeline (dlt → DuckDB →
**dbt** → Data Quality Tests → ML).

## Installation

```bash
pip install dbt-core dbt-duckdb
cd dbt
dbt deps        # si des packages sont ajoutés plus tard
dbt debug        # vérifie la connexion à ../duckdb/autoimmune_pipeline.duckdb
dbt build        # run + test tous les modèles
```

`profiles.yml` est inclus dans le dossier `dbt/` (au lieu de `~/.dbt/`) pour
que le projet soit autonome. Pour l'utiliser tel quel :

```bash
export DBT_PROFILES_DIR=$(pwd)   # depuis dbt/
```

Le chemin `path: ../duckdb/autoimmune_pipeline.duckdb` suppose la structure
de dépôt du PDF projet :

```
autoimmune-mlops/
├── duckdb/autoimmune_pipeline.duckdb
└── dbt/            <- ce dossier
```

## Structure des modèles

```
models/
├── staging/
│   └── stg_patients.sql             -- nettoyage 1:1, aucune ligne/colonne supprimée
├── intermediate/
│   └── int_patients_cleaned.sql     -- colonnes constantes/corrélées supprimées, log(C4)
└── marts/
    ├── patients_features.sql        -- + feature engineering (Clinical_Symptoms_Count)
    └── ml_patients_dataset.sql      -- dataset final encodé, prêt pour le ML
```

Convention staging → intermediate → marts : chaque couche ne fait qu'une
chose, ce qui permet de tester et de déboguer indépendamment le nettoyage,
la sélection de features et l'encodage final.

## Validation

Les 4 modèles ont été exécutés (`dbt build`) contre une copie de la vraie
base `duckdb/autoimmune_pipeline.duckdb` (13 812 lignes) : 4/4 modèles et
13/13 tests passent. Les résultats numériques (skew de C4 après
transformation = 0.0685, nombre de colonnes finales = 60) correspondent à
ceux obtenus en rejouant la logique du notebook directement en pandas sur
la table réelle.

Voir `TRANSFORMATION_LOGIC.md` pour le détail de chaque étape et les écarts
constatés entre le notebook et les données réelles en base.
