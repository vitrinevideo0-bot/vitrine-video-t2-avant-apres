# T2 « Avant / Après » — runtime unifié v0.7 et plan de contrôle Cloudflare

## Portée

Cette implémentation relie réellement le formulaire T2, les douze écrans de capture, les quatre médias caméra/micro, les textes commerçant, le rendu visuel v0.3, les voix, Afrofire (candidat D), le ducking, le contrôle qualité et la publication GitHub.

T1 reste une référence publique **en lecture seule** au commit `c656510ab81d31d413dc4dfd74b42671532cd978`. Ses mécanismes génériques utiles sont repris, mais le domaine reste exclusivement T2 **« Avant / Après »**. Le dépôt T1 public ne contient pas de Worker Cloudflare : la présente implémentation Cloudflare est propre à T2.

## Parcours canonique

1. `cloudflare/public/app.js` charge `form/questions_T2.json` par `/v1/contracts/form`.
2. Il charge et exécute les douze états stables de `config/T2_capture_flow_v1_0_0.json` par `/v1/contracts/capture-flow`.
3. Le décompte 3–2–1 est transitoire et ne crée pas un treizième écran.
4. Chaque scène demande caméra et microphone, s’arrête automatiquement après 6, 8, 7 ou 9 secondes, puis se relit **avec le son à vitesse 1×**.
5. `REFAIRE` détruit la prise locale. L’acceptation calcule son SHA-256 et l’envoie à R2.
6. Après S4, le Worker produit un seul `RenderJob` complet `1.1.0` et déclenche `repository_dispatch` sur GitHub.
7. GitHub télécharge les quatre captures avec vérification SHA-256, valide les médias, reconstruit les 900 images depuis ce même job, vérifie le SHA-256 du flux H.264 (l’empreinte du conteneur MP4 est seulement consignée), puis mixe voix et musique.
8. Le ducking conserve −3 dB hors parole, −10 dB sous parole, attaque 120 ms et relâchement 450 ms.
9. Le QC indépendant produit `RenderResult` ou `RenderError`, puis GitHub rappelle le Worker.
10. Le client suit `UPLOADING → READY → QUEUED → RUNNING → COMPLETED|FAILED` et ouvre le run GitHub.

## Frontières d’exécution

| Plan | Responsabilités |
|---|---|
| Navigateur | six réponses commerçant, machine à 12 écrans, caméra/micro, relecture, SHA-256 |
| Cloudflare Worker + R2 | authentification pilote, idempotence, stockage, RenderJob, dispatch, statuts et callback |
| GitHub Actions | FFmpeg/OpenCV, rendu 900 images, voix 1×, Afrofire (D), ducking, QC, artefact ou Release |

Cloudflare ne lance ni FFmpeg, ni OpenCV, ni mixage. Tout rendu de production est refusé hors GitHub Actions par le code Python lui-même.

## Voix

Le RenderJob accepte trois modes :

- `registered_voice_clips` — les quatre voix v0.5 verrouillées ;
- `captured_scene_audio` — le son des quatre prises, sans retiming ;
- `captured_or_registered_fallback` — le son capturé lorsqu’il contient une parole exploitable, sinon la voix enregistrée de la même scène.

Dans tous les cas, `source_speed = 1.0` et `audio_time_map = identity`. Aucun sous-titre automatique n’est produit.

Le parcours navigateur demande `captured_or_registered_fallback`. Le garde de parole exige au moins 0,35 s actives et un pic d’au moins −42 dBFS. Le rapport de mix consigne, scène par scène, la source réellement utilisée et la cause éventuelle du fallback.

## Musique

La sélection courante est explicitement **D — Afrofire · DPStudioMusic**. B est rejetée pour la production courante en raison du badge Content ID Registered affiché par sa page historique. D ne devient pas un choix implicite : le RenderJob la sélectionne explicitement et le JSON canonique conserve uniquement le profil sémantique `afrobeat_restaurants_maquis`.

Avant tout mixage, GitHub vérifie exactement :

```text
24e9606e14e4708e8c8ffa3a6a97429dbfc95049d388481392d72b971e932c61
```

La source vérifiée mesure `7 680 768` octets. Lors de la vérification datée du 2026-11-19, la page affichait le badge AI generated et aucun badge Content ID. Cette observation n’est pas une garantie juridique absolue.

