# Architecture serveur T2

La structure reprend les mécanismes génériques utiles du dépôt T1 public au commit verrouillé `c656510ab81d31d413dc4dfd74b42671532cd978`, sans modifier T1 et sans attribuer à T1 une implémentation Cloudflare absente de ses sources publiques.

Le métier, les textes et les médias restent ceux de T2 **« Avant / Après »**.

## Sources de vérité courantes

- `config/T2_avant_apres_template_v0_1_0.json` — `template_id: T2`, version visuelle `0.1.0` et profil `afrobeat_restaurants_maquis` ;
- `form/questions_T2.json` — six questions commerçant ;
- `config/T2_capture_flow_v1_0_0.json` — machine d’état exécutable des douze écrans ;
- `cloudflare/public/app.js` — consommateur réel des contrats formulaire/capture ;
- `config/T2_runtime_contract_v1_0_0.json` — liaisons formulaire, captures, audio, serveur et publication ;
- `config/T2_music_pool_v1_0_0.json` — pool final `300340 → 293956 → 300333 → 328624`, dérivés propres et cycle strict ;
- `audio/music/t2-afrobeat-v1/` — quatre instrumentales de 30 secondes sans voix, manifeste, preuves, provenance et checksums ;
- `config/T2_complete_voice_mix_v1_0_0_A.json` à `D.json` — quatre contrats de mixage courants ;
- `schemas/render_job.schema.json` — RenderJob historique `1.0.0` et profil complet additif `1.1.0` ;
- `schemas/render_result.schema.json` / `schemas/render_error.schema.json` — sorties terminales strictes ;
- `config/T2_text_motion_v0_3_0.json` et `baseline/T2_VISUAL_PIPELINE.lock.json` — visuel v0.3 inchangé ;
- `.github/workflows/server-render-unified.yml` — chemin complet de production courant, sans musique fixe ;
- `cloudflare/src/index.ts` — plan de contrôle, sélection/commit CAS et aucun moteur vidéo.

Les contrats v0.5/v0.6/v0.7, `config/T2_music_selection_v0_7_0.json`, le mix D/Afrofire et leurs éventuels artefacts restent des preuves historiques. Ils ne pilotent pas le runtime v1 et ne sont pas réécrits.

## Passage formulaire → captures → RenderJob → résultat

1. l’application charge les six questions et crée `merchant_payload` ;
2. elle exécute S1A/S1B/S1C … S4A/S4B/S4C, caméra et micro à vitesse identité ;
3. chaque prise acceptée est stockée dans R2 avec métadonnées et SHA-256 ;
4. le Worker lit `music/t2-last-success.json` et impose le successeur exact : état vide → A, puis A → B → C → D → A ;
5. le Worker enrichit le template avec les captures, la piste et son contrat de mixage, puis `repository_dispatch` déclenche GitHub Actions ;
6. GitHub télécharge et revalide les captures, puis reconstruit les 900 images depuis le même RenderJob ; pour la fixture canonique exacte, il matérialise à la place le master v0.3 verrouillé et vérifie ses deux empreintes ;
7. le mixeur vérifie par SHA-256 l’instrumentale locale de 30 secondes et choisit, pour chaque scène, la voix capturée exploitable ou son fallback enregistré à `1×` ;
8. la musique est duckée de −3 dB à −10 dB sous parole, avec attaque 120 ms et relâchement 450 ms ;
9. un QC indépendant valide l’unique MP4, l’absence d’audio autonome et l’invariance attendue du flux vidéo ;
10. `RenderResult` ou `RenderError` est renvoyé au Worker ; seul un `COMPLETED` conforme avance l’état d’un cran par écriture conditionnelle R2.

Un échec ne modifie pas l’état. Le rejeu du même succès est idempotent. Un choix explicite hors successeur et un second callback concurrent devenu hors séquence sont rejetés.

## Frontières

- **Navigateur** : saisie, caméra/micro, relecture, SHA-256.
- **Cloudflare Worker/R2** : sécurité, idempotence, stockage, cycle musical transactionnel, orchestration et statuts.
- **GitHub Actions** : OpenCV/FFmpeg, rendu dynamique, mixage, QC et artefact/pré-Release additive.

Cloudflare n’effectue aucun rendu. Le code Python refuse explicitement tout rendu complet lorsque `GITHUB_ACTIONS != true`.

Les sources Pixabay intégrales restent hors dépôt et ne sont jamais publiées. Le workflow peut utiliser les dérivés instrumentaux verrouillés pour le mix, mais refuse tout fichier audio autonome dans la livraison et refuse d’écraser une Release existante.

Voir [l’archive d’intégration Afrofire v0.7](T2_AFROFIRE_INTEGRATION_V0_7.md) pour l’historique et [le runtime musical v1 / plan de contrôle Cloudflare](T2_UNIFIED_RUNTIME_CLOUDFLARE.md) pour l’API, les secrets, les tests et le déploiement.
