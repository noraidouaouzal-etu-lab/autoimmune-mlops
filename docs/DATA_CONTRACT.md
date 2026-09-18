# Data Contract — Pipeline `autoimmune_mlops`

**Périmètre :** table source `raw_medical_data.patients` (ingérée par dlt) jusqu'à la table finale `ml_patients_dataset` (consommée par l'équipe ML), en passant par `stg_patients` → `int_patients_cleaned` → `patients_features`.
**Basé sur :** profilage réel de `Complete_Updated_Autoimmune_Disorder_Dataset2.csv` (13 812 lignes, 79 colonnes brutes) + les règles déjà codées dans `stg_patients.sql`, `int_patients_cleaned.sql`, `patients_features.sql`, `ml_patients_dataset.sql`, `_staging__models.yml`, `_marts__models.yml`, `_staging__sources.yml` et les tests custom (`assert_*.sql`).
**Propriétaire :** Data/DataOps team — voir `user.yml` (id `8c01aa0c-8df5-44a3-b61b-6d155b6a6292`).

---

## 1. Objectif de ce contrat

Un data contract fige, couche par couche, **ce que chaque colonne doit être** : son type, sa nullabilité, ses valeurs/plage acceptées, sa provenance et la transformation qui l'a produite — pour que :
- toute rupture de contrat (nouveau type, nouvelle valeur, dérive de plage) soit détectée par `dbt test` **avant** d'atteindre l'équipe ML ;
- le renommage/encodage attendu par les artefacts déjà entraînés (`models/*.pkl`, `scalers/*.pkl`, `encoder/*.json`) reste stable ;
- les décisions de nettoyage prises dans le notebook (`DataPreparation.ipynb`) restent traçables et reproductibles en SQL déclaratif.

Le contrat formel, **appliqué techniquement** via `config: {contract: {enforced: true}}`, ne porte aujourd'hui que sur `ml_patients_dataset` (voir `_marts__models.yml`). Les sections ci-dessous couvrent aussi les couches amont, qui sont testées mais pas contractuellement figées (```materialized: view```), pour qu'une dérive y soit détectée avant de se propager.

---

## 2. Vue d'ensemble du pipeline

| Couche | Modèle dbt | Matérialisation | Grain | Rôle |
|---|---|---|---|---|
| Source | `raw_medical_data.patients` | table (dlt) | 1 ligne = 1 enregistrement labo | Donnée brute, non fiable telle quelle |
| Staging | `stg_patients` | view | idem source | Casing/whitespace, normalisation `diagnosis`, **aucune colonne supprimée** |
| Intermediate | `int_patients_cleaned` | view | idem source | Suppression colonnes constantes, log-transform C4, suppression colonnes corrélées |
| Marts (features) | `patients_features` | table | idem source | Ajout `clinical_symptoms_count`, encore lisible (texte) |
| Marts (ML) | `ml_patients_dataset` | table, **contrat enforced** | idem source | 100% numérique, renommée/encodée pour les artefacts ML |

⚠️ **Point structurant du contrat : le grain n'est PAS "1 ligne = 1 patient".** `patient_id` n'est pas une clé unique (voir §3.2). Le contrat de non-perte de lignes (`assert_no_row_loss_across_pipeline`) porte sur le **row count brut**, pas sur un patient distinct.

---

## 3. Problèmes de qualité connus et comment le contrat les traite

