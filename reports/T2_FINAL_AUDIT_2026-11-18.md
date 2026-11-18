# T2 — audit final local de la rotation musicale v1

Date : 2026-11-18
Portée : intégration locale uniquement — aucun déploiement Cloudflare, aucune Release et aucun push effectués au moment de cet audit.

## Résultat

**PASS** — le runtime courant applique exclusivement le cycle :

`A (300340) → B (293956) → C (300333) → D (328624) → A`

- état initial : A ;
- chaque succès avec QC `PASS` impose exactement le successeur ;
- un choix explicite hors séquence est rejeté avant dispatch ;
- `FAILED` ne modifie pas l’état ;
- le registre persistant `successful_render_jobs` rend tout rejeu idempotent, y compris après un tour complet ;
- deux callbacks concurrents pour le même successeur produisent un seul commit et un conflit HTTP 409 ;
- les quatre actifs sont des instrumentales locales propres de 30,000 s, sans voix, vérifiées par SHA-256 ;
- les contrats historiques B et D/Afrofire restent séparés et inchangés.

## Validations exécutées

- `python -m unittest discover -s tests -v` : **68 tests PASS** ;
- tests historiques antérieurs à v0.6 : quatre fichiers byte-identiques ;
- verrou du pipeline visuel : **PASS**, flux H.264 `2ed8b3813410df8b9497da7b00877b208bed115038965f73989f00550d3941f5` ;
- compilation Python, validation des schémas JSON, JSON complet et contrats générés sans dérive : **PASS** ;
- TypeScript `tsc --noEmit` et `node --check cloudflare/public/app.js` : **PASS** ;
- `npm audit --audit-level=low` : **0 vulnérabilité** ;
- checksums stricts du pack musical : **PASS** ;
- Wrangler **4.165.0** sous Node 24, `deploy --dry-run` : **PASS**, 72,37 KiB / gzip 16,28 KiB et bindings attendus ;
- intégration Worker/R2 locale : **`T2_CLOUDFLARE_CONTROL_PLANE_STRICT_ROTATION_OK A→B→C→D→A`** ;
- YAML des workflows, `git diff --check` et politique sans audio autonome : **PASS**.

## Rendu réel du candidat courant

Le parcours manuel courant a construit `--music auto` sans état préalable et a donc sélectionné A.

- RenderJob : `t2-complete-ad87b17c6316ec07` ;
- idempotency key : `t2-avant-apres-v1.0.0-music-rotation-ad87b17c6316ec07` ;
- fichier : `VIDEO_T2_COMPLET_VOIX_MUSIQUE_A_NAIJA_FLOW.mp4` ;
- taille : **10 461 395 octets** ;
- SHA-256 : `2c4f93373833aba55db38cbca7597400e971da8e3c4b3d648731a2b5f81f9422` ;
- image : 720 × 1280, 30 i/s, 900 images, 30,000 s ;
- audio : AAC stéréo 48 kHz, **−16,13 LUFS**, **−1,99 dBTP**, zéro clipping ;
- intelligibilité parole/musique : **10,07 dB** ;
- RenderResult : `COMPLETED`, qualité `PASS`, aucun audio autonome.

Le visuel canonique v0.3 a été matérialisé depuis sa Release et ses empreintes de fichier et de flux ont été vérifiées avant le mixage.

## Package local

Répertoire ignoré par Git : `release/`

- 22 fichiers au total ;
- exactement un MP4 ;
- RenderJob, RenderResult, rapports QC, contrat de mixage sélectionné, pool, runtime, schémas, approbation, manifeste et provenance ;
- aucun MP3, WAV, M4A, AAC, FLAC, OGG, OPUS, MOV ou WebM ;
- taille du répertoire : **10 698 093 octets** ;
- SHA-256 de `release/SHA256SUMS.txt` : `ade80fa9a632cb091adb2f70e50c45e9482d572da7f1693a25a8f3df194eae89` ;
- `sha256sum --check --strict release/SHA256SUMS.txt` : **PASS**.

## Limites de cet audit

- aucune CI distante n’a encore été observée pour ces modifications ;
- aucun Worker ni bucket de production n’a été modifié ;
- aucune Release n’a été créée ;
- le rendu local a reproduit l’environnement GitHub Actions uniquement pour valider le candidat, sans publication.
