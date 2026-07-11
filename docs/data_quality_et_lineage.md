# Documentation qualité des données & lineage
**Projet Autoimmune Disease Prediction — MLOps/DevOps**
**Rôle : Data Quality Engineer — Hiba Bounaga (Member 5)**

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

| Couche | Modèle | Rôle | Grain | Matérialisation |
|---|---|---|---|---|
| Source | `raw_medical_data.patients` | Table brute chargée par dlt (`dlt_pipeline/ingestion.py`) | 1 ligne / enregistrement source | table DuckDB |
| Staging | `stg_patients` | Miroir propre de la source : casse du texte, normalisation du diagnostic | identique à la source (27 624 lignes) | view |
| Intermediate | `int_patients_cleaned` | Décisions de nettoyage statistique : colonnes constantes supprimées, `C4` log-transformé, colonnes corrélées (\|r\|>0.85) supprimées | identique (27 624 lignes) | view |
| Marts | `patients_features` | + feature engineering (`clinical_symptoms_count`) | identique (27 624 lignes) | table |
| Marts | `ml_patients_dataset` | Dataset final, entièrement numérique, encodage ordinal, **contrat de données appliqué** | identique (27 624 lignes), 60 colonnes | table |

Aucune ligne n'est jamais supprimée ni dupliquée par les modèles dbt eux-mêmes : c'est vérifié
automatiquement par le test `assert_no_row_loss_across_pipeline` (section 5).

**Lineage visuel auto-généré** : `dbt docs generate` produit un graphe interactif (DAG) cliquable
montrant exactement ces dépendances, colonne par colonne. Pour le consulter :
```bash
cd dbt
export DBT_PROFILES_DIR=$(pwd)
dbt docs generate
dbt docs serve   # ouvre http://localhost:8080
```
Le site statique généré (`target/index.html`, `catalog.json`, `manifest.json`) est fourni dans
`dbt_docs_site/` et peut être ouvert directement dans un navigateur sans relancer dbt.

---

## 3. Dictionnaire de données (`ml_patients_dataset`, l'interface finale)

60 colonnes, 27 624 lignes. Catégories :

| Catégorie | Nombre de colonnes | Exemples | Type |
|---|---|---|---|
| Démographie | 2 | `Age`, `gender` (0=female, 1=male) | bigint / integer |
| Hématologie (NFS) | 17 | `Hemoglobin`, `WBC_Count`, `PLT_Count`, `MCV`... | double |
| Immunologie / anticorps | 33 | `ana`, `anti_ds_dna`, `rheumatoid_factor`, `crp`... | bigint (binaire) / double |
| Symptômes cliniques | 10 → agrégés | fusionnés dans `clinical_symptoms_count` (0-10) | bigint |
| Feature engineering | 1 | `clinical_symptoms_count` | bigint |
| Cible | 1 | `diagnosis` (0-5, encodage ordinal) | integer |

Encodages figés (doivent rester synchronisés avec `encoder/gender.json` et `encoder/diagnosis.json`) :
- `gender` : female=0, male=1
- `diagnosis` : autoimmune_orchitis=0, graves_disease=1, normal=2, rheumatoid_arthritis=3,
  sjogren_syndrome=4, systemic_lupus_erythematosus=5

Le dictionnaire complet colonne-par-colonne (nom, type, description) est déclaré dans
`dbt/models/marts/_marts__models.yml` — c'est la source de vérité, pas ce document.

---

## 4. Problèmes de qualité identifiés (audit)

Tous confirmés en exécutant les requêtes directement sur `duckdb/autoimmune_pipeline.duckdb` (27 624 lignes) :