### 3.1 Collision de noms de colonnes à l'ingestion (dlt)
La source CSV contient à la fois `Anti-dsDNA` / `Anti_dsDNA` et `Anti-Sm` / `Anti_Sm`. dlt normalise les deux en snake_case identique au chargement → une des deux valeurs est silencieusement perdue. **Convention retenue et figée par ce contrat :** les colonnes issues de la variante *underscore* (`Anti_dsDNA`, `Anti_Sm`) sont celles qui survivent et alimentent `anti_ds_dna` / `anti_sm` en aval. Documenté dans `_staging__sources.yml`, hors périmètre de correction dbt (problème d'ingestion).

### 3.2 `patient_id` n'est pas une clé primaire
643 valeurs distinctes pour 13 812 lignes (donc **≈50% de lignes strictement dupliquées**, confirmé par profilage : 13 169 doublons de `patient_id`). Le contrat n'impose **pas** d'unicité sur `patient_id` — seulement `not_null`. Deux tests custom encadrent cette situation plutôt que de la "corriger" unilatéralement :
- `assert_duplicate_row_rate_within_bounds` (severity `warn`) : échoue si le taux de duplication sort de `[40%, 60%]`.
- `assert_patient_id_cardinality_guard` : échoue si le nombre de `patient_id` distincts sort de `[500, 800]`.

### 3.3 Labels de diagnostic hors vocabulaire fixe
`stg_patients.diagnosis` retombe sur `'other_autoimmune_disease'` pour tout libellé brut non reconnu (au lieu de faire planter le run). Ce bucket n'a **pas** d'entrée dans les encodeurs ML → il devient `NULL` dans `ml_patients_dataset.diagnosis`. Contrat : `assert_no_unmapped_diagnosis_labels` déclenche l'alerte **en amont** (à `stg_patients`), avec le libellé brut en contexte, plutôt que de laisser `not_null` échouer 3 modèles plus loin sans contexte.

### 3.4 Colonnes constantes / redondantes (silencieuses mais réelles)
`anti_t_tg` et `progesterone_antibodies` sont constantes à `0` sur les 13 812 lignes (confirmé par profilage) → aucune valeur informative, supprimées dès `int_patients_cleaned`.

---

## 4. Contrat détaillé par couche

### 4.1 Source — `raw_medical_data.patients`

| Colonne | Type brut | Nullable | Contrat |
|---|---|---|---|
| `patient_id` | int | non | Identifiant, **pas garanti unique** (voir §3.2) |
| `gender` | string | non | Casse mixte (`"Male"`, `"Female"`) — normalisé en aval |
| `diagnosis` | string | non | Texte libre, ex. `"Systemic lupus erythematosus (SLE)"`, `"Sjögren syndrome"`, `"Graves' disease"` — normalisé en aval |
| *(76 autres colonnes)* | int/float | non | Voir §4.2 pour le détail (mêmes colonnes, noms bruts) |

### 4.2 `stg_patients` — nettoyage léger, **aucune colonne supprimée**

Règles appliquées : `gender` → `lower(trim(...))` ; `diagnosis` → normalisé vers un vocabulaire fixe de 7 valeurs (voir table `accepted_values` ci-dessous). Toutes les autres colonnes passent 1:1.

**Colonnes catégorielles**

| Colonne | Type | Nullable | Valeurs acceptées |
|---|---|---|---|
| `patient_id` | BIGINT | non | — (pas de contrainte d'unicité, voir §3.2) |
| `gender` | VARCHAR | non | `{'female', 'male'}` |
| `diagnosis` | VARCHAR | non | `{'normal', 'systemic_lupus_erythematosus', 'sjogren_syndrome', 'graves_disease', 'rheumatoid_arthritis', 'autoimmune_orchitis', 'other_autoimmune_disease'}` |

### Variables cliniques quantitatives

| Colonne (staging, snake_case) | Colonne source (CSV brut) | Type | Nullable | Plage / valeurs observées | Description métier |
|---|---|---|---|---|---|
| `age` | `Age` | BIGINT | non (`not_null` recommandé) | [20 – 79] | Âge du patient (années) |
| `sickness_duration_months` | `Sickness_Duration_Months` | BIGINT | non (`not_null` recommandé) | [1 – 119] | Durée des symptômes avant diagnostic (mois) |
| `rbc_count` | `RBC_Count` | DOUBLE | non (`not_null` recommandé) | [3.510 – 6.100] | Numération des globules rouges (10^6/µL) |
| `hemoglobin` | `Hemoglobin` | DOUBLE | non (`not_null` recommandé) | [10.000 – 17.196] | Hémoglobine (g/dL) |
| `hematocrit` | `Hematocrit` | DOUBLE | non (`not_null` recommandé) | [36.000 – 50.282] | Hématocrite (%) |
| `mcv` | `MCV` | DOUBLE | non (`not_null` recommandé) | [75.090 – 104.970] | Volume globulaire moyen (fL) |
| `mch` | `MCH` | DOUBLE | non (`not_null` recommandé) | [26.000 – 32.000] | Teneur corpusculaire moyenne en hémoglobine (pg) |
| `mchc` | `MCHC` | DOUBLE | non (`not_null` recommandé) | [31.000 – 35.999] | Concentration corpusculaire moyenne en hémoglobine (g/dL) |
| `rdw` | `RDW` | DOUBLE | non (`not_null` recommandé) | [11.501 – 16.000] | Indice de distribution des globules rouges (%) |
| `reticulocyte_count` | `Reticulocyte_Count` | DOUBLE | non (`not_null` recommandé) | [0.500 – 3.000] | Numération des réticulocytes (%) |
| `wbc_count` | `WBC_Count` | DOUBLE | non (`not_null` recommandé) | [4004.000 – 11992.000] | Numération des globules blancs (/µL) |
| `neutrophils` | `Neutrophils` | DOUBLE | non (`not_null` recommandé) | [30.070 – 75.000] | Neutrophiles (%) |
| `lymphocytes` | `Lymphocytes` | DOUBLE | non (`not_null` recommandé) | [15.260 – 44.970] | Lymphocytes (%) |
| `monocytes` | `Monocytes` | DOUBLE | non (`not_null` recommandé) | [2.001 – 9.980] | Monocytes (%) |
| `eosinophils` | `Eosinophils` | DOUBLE | non (`not_null` recommandé) | [1.001 – 4.990] | Éosinophiles (%) |
| `basophils` | `Basophils` | DOUBLE | non (`not_null` recommandé) | [0.500 – 1.490] | Basophiles (%) |
| `plt_count` | `PLT_Count` | DOUBLE | non (`not_null` recommandé) | [100073.000 – 499918.000] | Numération plaquettaire (/µL) |
| `mpv` | `MPV` | DOUBLE | non (`not_null` recommandé) | [7.010 – 11.980] | Volume plaquettaire moyen (fL) |
| `esbach` | `Esbach` | DOUBLE | non (`not_null` recommandé) | [0.002 – 499.999] | Protéinurie des 24h (méthode d'Esbach, mg/L) |
| `mbl_level` | `MBL_Level` | DOUBLE | non (`not_null` recommandé) | [0.500 – 2.000] | Taux de Mannose-Binding Lectin (µg/mL) |
| `esr` | `ESR` | DOUBLE | non (`not_null` recommandé) | [0.016 – 59.983] | Vitesse de sédimentation (mm/h) |
| `c3` | `C3` | DOUBLE | non (`not_null` recommandé) | [0.025 – 179.996] | Complément C3 (mg/dL) |
| `c4` | `C4` | DOUBLE | non (`not_null` recommandé) | [0.002 – 39.997] | Complément C4 (mg/dL) — transformé en aval (log1p) dans int_patients_cleaned |
| `crp` | `CRP` | DOUBLE | non (`not_null` recommandé) | [0.001 – 49.986] | Protéine C-réactive (mg/L) |

### Marqueurs immunologiques binaires (0/1)

| Colonne (staging, snake_case) | Colonne source (CSV brut) | Type | Nullable | Plage / valeurs observées | Description métier |
|---|---|---|---|---|---|
| `ana` | `ANA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anticorps antinucléaires (AAN) |
| `anti_ds_dna` | `Anti_dsDNA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-ADN double brin (source: colonne "Anti_dsDNA" retenue ; collision avec "Anti-dsDNA" — voir §3) |
| `anti_sm` | `Anti_Sm` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-Sm (source: colonne "Anti_Sm" retenue ; collision avec "Anti-Sm" — voir §3) |
| `rheumatoid_factor` | `Rheumatoid factor` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Facteur rhumatoïde |
| `acpa` | `ACPA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anticorps anti-peptides citrullinés |
| `anti_tpo` | `Anti-TPO` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-thyroperoxydase |
| `anti_tg` | `Anti-Tg` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-thyroglobuline |
| `anti_sma` | `Anti-SMA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-muscle lisse (variante "Anti-SMA") |
| `anti_enterocyte_antibodies` | `Anti_enterocyte_antibodies` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anticorps anti-entérocytes |
| `anti_lkm1` | `anti_LKM1` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-LKM1 |
| `anti_rnp` | `Anti_RNP` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-RNP |
| `asca` | `ASCA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-Saccharomyces cerevisiae |
| `anti_ro_ssa` | `Anti_Ro_SSA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-Ro/SSA — DROPPÉE en aval (corrélation > 0.85, voir §4.3) |
| `anti_c_bir1` | `Anti_CBir1` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-CBir1 — DROPPÉE en aval (corrélation > 0.85, voir §4.3) |
| `anti_bp230` | `Anti_BP230` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-BP230 |
| `anti_t_tg` | `Anti_tTG` | BOOLEAN (0/1) | non (`not_null` recommandé) | CONSTANTE = 0 | Anti-tTG — colonne constante (0 partout) — DROPPÉE en aval (§4.3) |
| `dgp` | `DGP` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Peptides de gliadine désamidés |
| `anti_bp180` | `Anti_BP180` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-BP180 — DROPPÉE en aval (corrélation > 0.85, voir §4.3) |
| `asma` | `ASMA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | ASMA (variante distincte de anti_sma) — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `anti_if` | `Anti_IF` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-facteur intrinsèque |
| `ig_g_ig_e_receptor` | `IgG_IgE_receptor` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-récepteur IgE (auto-immunité de l'urticaire chronique) |
| `anti_srp` | `Anti_SRP` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-SRP |
| `anti_desmoglein_3` | `Anti_desmoglein_3` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-desmogléine 3 |
| `anti_la_ssb` | `Anti_La_SSB` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-La/SSB — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `anti_jo1` | `Anti_Jo1` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-Jo1 — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `anca` | `ANCA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | ANCA — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `anti_centromere` | `anti_centromere` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-centromère |
| `anti_desmoglein_1` | `Anti_desmoglein_1` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-desmogléine 1 — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `ema` | `EMA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-endomysium — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `anti_type_vii_collagen` | `Anti_type_VII_collagen` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-collagène type VII |
| `c1_inhibitor` | `C1_inhibitor` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | C1-inhibiteur |
| `anti_tif1` | `Anti_TIF1` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-TIF1 — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `anti_epidermal_basement_membrane_ig_a` | `Anti_epidermal_basement_membrane_IgA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-membrane basale épidermique IgA |
| `anti_omp_c` | `Anti_OmpC` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-OmpC — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `p_anca` | `pANCA` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | p-ANCA |
| `anti_tissue_transglutaminase` | `Anti_tissue_transglutaminase` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-transglutaminase tissulaire |
| `anti_scl_70` | `anti_Scl_70` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-Scl-70 — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `anti_mi2` | `Anti_Mi2` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-Mi2 — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `anti_parietal_cell` | `Anti_parietal_cell` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Anti-cellules pariétales — DROPPÉE en aval (corrélation > 0.85, §4.3) |
| `progesterone_antibodies` | `Progesterone_antibodies` | BOOLEAN (0/1) | non (`not_null` recommandé) | CONSTANTE = 0 | Anti-progestérone — colonne constante (0 partout) — DROPPÉE en aval (§4.3) |

### Symptômes cliniques binaires (0/1)

| Colonne (staging, snake_case) | Colonne source (CSV brut) | Type | Nullable | Plage / valeurs observées | Description métier |
|---|---|---|---|---|---|
| `low_grade_fever` | `Low-grade fever` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Fièvre légère |
| `fatigue_or_chronic_tiredness` | `Fatigue or chronic tiredness` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Fatigue chronique |
| `dizziness` | `Dizziness` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Vertiges |
| `weight_loss` | `Weight loss` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Perte de poids |
| `rashes_and_skin_lesions` | `Rashes and skin lesions` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Éruptions / lésions cutanées |
| `stiffness_in_the_joints` | `Stiffness in the joints` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Raideur articulaire |
| `brittle_hair_or_hair_loss` | `Brittle hair or hair loss` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Cheveux cassants / perte de cheveux |
| `dry_eyes_and_or_mouth` | `Dry eyes and/or mouth` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Sécheresse oculaire et/ou buccale |
| `general_unwell_feeling` | `General 'unwell' feeling` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Sensation générale de malaise |
| `joint_pain` | `Joint pain` | BOOLEAN (0/1) | non (`not_null` recommandé) | {0, 1} | Douleurs articulaires |

### 4.3 `int_patients_cleaned` — colonnes supprimées et transformées

Hérite intégralement du contrat `stg_patients` **moins** :

**a) Colonnes constantes supprimées (valeur unique sur 27 624 lignes du notebook / confirmé constantes ici) :**
`anti_t_tg`, `progesterone_antibodies`

**b) `c4` transformé** : `c4 → ln(c4 + 1)`, le nom de colonne est conservé (les consommateurs en aval — scaler/modèle déjà entraînés — attendent le nom `c4`). Skew corrigé de 2.02 → 0.07. **Contrat : `c4` en sortie de cette couche n'est plus dans la plage brute `[0.002, 39.997]` mais dans sa version log1p — ne pas re-tester la plage brute en aval de ce modèle.**

**c) Colonnes supprimées pour corrélation |r| > 0.85 avec une autre variable conservée** (liste figée, calculée hors dbt — à revalider si la source évolue significativement) :
`anti_sm`, `anti_ro_ssa`, `anti_c_bir1`, `anti_bp180`, `asma`, `anti_la_ssb`, `anti_jo1`, `anca`, `anti_desmoglein_1`, `ema`, `anti_tif1`, `anti_omp_c`, `anti_scl_70`, `anti_mi2`, `anti_parietal_cell`

