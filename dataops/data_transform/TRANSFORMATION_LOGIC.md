# Logique de transformation — de `DataPreparation.ipynb` aux modèles dbt

Ce document explique, étape par étape, comment chaque transformation du
notebook a été traduite en SQL dbt, et signale les écarts trouvés en
comparant le notebook (qui tourne sur le CSV brut) à ce qui est réellement
disponible dans la table `patients` de DuckDB (chargée par dlt).

## 0. Constat de départ : notebook (CSV) vs table réelle (DuckDB)

Le notebook lit `data/Complete_Updated_Autoimmune_Disorder_Dataset2.csv`
directement avec pandas. La table `raw_medical_data.patients` en base a été
chargée par le pipeline dlt (`dlt_pipeline/ingestion.py`) à partir du même
CSV, mais dlt **normalise tous les noms de colonnes en snake_case**. Deux
paires de colonnes du CSV entrent alors en collision :

| CSV (2 colonnes distinctes) | Colonne normalisée dlt | Conséquence |
|---|---|---|
| `Anti-dsDNA` / `Anti_dsDNA` | `anti_ds_dna` | seule la valeur de `Anti_dsDNA` est conservée |
| `Anti-Sm` / `Anti_Sm` | `anti_sm` | seule la valeur de `Anti_Sm` est conservée |

C'est un problème d'ingestion (hors périmètre de ce projet dbt), mais il
explique pourquoi mes modèles ont 2 colonnes de moins que ce que produit
littéralement le notebook. C'est documenté dans
`models/staging/_staging__sources.yml` pour que le Data Engineer et la
Data Quality Engineer en soient informés.

## 1. `stg_patients` — nettoyage de surface

Reproduit les cellules "Data Cleaning" du notebook :

- `Gender` → passé en minuscules et trim (`df['Gender'] = df['Gender'].str.lower()`).
- `Diagnosis` → normalisé vers un vocabulaire fixe via un `CASE WHEN` qui
  reproduit exactement la fonction `diagnosis_naming()` : `normal`,
  `systemic_lupus_erythematosus`, `sjogren_syndrome`, `graves_disease`,
  `rheumatoid_arthritis`, `autoimmune_orchitis`, ou `other_autoimmune_disease`
  en filet de sécurité pour tout libellé imprévu.
- `patient_id` est **conservé** à ce stade (contrairement au notebook qui le
  supprime tout de suite) : en dbt, on garde les clés source le plus
  longtemps possible pour pouvoir tracer/joindre les lignes en cas de
  contrôle qualité. Il n'est retiré qu'au tout dernier modèle
  (`ml_patients_dataset`), juste avant la livraison à l'équipe ML.

Aucune ligne ni colonne n'est supprimée dans ce modèle : c'est la couche
"miroir propre" de la source, utile pour tout audit de qualité.

## 2. `int_patients_cleaned` — décisions de nettoyage statistique

Reproduit les sections "Data Quality Checks", "skewed distributions" et
"Correlation" du notebook, **recalculées sur la vraie table** (et non
supposées identiques au notebook) :

- **Colonnes constantes** (une seule valeur unique sur 27 624 lignes) :
  `anti_t_tg`, `progesterone_antibodies` → supprimées.
- **Asymétrie (skew)** : seule `c4` a un skew > 1 (2.02). Transformation
  `log1p` (`ln(c4 + 1)`) qui ramène le skew à 0.07. La colonne garde le nom
  `c4` après transformation (comme dans le notebook) pour rester compatible
  avec les artefacts déjà entraînés (`scalers/rfe_features_scaler.pkl`,
  `models/*.pkl`) qui s'attendent à une colonne `C4`.
- **Corrélation** : toute paire de colonnes numériques/binaires avec
  |corrélation| > 0.85 → on retire la seconde colonne du couple. 15 colonnes
  supprimées : `anti_sm`, `anti_ro_ssa`, `anti_c_bir1`, `anti_bp180`,
  `asma`, `anti_la_ssb`, `anti_jo1`, `anca`, `anti_desmoglein_1`, `ema`,
  `anti_tif1`, `anti_omp_c`, `anti_scl_70`, `anti_mi2`, `anti_parietal_cell`.

