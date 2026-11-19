# Architecture serveur T2

La structure technique reprend le modèle du dépôt T1 public, sans le modifier et sans réutiliser sa musique, ses voix ou ses médias.

## Sources de vérité

- `baseline/T1_BASELINE.lock.json` : dépôt et commit T1 de référence ;
- `form/questions_T2.json` : questions commerçant ;
- `capture-guide/consignes_T2.json` : quatre guides validés ;
- `config/T2_avant_apres_template_v0_1_0.json` : chronologie et transitions ;
- `schemas/render_job.schema.json` : contrat des réponses ;
- `engine/render_silent.py` : rendu actuel, sans texte et sans audio ;
- `.github/workflows/server-render-silent.yml` : seul chemin de production de la vidéo actuelle.

## Règle d’étape

La musique et la voix n’existent pas dans l’étape actuelle. Elles seront ajoutées dans des workflows séparés seulement après validation du montage silencieux.