→ **15 colonnes supprimées au total** entre `stg_patients` (77 colonnes hors clé/catégorielles) et `int_patients_cleaned`.

**d) Duplication non résolue à ce stade** (voir §3.2) : ~50% de lignes strictement dupliquées, volontairement conservées par fidélité avec le notebook source.

### 4.4 `patients_features` — ajout d'une feature dérivée

Hérite du contrat `int_patients_cleaned` **plus** :

| Colonne | Type | Nullable | Contrat |
|---|---|---|---|
| `clinical_symptoms_count` | BIGINT | non | Somme des 10 flags symptômes binaires ci-dessus → **plage `[0, 10]`** |

### 4.5 `ml_patients_dataset` — contrat **enforced** (source de vérité pour le ML)

Table finale, 100% numérique. `patient_id` est **supprimé** (n'est pas une feature). `gender` et `diagnosis` sont **ordinalement encodés** pour rester compatibles avec `encoder/gender.json` / `encoder/diagnosis.json` (encodage `sklearn.LabelEncoder`, ordre alphabétique) :

| Colonne source | → | Colonne finale | Encodage |
|---|---|---|---|
| `gender` | → | `gender` | `female → 0`, `male → 1` |
| `diagnosis` | → | `diagnosis` | `autoimmune_orchitis → 0`, `graves_disease → 1`, `normal → 2`, `rheumatoid_arthritis → 3`, `sjogren_syndrome → 4`, `systemic_lupus_erythematosus → 5` |

⚠️ **`other_autoimmune_disease` n'a pas d'entrée d'encodeur → devient `NULL`.** C'est *volontaire* : le test `not_null` sur `diagnosis` dans ce modèle doit alors faire échouer le build plutôt que de laisser une valeur non mappée entrer dans l'entraînement. Voir §3.3 pour l'alerte amont.

23 colonnes numériques sont en plus **renommées en capitalisé** pour matcher le schéma FastAPI (`app/main.py PatientData`) et le détecteur de drift : `Age`, `Sickness_Duration_Months`, `RBC_Count`, `Hemoglobin`, `Hematocrit`, `MCV`, `MCH`, `MCHC`, `RDW`, `Reticulocyte_Count`, `WBC_Count`, `Neutrophils`, `Lymphocytes`, `Monocytes`, `Eosinophils`, `Basophils`, `PLT_Count`, `MPV`, `Esbach`, `MBL_Level`, `ESR`, `C3`, `C4`. Toutes les autres colonnes (anticorps, symptômes, `clinical_symptoms_count`, `gender`, `diagnosis`) passent sous leur nom snake_case.

**Contrat de types (extrait de `_marts__models.yml`, `contract.enforced: true`)** — le build échoue si un type diverge :

| Colonne | data_type | not_null testé |
|---|---|---|
| `Age`, `Sickness_Duration_Months`, `WBC_Count` | bigint | ✅ |
| `RBC_Count`, `Hemoglobin`, `Hematocrit`, `ESR` | double | ✅ |
| `MCV`, `MCH`, `MCHC`, `RDW`, `Reticulocyte_Count`, `Neutrophils`, `Lymphocytes`, `Monocytes`, `Eosinophils`, `Basophils`, `PLT_Count`, `MPV`, `Esbach`, `MBL_Level`, `C3` | double | — |
| `C4` | double | — (log1p-transformée, voir §4.3) |
| `ana`, `anti_ds_dna`, symptômes (10), antibodies restants (~30) | bigint | variable — voir table détaillée `_marts__models.yml` |
| `clinical_symptoms_count` | bigint | ✅ (implicite `[0,10]` via §4.4) |
| `gender` | integer | ✅ + `accepted_values: [0, 1]` |
| `diagnosis` | integer | ✅ + `accepted_values: [0, 1, 2, 3, 4, 5]` |

---

## 5. Tests transverses (garde-fous multi-couches)

| Test | Portée | Severity | Ce qu'il garantit |
|---|---|---|---|
| `assert_no_row_loss_across_pipeline` | source → `ml_patients_dataset` | error (défaut) | Aucune couche ne perd/duplique de lignes par rapport au row count source |
| `assert_no_unmapped_diagnosis_labels` | `stg_patients` | error (défaut) | Toute nouvelle valeur de `diagnosis` brute non reconnue est signalée **avec son contexte**, avant de devenir un `NULL` silencieux |
| `assert_duplicate_row_rate_within_bounds` | `stg_patients` | **warn** | Le taux de duplication (~50% attendu) reste dans `[40%, 60%]` — dérive = signal upstream |
| `assert_patient_id_cardinality_guard` | `stg_patients` | error (défaut) | Le nombre de `patient_id` distincts reste dans `[500, 800]` — dérive = nouveau lot de patients / changement de schéma d'ID |

---

## 6. Gouvernance et évolution du contrat

1. **Toute modification du schéma source** (nouvelle colonne, nouveau label de diagnostic légitime, changement de plage clinique) doit être répercutée ici **et** dans `_staging__models.yml` / `_marts__models.yml` avant merge.
2. **La liste des colonnes corrélées supprimées (§4.3c)** est figée par calcul hors-pipeline : si la donnée source change significativement, elle doit être recalculée et ce document + `int_patients_cleaned.sql` mis à jour ensemble.
3. **Toute évolution des encodeurs ML** (`encoder/gender.json`, `encoder/diagnosis.json`) doit être répercutée dans `ml_patients_dataset.sql` **et** dans la table d'encodage du §4.5, sous peine d'incompatibilité silencieuse avec les modèles déjà entraînés.
4. **La question de la déduplication (§3.2)** est un choix produit non tranché : ce contrat documente le statu quo (conservation des doublons) mais n'empêche pas une décision future de déduplication — dans ce cas, `assert_duplicate_row_rate_within_bounds` et ce document devront être mis à jour de concert.
5. CI (`ci.yml`) exécute `dbt test` dans le job `data-quality-contracts`, juste après l'ingestion dlt et avant l'orchestration Dagster — toute violation de ce contrat bloque la pipeline avant qu'elle n'atteigne l'entraînement ML.
