# Architecture serveur T2

La structure technique reprend le modèle du dépôt T1 public, sans le modifier et sans réutiliser sa musique, ses voix ou ses médias.

## Sources de vérité

- `baseline/T1_BASELINE.lock.json` : dépôt et commit T1 de référence ;
- `form/questions_T2.json` : questions commerçant ;
- `capture-guide/consignes_T2.json` : quatre guides validés ;
- `config/T2_avant_apres_template_v0_1_0.json` : chronologie et transitions ;
- `schemas/render_job.schema.json` : contrat strict du RenderJob (`merchant_payload`, quatre `captures`, sortie) ;
- `engine/render_silent.py` : référence v0.2 du montage sans texte ;
- `config/T2_runtime_contract_v0_3_0.json` : liaison formulaire, caméras, scènes et future voix ;
- `config/T2_text_motion_v0_3_0.json` : police, blocs et fenêtres des textes dynamiques ;
- `engine/render_text_motion.py` : rendu v0.3 des informations commerçant ;
- `.github/workflows/server-render-silent.yml` : seul chemin de production de la vidéo actuelle.

## Règle d’étape

La musique et la voix ne sont pas encore mixées dans l’étape actuelle. Les quatre captures conservent toutefois une timeline audio identité à 1,0× ; la future voix et le ducking musical sont réservés dans le contrat, puis seront activés seulement après les validations prévues.

## Passage questions → RenderJob → montage

Le mécanisme reprend les noms publics de T1 au commit verrouillé :

1. les six réponses sont normalisées dans `merchant_payload` ;
2. les quatre prises sont liées à `captures.S1`…`captures.S4` avec les durées 6 000, 8 000, 7 000 et 9 000 ms ;
3. `tools/build_render_job.py` valide le tout avec `schemas/render_job.schema.json` ;
4. `engine/render_silent.py` lit les captures et la sortie depuis ce RenderJob.

Le profil v0.2 garde `render_business_text=false`. Le profil v0.3 utilise `render_business_text=true`, lit les mêmes champs et les dessine après les transitions. `render_audio=false` reste imposé uniquement pendant le contrôle des textes.
