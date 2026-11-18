# T2 « Avant / Après » — runtime musical A–D persistant et plan de contrôle Cloudflare

## Portée

Cette implémentation relie réellement le formulaire T2, les douze écrans de capture, les quatre médias caméra/micro, les textes commerçant, le rendu visuel v0.3, les voix, le pool musical approuvé A–D, le ducking, le contrôle qualité et la publication GitHub.

T1 reste une référence publique **en lecture seule** au commit `c656510ab81d31d413dc4dfd74b42671532cd978`. Ses mécanismes génériques utiles sont repris, mais le domaine reste exclusivement T2 **« Avant / Après »**. Le dépôt T1 public ne contient pas de Worker Cloudflare : la présente implémentation Cloudflare est propre à T2.

## Parcours canonique

1. `cloudflare/public/app.js` charge `form/questions_T2.json` par `/v1/contracts/form`.
2. Il charge et exécute les douze états stables de `config/T2_capture_flow_v1_0_0.json` par `/v1/contracts/capture-flow`.
3. Le décompte 3–2–1 est transitoire et ne crée pas un treizième écran.
4. Chaque scène demande caméra et microphone, s’arrête automatiquement après 6, 8, 7 ou 9 secondes, puis se relit **avec le son à vitesse 1×**.
5. `REFAIRE` détruit la prise locale. L’acceptation calcule son SHA-256 et l’envoie à R2.
6. Après S4, le Worker lit `music/t2-last-success.json` et impose le successeur exact du dernier succès dans le cycle **A → B → C → D → A**. Sans état, A est obligatoire ; un choix explicite n’est accepté que s’il désigne ce même successeur. Le Worker produit ensuite un `RenderJob` complet `1.1.0` et déclenche `repository_dispatch` sur GitHub.
7. GitHub télécharge les quatre captures avec vérification SHA-256 et valide les médias. Un job commerçant dynamique reconstruit ses 900 images depuis ce même job. Pour l’exemplaire historique explicitement verrouillé, GitHub matérialise plutôt le master de la Release v0.3 et exige à la fois son SHA-256 de fichier et son SHA-256 de flux H.264 avant de mixer voix et musique.
8. Le ducking conserve −3 dB hors parole, −10 dB sous parole, attaque 120 ms et relâchement 450 ms.
9. Le QC indépendant produit `RenderResult` ou `RenderError`, puis GitHub rappelle le Worker. L’état musical est écrit par CAS R2 uniquement après un `COMPLETED` conforme ; un échec ne l’avance jamais.
10. Le client suit `UPLOADING → READY → QUEUED → RUNNING → COMPLETED|FAILED` et ouvre le run GitHub.

## Frontières d’exécution

| Plan | Responsabilités |
|---|---|
| Navigateur | six réponses commerçant, machine à 12 écrans, caméra/micro, relecture, SHA-256 |
| Cloudflare Worker + R2 | authentification pilote, idempotence, stockage, sélection A–D, état transactionnel après succès, RenderJob, dispatch, statuts et callback |
| GitHub Actions | FFmpeg/OpenCV pour les jobs dynamiques, matérialisation verrouillée du master pour l’exemplaire historique, voix 1×, musique sélectionnée, ducking, QC, artefact ou Release |

Cloudflare ne lance ni FFmpeg, ni OpenCV, ni mixage. Tout rendu de production est refusé hors GitHub Actions par le code Python lui-même.

## Voix

Le RenderJob accepte trois modes :

- `registered_voice_clips` — les quatre voix v0.5 verrouillées ;
- `captured_scene_audio` — le son des quatre prises, sans retiming ;
- `captured_or_registered_fallback` — le son capturé lorsqu’il contient une parole exploitable, sinon la voix enregistrée de la même scène.

Dans tous les cas, `source_speed = 1.0` et `audio_time_map = identity`. Aucun sous-titre automatique n’est produit.

Le parcours navigateur demande `captured_or_registered_fallback`. Le garde de parole exige au moins 0,35 s actives et un pic d’au moins −42 dBFS. Le rapport de mix consigne, scène par scène, la source réellement utilisée et la cause éventuelle du fallback.

## Musique

Le pool de production est exactement **A — Naija Flow (300340) / B — Savanna Beats (293956) / C — Vibe Republic (300333) / D — Adolescence (328624)**. La piste D approuvée remplace Afrofire 300338. Les identifiants A/B/C historiques restent dans `music/T2_music_shortlist_v0_4_0.json` avec leur statut Content ID et ne sont jamais promus par le nouveau catalogue.

