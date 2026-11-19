# Architecture serveur T2

La structure technique reprend le modèle du dépôt T1 public, sans le modifier et sans réutiliser sa musique, ses voix ou ses médias.

## Sources de vérité

- `baseline/T1_BASELINE.lock.json` : dépôt et commit T1 de référence ;
- `form/questions_T2.json` : questions commerçant ;
- `capture-guide/consignes_T2.json` : quatre guides validés ;
- `config/T2_avant_apres_template_v0_1_0.json` : chronologie et transitions ;
- `schemas/render_job.schema.json` : contrat strict du RenderJob (`merchant_payload`, quatre `captures`, sortie) ;
- `engine/render_silent.py` : rendu actuel, sans texte et sans audio ;
- `.github/workflows/server-render-silent.yml` : seul chemin de production de la vidéo actuelle.

## Règle d’étape

La musique et la voix n’existent pas dans l’étape actuelle. Elles seront ajoutées dans des workflows séparés seulement après validation du montage silencieux.

## Passage questions → RenderJob → montage

Le mécanisme reprend les noms publics de T1 au commit verrouillé :

1. les six réponses sont normalisées dans `merchant_payload` ;
2. les quatre prises sont liées à `captures.S1`…`captures.S4` avec les durées 6 000, 8 000, 7 000 et 9 000 ms ;
3. `tools/build_render_job.py` valide le tout avec `schemas/render_job.schema.json` ;
4. `engine/render_silent.py` lit les captures et la sortie depuis ce RenderJob.

À l’étape actuelle, `merchant_payload` est stocké mais `render_business_text=false` et `render_audio=false`. Le moteur ne contient aucune API de dessin de texte et l’export supprime tout flux audio.
