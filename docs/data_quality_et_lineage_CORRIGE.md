# Documentation qualité des données & lineage
**Projet Autoimmune Disease Prediction — MLOps/DevOps**
**Rôle : Data Quality Engineer — Hiba Bounaga (Member 5)**

> ⚠️ **Note de correction** — cette version remplace une précédente qui affirmait 27 624 lignes
> et un taux de duplication de 50 % dans le pipeline. Tous les chiffres ci-dessous ont été
> **recalculés directement** sur `Complete_Updated_Autoimmune_Disorder_Dataset2.csv`
> (13 812 lignes, 79 colonnes), le fichier source réellement partagé pour ce projet. Voir §4 pour
> le détail de l'écart avec les commentaires SQL existants (`int_patients_cleaned.sql` parle
> encore de "27,624 rows" / "13,812 fully duplicated rows") — **à trancher avant la soutenance**,
> voir l'action requise en fin de §4.

---

## 1. Où se situe ce document dans le pipeline

```
Dataset (CSV) → dlt (Member 3) → DuckDB → dbt (Member 4) → Data Quality (Member 5, ce doc)
→ ML Model → MLflow (Member 1) → FastAPI (Member 2) → Docker → CI/CD (Member 6) → Monitoring (Member 7)
```

Le travail de qualité des données s'insère juste après les transformations dbt et juste avant que le
dataset ne soit considéré "prêt pour le ML". Il répond à trois questions :
1. Peut-on faire confiance aux données à chaque étape du pipeline ?
2. Qu'est-ce qui est *garanti* à l'équipe en aval (ML, API) sur la forme des données ?
3. Si quelque chose casse, où et pourquoi ?

---

## 2. Lineage du pipeline

| Couche | Modèle | Rôle | Grain | Lignes (mesuré) | Matérialisation |
|---|---|---|---|---|---|
| Source | `raw_medical_data.patients` | Table brute chargée par dlt (`dlt_pipeline/ingestion.py`) | 1 ligne / enregistrement source | **13 812** | table DuckDB |
| Staging | `stg_patients` | Miroir propre de la source : casse du texte, normalisation du diagnostic | identique à la source | **13 812** | view |
| Intermediate | `int_patients_cleaned` | Décisions de nettoyage statistique : 2 colonnes constantes supprimées, `C4` log-transformé, 15 colonnes corrélées (\|r\|>0.85) supprimées | identique | **13 812** | view |
| Marts | `patients_features` | + feature engineering (`clinical_symptoms_count`) | identique | **13 812** | table |
| Marts | `ml_patients_dataset` | Dataset final, entièrement numérique, encodage ordinal, **contrat de données appliqué** | identique, **60 colonnes** | **13 812** | table |

Aucune ligne n'est jamais supprimée ni dupliquée par les modèles dbt eux-mêmes — c'est le rôle du
test `assert_no_row_loss_across_pipeline` (section 5) de le garantir en continu, quel que soit le
nombre exact de lignes source.

