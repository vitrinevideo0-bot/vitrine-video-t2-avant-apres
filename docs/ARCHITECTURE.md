# Architecture serveur T2

La structure reprend les mécanismes génériques utiles du dépôt T1 public au commit verrouillé `c656510ab81d31d413dc4dfd74b42671532cd978`, sans modifier T1 et sans attribuer à T1 une implémentation Cloudflare absente de ses sources publiques.

Le métier, les textes et les médias restent ceux de T2 **« Avant / Après »**.

## Sources de vérité

- `config/T2_avant_apres_template_v0_1_0.json` — `template_id: T2`, version visuelle `0.1.0` et profil `afrobeat_restaurants_maquis` ;
- `form/questions_T2.json` — six questions commerçant ;
- `config/T2_capture_flow_v1_0_0.json` — machine d’état exécutable des douze écrans ;
- `cloudflare/public/app.js` — consommateur réel des contrats formulaire/capture ;
- `config/T2_runtime_contract_v0_7_0.json` — liaisons formulaire, captures, audio, serveur et publication ;
- `config/T2_music_selection_v0_7_0.json` — décision explicite D/Afrofire et preuve de droits observée ;
- `schemas/render_job.schema.json` — RenderJob historique `1.0.0` et profil complet additif `1.1.0` ;
- `schemas/render_result.schema.json` / `schemas/render_error.schema.json` — sorties terminales strictes ;
- `config/T2_text_motion_v0_3_0.json` et `baseline/T2_VISUAL_PIPELINE.lock.json` — visuel v0.3 inchangé ;
- `config/T2_complete_voice_mix_v0_7_0.json` — quatre voix, Afrofire et ducking inchangé ;
- `.github/workflows/server-render-unified.yml` — seul chemin complet de production courant ;
- `cloudflare/src/index.ts` — plan de contrôle, sans moteur vidéo.

Les contrats v0.5/v0.6 et leurs Releases restent des preuves historiques. Ils ne sont pas réécrits.

## Passage formulaire → captures → RenderJob → résultat

1. l’application charge les six questions et crée `merchant_payload` ;
2. elle exécute S1A/S1B/S1C … S4A/S4B/S4C, caméra et micro à vitesse identité ;
3. chaque prise acceptée est stockée dans R2 avec métadonnées et SHA-256 ;
4. le Worker enrichit le template canonique v0.7 avec ces données, sans réécrire le plan visuel ;
5. `repository_dispatch` déclenche GitHub Actions ;
6. GitHub matérialise et revalide les captures ; les jobs dynamiques reconstruisent leurs 900 images, tandis que l’exemplaire canonique matérialise le master v0.3 exact et vérifie ses deux empreintes verrouillées ;
7. le mixeur choisit pour chaque scène la voix capturée exploitable ou son fallback enregistré, à `1×` ;
8. la source D — Afrofire est vérifiée par SHA-256, puis duckée de −3 dB à −10 dB sous parole ;
9. un QC indépendant valide l’unique MP4 et l’invariance du flux vidéo ;
10. `RenderResult` ou `RenderError` est renvoyé au Worker et archivé avec les preuves GitHub.

## Frontières

- **Navigateur** : saisie, caméra/micro, relecture, SHA-256.
- **Cloudflare Worker/R2** : sécurité, idempotence, stockage, orchestration, statuts.
- **GitHub Actions** : OpenCV/FFmpeg pour le dynamique, matérialisation du master canonique, mixage, QC, artefact/Release.

Cloudflare n’effectue aucun rendu. Le code Python refuse explicitement tout rendu complet lorsque `GITHUB_ACTIONS != true`.

La source musicale est temporaire, vérifiée avant mixage et jamais publiée seule. Le workflow refuse aussi d’écraser une Release existante.

Voir [T2_AFROFIRE_INTEGRATION_V0_7.md](T2_AFROFIRE_INTEGRATION_V0_7.md) pour la sélection musicale et [T2_UNIFIED_RUNTIME_CLOUDFLARE.md](T2_UNIFIED_RUNTIME_CLOUDFLARE.md) pour l’API, les secrets, les tests et le déploiement.