| # | Problème | Mesure exacte | Où | Statut |
|---|---|---|---|---|
| 1 | `patient_id` non unique | 643 valeurs distinctes seulement (pour 27 624 lignes) | source/staging | Documenté, non corrigé (décision d'équipe requise) |
| 2 | Lignes strictement dupliquées | 13 812 / 27 624 (exactement 50 %) | staging | Volontairement conservé pour fidélité au notebook — **surveillé**, pas bloqué |
| 3 | Colonnes binaires identiques | 14 colonnes recoupant la liste des 15 colonnes retirées pour corrélation >0.85 | intermediate | Corrigé (colonnes retirées) |
| 4 | Collision de colonnes à l'ingestion | `Anti-dsDNA`/`Anti_dsDNA` et `Anti-Sm`/`Anti_Sm` → dlt normalise en snake_case → une valeur écrase l'autre silencieusement | dlt (Member 3) | **Non résolu, hors périmètre dbt** — à remonter formellement à Benlaidi Hajar |
| 5 | Label diagnostic non mappé | `other_autoimmune_disease` n'a pas d'entrée dans l'encoder → deviendrait `NULL` | marts | Filet de sécurité en place (tests + alerte amont), 0 occurrence actuellement |

### Recommandation formelle sur le problème #4
C'est le seul problème qui ne peut pas être résolu dans dbt : les données sont déjà perdues au
moment où elles arrivent dans DuckDB. Deux options à trancher en équipe :
- **Option A** : corriger `dlt_pipeline/ingestion.py` pour renommer les colonnes source avant le
  chargement (ex. `Anti-dsDNA` → `anti_ds_dna_dash`, `Anti_dsDNA` → `anti_ds_dna_underscore`).
- **Option B** : documenter formellement la perte comme acceptée si les deux colonnes sont jugées
  redondantes après analyse clinique.
À valider avec Benlaidi Hajar (Data Engineer) et Malak (Data Transformation).

---

## 5. Suite de tests automatisés

29 tests au total (`dbt build` — voir `dbt/models/*/_*.yml` pour les tests génériques et
`dbt/tests/` pour les tests singuliers) :

| Type | Nombre | Exemples |
|---|---|---|
| Tests génériques dbt (déjà existants, Member 4) | 13 | `not_null`, `accepted_values` sur gender/diagnosis |
| Tests singuliers qualité (nouveaux, Member 5) | 4 | voir ci-dessous |
| Tests de contrat (déclaratifs, via `contract.enforced`) | 12 | types de colonnes de `ml_patients_dataset` |

**Les 4 tests singuliers ajoutés**, tous conçus pour surveiller un problème *connu et accepté*
plutôt que de faire échouer le build en permanence (ce qui serait ignoré par l'équipe) :

1. `assert_duplicate_row_rate_within_bounds` — le taux de doublons doit rester entre 40 % et 60 %.
2. `assert_patient_id_cardinality_guard` — le nombre de `patient_id` distincts doit rester entre 500 et 800.
3. `assert_no_row_loss_across_pipeline` — le nombre de lignes doit être identique à chaque couche.
4. `assert_no_unmapped_diagnosis_labels` — alerte dès `stg_patients` si un nouveau label de diagnostic apparaît.

**Exécution** :
```bash
cd dbt
export DBT_PROFILES_DIR=$(pwd)
dbt build        # run + test tous les modèles + le contrat
dbt test         # tests seuls, si les modèles sont déjà construits
```
Validé le 10/07/2026 contre la base réelle : **29/29 tests passent**.

---

## 6. Data Contract

Le modèle `ml_patients_dataset` porte `config: contract: {enforced: true}` avec les 60 colonnes
déclarées (nom + type exact). C'est l'interface remise à :
- l'équipe ML (entraînement du modèle)
- l'API FastAPI (`app/main.py`, schéma `PatientData`)
- le détecteur de drift du monitoring (Member 7)

**Effet concret** : si un futur changement dans `ml_patients_dataset.sql` renomme, retype, supprime
ou réordonne une colonne sans mettre à jour le contrat, `dbt build` échoue immédiatement à la
compilation avec un message explicite — au lieu que l'erreur apparaisse plus tard comme un bug API
ou une fausse alerte de drift. Testé et confirmé (simulation d'un changement de type sur `Age`,
bloqué correctement par dbt).

**Règle d'équipe à faire valider** : tout changement de schéma sur `ml_patients_dataset` doit être
reflété dans le contrat **et** communiqué à Member 2 (Déploiement) et Member 7 (Monitoring) avant
merge.

---

## 7. Pour la soutenance — résumé en une phrase par item
- **Tests qualité** : 4 tests qui surveillent des problèmes connus par des bornes plutôt que des
  échecs bruts, + 13 tests hérités de la couche transformation.
- **Data Contract** : schéma figé et vérifié automatiquement sur l'interface de sortie vers le ML/API.
- **Lineage** : DAG auto-généré par `dbt docs`, 5 couches, aucune perte de ligne vérifiée.
- **Documentation** : ce document + le dictionnaire de données dans les fichiers `.yml` du projet dbt.