Ces listes sont **codées en dur dans le SQL** plutôt que recalculées à
chaque `dbt run` : un modèle dbt doit rester déterministe et rejouable de
façon identique en CI/CD. Le profilage (nunique, skew, corrélation) est un
travail d'analyse exploratoire, pas une transformation de production. Si de
nouvelles données changent significativement ces statistiques, il faut
refaire le profilage (le script utilisé est décrit plus bas) et mettre à
jour les listes.

### Point important non reproduit du notebook : les doublons

Le notebook détecte des lignes et colonnes dupliquées mais **ne les
supprime jamais** — les cellules concernées (`df.duplicated()`,
`df.T.duplicated()`) ne font qu'imprimer un diagnostic, sans `.drop()` qui
suive. Pour rester fidèle au comportement réel du notebook (et au fichier
`CleanedDataset.csv` qu'il produit), `int_patients_cleaned` ne déduplique
pas non plus.

Ce que le profilage a trouvé sur la vraie table, à communiquer à la Data
Quality Engineer :
- **13 812 lignes strictement dupliquées sur 27 624** (exactement la
  moitié du volume total).
- **643 valeurs de `patient_id` répétées** — `patient_id` n'est donc **pas**
  une clé primaire fiable en l'état.
- **14 colonnes binaires strictement identiques** entre elles (valeurs
  identiques ligne à ligne), en plus des 15 colonnes retirées pour
  corrélation > 0.85 (la liste des 14 est un sous-ensemble/recoupe la
  liste corrélation, car des colonnes identiques ont par définition une
  corrélation de 1.0).

Recommandation : si l'équipe valide qu'il s'agit bien de doublons
d'ingestion (et non de vrais patients aux mesures identiques), ajouter une
étape de déduplication (`qualify row_number() over (partition by ... )`)
dans `int_patients_cleaned`, en coordination avec le Data Engineer et la
Data Quality Engineer plutôt que de le faire unilatéralement ici.

## 3. `patients_features` — feature engineering

Reproduit la section "Features extraction" du notebook : une feature
dérivée, `clinical_symptoms_count`, somme des 10 indicateurs binaires de
symptômes cliniques (fièvre légère, fatigue chronique, vertiges, perte de
poids, éruptions cutanées, raideur articulaire, cheveux cassants/perte de
cheveux, sécheresse oculaire/buccale, sensation générale de malaise,
douleurs articulaires).

## 4. `ml_patients_dataset` — dataset final pour le ML

Reproduit la section "Encoding Categorical Variables" du notebook :

- `patient_id` est retiré (ce n'est pas une feature).
- `gender` → encodage ordinal `female = 0`, `male = 1`.
- `diagnosis` → encodage ordinal `autoimmune_orchitis = 0`,
  `graves_disease = 1`, `normal = 2`, `rheumatoid_arthritis = 3`,
  `sjogren_syndrome = 4`, `systemic_lupus_erythematosus = 5`.

Ces valeurs sont codées en dur pour correspondre **exactement** aux
mappings déjà produits par `sklearn.LabelEncoder` et sauvegardés dans
`encoder/gender.json` et `encoder/diagnosis.json`. C'est volontaire : le
modèle et le scaler déjà entraînés par l'équipe ML dépendent de ce mapping
précis. Si les encodeurs sont un jour régénérés, il faut mettre à jour ce
modèle en conséquence (et vice-versa).

`other_autoimmune_disease` (le filet de sécurité de `stg_patients`) n'a pas
d'entrée dans l'encodeur actuel : il devient `NULL` dans ce modèle. Le test
`not_null` sur `diagnosis` fera donc échouer le build si ce cas apparaît,
plutôt que de laisser un `NULL` silencieux atteindre l'entraînement.

## Validation effectuée

`dbt build` a été exécuté contre une copie de
`duckdb/autoimmune_pipeline.duckdb` (27 624 lignes) : 4 modèles + 13 tests,
tout passe. Vérifications manuelles supplémentaires :
- nombre de lignes final = 27 624 (aucune perte/duplication introduite par
  les modèles eux-mêmes) ;
- skew de `c4` après transformation = 0.0685 (identique au calcul pandas
  sur la table réelle) ;
- 60 colonnes dans `ml_patients_dataset` (58 features numériques/binaires +
  `clinical_symptoms_count` + `gender` + `diagnosis`), cohérent avec
  `data/CleanedDataset.csv`.