**60 colonnes en sortie, vérifié par calcul** : 77 colonnes en staging → -2 (colonnes constantes)
→ -15 (colonnes corrélées) = 60 en `int_patients_cleaned` → +1 (`clinical_symptoms_count`) = 61 en
`patients_features` → -1 (`patient_id`, retiré car ce n'est pas une feature) = **60** en
`ml_patients_dataset`. Ce chiffre était correct dans la version précédente du document.

**Lineage visuel auto-généré** : `dbt docs generate` produit un graphe interactif (DAG) cliquable
montrant exactement ces dépendances, colonne par colonne. Pour le consulter :
```bash
cd dbt
export DBT_PROFILES_DIR=$(pwd)
dbt docs generate
dbt docs serve   # ouvre http://localhost:8080
```

---

## 3. Dictionnaire de données (`ml_patients_dataset`, l'interface finale)

**60 colonnes, 13 812 lignes.** Catégories (recomptées) :

| Catégorie | Nombre de colonnes | Exemples | Type |
|---|---|---|---|
| Démographie | 2 | `Age`, `gender` (0=female, 1=male) | bigint / integer |
| Hématologie (NFS) | 23 | `Hemoglobin`, `WBC_Count`, `PLT_Count`, `MCV`, `Esbach`, `MBL_Level`, `ESR`, `C3`, `C4`... | double / bigint |
| Immunologie / anticorps | 33 | `ana`, `anti_ds_dna`, `rheumatoid_factor`, `crp`... | bigint (binaire) / double |
| Symptômes cliniques | 10 → agrégés | fusionnés dans `clinical_symptoms_count` (0-10) | bigint |
| Feature engineering | 1 | `clinical_symptoms_count` | bigint |
| Cible | 1 | `diagnosis` (0-5, encodage ordinal) | integer |

Encodages figés (doivent rester synchronisés avec `encoder/gender.json` et `encoder/diagnosis.json`) :
- `gender` : female=0, male=1
- `diagnosis` : autoimmune_orchitis=0, graves_disease=1, normal=2, rheumatoid_arthritis=3,
  sjogren_syndrome=4, systemic_lupus_erythematosus=5

Répartition réelle des 6 classes (mesurée sur les 13 812 lignes, plutôt équilibrée) : Autoimmune
orchitis (2 490), Systemic lupus erythematosus (2 390), Rheumatoid arthritis (2 310), Normal
(2 230), Sjögren syndrome (2 200), Graves' disease (2 192).

Le dictionnaire complet colonne-par-colonne (nom, type, description) est déclaré dans
`dbt/models/marts/_marts__models.yml` — c'est la source de vérité, pas ce document.

---

## 4. Problèmes de qualité identifiés (audit)

Tous confirmés en exécutant les requêtes directement sur `Complete_Updated_Autoimmune_Disorder_Dataset2.csv`
(13 812 lignes) :

| # | Problème | Mesure exacte | Où | Statut |
|---|---|---|---|---|
| 1 | `patient_id` non unique | **643 valeurs distinctes** pour 13 812 lignes → chaque `patient_id` se répète en moyenne ~21 fois | source/staging | Documenté, non corrigé (décision d'équipe requise) |
| 2 | Lignes strictement dupliquées (toutes colonnes identiques) | **0 sur 13 812** dans ce fichier — un `patient_id` répété n'a **pas** forcément la même ligne complète | staging | À reconfirmer sur la vraie base DuckDB, voir action ci-dessous |
| 3 | Colonnes binaires redondantes | 15 colonnes corrélées (\|r\|>0.85) avec une colonne conservée | intermediate | Corrigé (colonnes retirées dans `int_patients_cleaned.sql`) |
| 4 | Colonnes constantes | `Anti_tTG` et `Progesterone_antibodies` = 0 sur les 13 812 lignes, aucune variance | staging/intermediate | Corrigé (colonnes retirées) |
| 5 | Collision de colonnes à l'ingestion | `Anti-dsDNA`/`Anti_dsDNA` et `Anti-Sm`/`Anti_Sm` → dlt normalise en snake_case → une valeur écrase l'autre silencieusement | dlt (Member 3) | **Non résolu, hors périmètre dbt** — à remonter formellement à Benlaidi Hajar |
| 6 | Label diagnostic non mappé | `other_autoimmune_disease` n'a pas d'entrée dans l'encoder → deviendrait `NULL` | marts | Filet de sécurité en place (tests + alerte amont), 0 occurrence actuellement (les 6 labels bruts du CSV correspondent tous au vocabulaire connu) |

### ⚠️ Action requise avant la soutenance : écart entre le CSV et les commentaires SQL

Les commentaires dans `int_patients_cleaned.sql` et les bornes des tests
`assert_duplicate_row_rate_within_bounds` (attend 40–60 % de doublons) et
`assert_patient_id_cardinality_guard` (attend 500–800 `patient_id` distincts) sont écrits en
référence à **27 624 lignes / 13 812 doublons exacts (50 %)**. Le fichier CSV analysé ici en
contient **13 812, avec 0 doublon de ligne exacte**. Deux hypothèses, à trancher avec Benlaidi
Hajar (Data Engineer) en interrogeant directement DuckDB :

- **Si la vraie table `raw_medical_data.patients` fait 27 624 lignes** : ce CSV n'est qu'une
  moitié/un export partiel de la donnée de production. Les chiffres de volumétrie de ce document
  doivent alors être repris sur les 27 624 lignes réelles, et `assert_duplicate_row_rate_within_bounds`
  reste valide tel quel.
- **Si la vraie table fait bien 13 812 lignes** (comme ce CSV) : le taux de doublons réel est 0 %,
  ce qui ferait **échouer** `assert_duplicate_row_rate_within_bounds` (bornes 40–60 %) dès le
  premier `dbt build`. Il faudrait alors resserrer les bornes du test vers 0 %, et les 643
  `patient_id` distincts (dans la borne actuelle [500, 800]) resteraient corrects.

Tant que ce point n'est pas vérifié directement sur `autoimmune_pipeline.duckdb`
(`SELECT COUNT(*) FROM raw_medical_data.patients`), le statut "29/29 tests passent" ne peut pas
être affirmé avec certitude dans ce document — il est donc retiré de cette version (voir §5).

---

## 5. Suite de tests automatisés

Tests définis dans le projet (`dbt/models/*/_*.yml` pour les tests génériques et `dbt/tests/` pour
les tests singuliers) :

| Type | Nombre | Exemples |
|---|---|---|
| Tests génériques dbt (couche transformation, Member 4) | 13 | `not_null`, `accepted_values` sur gender/diagnosis |
| Tests singuliers qualité (Member 5) | 4 | voir ci-dessous |
| Contraintes de contrat (`contract.enforced`) | 60 déclarations de type sur `ml_patients_dataset` | types de colonnes |

**Les 4 tests singuliers**, tous conçus pour surveiller un problème *connu* par des bornes plutôt
que de faire échouer le build en permanence (ce qui serait ignoré par l'équipe) :

1. `assert_duplicate_row_rate_within_bounds` (severity `warn`) — le taux de doublons doit rester
   entre 40 % et 60 %. **À revalider selon §4** avant de considérer ce test fiable sur la donnée
   actuelle.
2. `assert_patient_id_cardinality_guard` — le nombre de `patient_id` distincts doit rester entre
   500 et 800. Cohérent avec les 643 mesurés.
3. `assert_no_row_loss_across_pipeline` — le nombre de lignes doit être identique à chaque couche,
   quel que soit le total (indépendant du débat §4).
4. `assert_no_unmapped_diagnosis_labels` — alerte dès `stg_patients` si un nouveau label de
   diagnostic apparaît. Cohérent : les 6 labels bruts du CSV correspondent tous au vocabulaire
   attendu.

**Exécution** :
```bash
cd dbt
export DBT_PROFILES_DIR=$(pwd)
dbt build        # run + test tous les modèles + le contrat
dbt test         # tests seuls, si les modèles sont déjà construits
```
*(Le résultat exact du dernier run, et sa date, doivent être ré-obtenus en relançant `dbt build`
contre la base réelle — non ré-affirmé ici tant que §4 n'est pas tranché.)*

---

## 6. Data Contract

Le modèle `ml_patients_dataset` porte `config: contract: {enforced: true}` avec les **60 colonnes**
déclarées (nom + type exact, voir `_marts__models.yml`). C'est l'interface remise à :
- l'équipe ML (entraînement du modèle)
- l'API FastAPI (`app/main.py`, schéma `PatientData`)
- le détecteur de drift du monitoring (Member 7)

**Effet concret** : si un futur changement dans `ml_patients_dataset.sql` renomme, retype, supprime
ou réordonne une colonne sans mettre à jour le contrat, `dbt build` échoue immédiatement à la
compilation avec un message explicite — au lieu que l'erreur apparaisse plus tard comme un bug API
ou une fausse alerte de drift.

**Règle d'équipe à faire valider** : tout changement de schéma sur `ml_patients_dataset` doit être
reflété dans le contrat **et** communiqué à Member 2 (Déploiement) et Member 7 (Monitoring) avant
merge.

---

## 7. Pour la soutenance — résumé en une phrase par item
- **Tests qualité** : 4 tests qui surveillent des problèmes connus par des bornes plutôt que des
  échecs bruts, + 13 tests hérités de la couche transformation — bornes de duplication à reconfirmer
  contre la base réelle avant présentation (§4).
- **Data Contract** : schéma figé (60 colonnes) et vérifié automatiquement sur l'interface de sortie
  vers le ML/API.
- **Lineage** : DAG auto-généré par `dbt docs`, 5 couches, 13 812 lignes mesurées sur le fichier
  source fourni, aucune perte de ligne vérifiée entre les couches.
- **Documentation** : ce document + le dictionnaire de données dans les fichiers `.yml` du projet dbt.
