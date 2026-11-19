# Contrat des douze écrans T2

Le parcours contient **exactement quatre scènes × trois états stables**. Le décompte `3 · 2 · 1` entre A et B est transitoire et n’est pas un treizième écran.

| N° | Identifiant | État | Durée/texte | Action positive |
|---:|---|---|---|---|
| 1 | `T2_CAPTURE_S1_A_GUIDE` | guide L’AVANT | 6 s | `COMMENCER À FILMER` |
| 2 | `T2_CAPTURE_S1_B_RECORDING` | caméra + chrono | `0:00 → 0:06` | arrêt automatique |
| 3 | `T2_CAPTURE_S1_C_REVIEW` | relecture sonore | `PRISE 1 · 0:06` | `SCÈNE SUIVANTE` |
| 4 | `T2_CAPTURE_S2_A_GUIDE` | guide LA TRANSFORMATION | 8 s | `COMMENCER À FILMER` |
| 5 | `T2_CAPTURE_S2_B_RECORDING` | caméra + chrono | `0:00 → 0:08` | arrêt automatique |
| 6 | `T2_CAPTURE_S2_C_REVIEW` | relecture sonore | `PRISE 2 · 0:08` | `SCÈNE SUIVANTE` |
| 7 | `T2_CAPTURE_S3_A_GUIDE` | guide LA RÉVÉLATION | 7 s | `COMMENCER À FILMER` |
| 8 | `T2_CAPTURE_S3_B_RECORDING` | caméra + chrono | `0:00 → 0:07` | arrêt automatique |
| 9 | `T2_CAPTURE_S3_C_REVIEW` | relecture sonore | `PRISE 3 · 0:07` | `SCÈNE SUIVANTE` |
| 10 | `T2_CAPTURE_S4_A_GUIDE` | guide L’APRÈS | 9 s | `COMMENCER À FILMER` |
| 11 | `T2_CAPTURE_S4_B_RECORDING` | caméra + chrono | `0:00 → 0:09` | arrêt automatique |
| 12 | `T2_CAPTURE_S4_C_REVIEW` | relecture sonore | `PRISE 4 · 0:09` | `VOIR MON AVANT / APRÈS` |

## État A — Guide

- consigne simple ;
- listes « À filmer » et « À éviter » ;
- bloc « Ce que tu dois faire » ;
- mention linguistique en bas ;
- exemple de phrase facultatif ;
- bouton `COMMENCER À FILMER`.

Mention commune exacte :

> Tu peux parler pendant que tu filmes, dans la langue que tu veux : fon, yoruba, français, anglais ou une autre langue que tu maîtrises.

Puis :

> Tu peux aussi ne pas parler si tu préfères.

## État B — Enregistrement

- caméra plein écran ;
- microphone actif ;
- indicateur `REC`, chrono et progression seulement ;
- vitesse 1,0× ;
- aucun arrêt manuel ;
- arrêt automatique à la durée exacte ;
- aucun texte de guide et aucun sous-titre automatique.

## État C — Validation

- lecture en boucle avec le son ;
- `REFAIRE` efface uniquement la prise courante et retourne à A ;
- la validation conserve la prise ;
- S1 à S3 ouvrent le guide suivant ;
- S4 ouvre l’état de montage.

La preuve visuelle est `ui-screens/T2_PLANCHE_12_ECRANS.png` et la liste machine est `ui-screens/manifest.json`.