`config/T2_music_pool_v1_0_0.json` verrouille pour chaque piste la page, l’URL CDN, le SHA-256 et la taille de la source, le contrat de mixage ainsi que l’instrumentale locale de 30 secondes. `auto` est la valeur par défaut. La sélection ne dépend ni d’un hash de job ni d’un tirage : état vide → A, puis A → B, B → C, C → D et D → A. Une sélection explicite différente du successeur attendu est rejetée avant dispatch.

Le Worker conserve l’état conforme à `schemas/T2_music_selection_state.schema.json` dans l’objet R2 `music/t2-last-success.json`. Le registre `successful_render_jobs` associe chaque job déjà validé à sa piste : même après un tour complet, son callback rejoué ne peut donc pas avancer une seconde fois. Les écritures sont conditionnelles sur l’ETag, deux callbacks concurrents ne peuvent pas perdre une mise à jour et un succès hors séquence est refusé. `FAILED` ne crée ni ne modifie cet état.

Les dates et observations de contrôle des pages source sont archivées dans le manifeste et les preuves du pack. L’absence observée de badge Content ID ne constitue pas une garantie juridique absolue. Les sources Pixabay complètes restent hors dépôt et ne sont jamais publiées ; seules les quatre éditions instrumentales propres de 30 secondes, sans voix, sont embarquées comme actifs de production.

## API Worker

### Routes publiques en lecture

- `GET /health`
- `GET /v1/contracts/form`
- `GET /v1/contracts/capture-flow`
- `GET /v1/contracts/music-pool`
- `GET /v1/jobs/{job_id}` — statut sans données commerçant ni média

### Routes client protégées par `CLIENT_API_TOKEN`

- `POST /v1/jobs`
- `PUT /v1/jobs/{job_id}/captures/S1|S2|S3|S4`
- `POST /v1/jobs/{job_id}/dispatch`

`POST /v1/jobs` exige `Idempotency-Key`. Le Worker réserve cette clé par écriture R2 conditionnelle. Le JSON accepte aussi `music_id: "auto"|"A"|"B"|"C"|"D"`; l’absence du champ équivaut à `auto`.

Les captures acceptées sont `video/mp4`, `video/webm` ou `video/quicktime`. Les métadonnées sont déclarées par en-têtes, puis contrôlées de nouveau avec `ffprobe` sur GitHub. R2 vérifie le SHA-256 pendant l’écriture ; GitHub le recalcule après téléchargement.

### Routes GitHub protégées par `CALLBACK_TOKEN`

- `GET /v1/music-state` — état de rotation, sans média ni données commerçant
- `GET /v1/jobs/{job_id}/payload`
- `GET /v1/jobs/{job_id}/captures/{slot}`
- `POST /v1/jobs/{job_id}/events`

Un callback `COMPLETED` doit contenir un `RenderResult` rattaché au bon job avec QC `PASS`. Le Worker recroise aussi le profil, l’URI de sortie, les quatre empreintes de capture et le SHA-256 de la piste sélectionnée avec le RenderJob stocké, puis seulement il valide la nouvelle dernière musique. Un callback `FAILED` doit contenir un `RenderError` rattaché au bon job et laisse l’état musical inchangé.

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

Ce test couvre le formulaire canonique, le contrat des 12 écrans, le pool musical, l’authentification, l’idempotence, MP4/WebM, R2, le RenderJob strict, le dispatch, le téléchargement GitHub, les callbacks invalides/valides, l’échec sans mutation, le conflit concurrent et le cycle complet **A → B → C → D → A**. Il ne produit aucune vidéo locale.

## Rendu de référence unique

Le workflow `.github/workflows/server-render-unified.yml` peut être lancé manuellement sur GitHub. Ce parcours construit désormais un job courant avec `--music auto` et, en l’absence d’un état Cloudflare, vérifie que la première piste est A. Comme la fixture emploie les quatre captures canoniques, le moteur matérialise le master v0.3 de sa Release et vérifie le SHA-256 du fichier et du flux H.264 ; les jobs commerçants Cloudflare reconstruisent au contraire leur propre visuel dynamique. Le workflow vérifie ensuite l’instrumentale locale sélectionnée, exécute les tests et le QC, puis produit une seule vidéo. Il ne fixe plus D/Afrofire comme musique du parcours manuel.

L’option `publish_prerelease` est désactivée par défaut. Le package reproductible contient exactement un MP4, le RenderJob, le RenderResult, les rapports, le contrat de mixage sélectionné, les schémas, le manifeste/provenance musicale et les checksums, mais aucun MP3/WAV ni rush brut. Si la publication est demandée explicitement, le workflow crée une pré-Release additive au tag unique et refuse d’écraser un tag existant. Les jobs Cloudflare utilisent le même workflow par `repository_dispatch`, publient un artefact GitHub privé et rappellent le Worker ; seul ce callback conforme peut faire avancer l’état persistant.