La source Pixabay, les WAV voix et les stems restent éphémères. Ils ne sont jamais publiés comme fichiers autonomes. Les détails sont verrouillés dans `config/T2_music_selection_v0_7_0.json`.

## API Worker

### Routes publiques en lecture

- `GET /health`
- `GET /v1/contracts/form`
- `GET /v1/contracts/capture-flow`
- `GET /v1/jobs/{job_id}` — statut sans données commerçant ni média

### Routes client protégées par `CLIENT_API_TOKEN`

- `POST /v1/jobs`
- `PUT /v1/jobs/{job_id}/captures/S1|S2|S3|S4`
- `POST /v1/jobs/{job_id}/dispatch`

`POST /v1/jobs` exige `Idempotency-Key`. Le Worker réserve cette clé par écriture R2 conditionnelle.

Les captures acceptées sont `video/mp4`, `video/webm` ou `video/quicktime`. Les métadonnées sont déclarées par en-têtes, puis contrôlées de nouveau avec `ffprobe` sur GitHub. R2 vérifie le SHA-256 pendant l’écriture ; GitHub le recalcule après téléchargement.

### Routes GitHub protégées par `CALLBACK_TOKEN`

- `GET /v1/jobs/{job_id}/payload`
- `GET /v1/jobs/{job_id}/captures/{slot}`
- `POST /v1/jobs/{job_id}/events`

Un callback `COMPLETED` doit contenir un `RenderResult` rattaché au bon job avec QC `PASS`. Le Worker recroise aussi le profil, l’URI de sortie, les quatre empreintes de capture et le SHA-256 Afrofire avec le RenderJob stocké. Un callback `FAILED` doit contenir un `RenderError` rattaché au bon job.

## Déploiement Cloudflare

Le workflow `.github/workflows/cloudflare-control-plane.yml` valide toujours le Worker et ne déploie que sur demande explicite avec `deploy=true`.

### Secrets GitHub requis

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `GITHUB_DISPATCH_TOKEN` — jeton fin GitHub avec `Contents: write` sur T2
- `CLOUDFLARE_CALLBACK_TOKEN` — même valeur injectée dans le Worker et utilisée par le workflow de rendu
- `T2_CLIENT_API_TOKEN` — code d’accès pilote saisi dans l’application

### Variable GitHub requise

- `T2_PUBLIC_API_BASE` — URL HTTPS publique du Worker, par exemple `https://t2-avant-apres-control-plane.<compte>.workers.dev`

Le workflow provisionne les buckets `t2-avant-apres-media` et `t2-avant-apres-media-preview`, installe les trois secrets Worker et déploie le Worker avec ses assets statiques.

Aucun identifiant Cloudflare n’est présent dans le dépôt. Sans ces prérequis, l’implémentation est testable et déployable, mais aucun déploiement réel n’est tenté.

## Validation locale sans rendu de production

```bash
python -m pip install -r requirements.txt
npm ci --prefix cloudflare
npm run test --prefix cloudflare

python cloudflare/test/mock_github_api.py --port 8790 &
cd cloudflare
npx wrangler dev --local --port 8787 \
  --var CLIENT_API_TOKEN:test-client \
  --var CALLBACK_TOKEN:test-callback \
  --var GITHUB_TOKEN:test-token \
  --var PUBLIC_API_BASE:http://127.0.0.1:8787 \
  --var GITHUB_API_BASE:http://127.0.0.1:8790
```

Dans un second terminal :

```bash
python cloudflare/test/control_plane_integration.py
```

Ce test couvre le formulaire canonique, le contrat des 12 écrans, l’authentification, l’idempotence, MP4/WebM, R2, le RenderJob strict, le dispatch, le téléchargement GitHub, le callback invalide puis le callback valide. Il ne produit aucune vidéo locale.

## Rendu de référence unique

Le workflow `.github/workflows/server-render-unified.yml` peut être lancé manuellement sur GitHub. Il reconstruit l’exemplaire canonique D/Afrofire, prouve les verrous historiques et visuels, exécute les tests, puis rend une seule vidéo. L’option `publish_release` est désactivée par défaut.

Si une Release v0.7 est demandée explicitement, le workflow refuse d’écraser un tag existant et publie exactement un MP4, les rapports et les checksums — jamais la source musicale seule. Les jobs Cloudflare utilisent le même workflow par `repository_dispatch`, mais publient un artefact GitHub privé plutôt qu’une nouvelle Release publique à chaque commerçant.
