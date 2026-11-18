# Changelog

## 1.0.0 — instrumentales propres et cycle strict

- remplacement de la piste D Afrofire 300338 par la piste approuvée 328624 ;
- quatre instrumentales propres de 30 secondes embarquées, sans voix d’audition ;
- recalage validé de 328624 à 1,83 s dans la source originale ;
- rotation persistante stricte A → B → C → D → A, avancée uniquement après succès/QC validé ;
- registre persistant `successful_render_jobs` : rejeu idempotent même après un tour complet, échec sans mutation et rejet des commits concurrents hors cycle ;
- contrats Python, Cloudflare, schémas, provenance et tests mis à jour.

## 0.7.0 — préparation Afrofire approuvée

- remplacement de la sélection courante B rejetée par le candidat existant D — **Afrofire · DPStudioMusic** ;
- preuve stricte de page, licence Pixabay, taille `7 680 768` octets et SHA-256 `24e9606e14e4708e8c8ffa3a6a97429dbfc95049d388481392d72b971e932c61` ;
- observation datée : badge AI generated visible et aucun badge Content ID visible le 2026-11-19, sans en faire une garantie juridique absolue ;
- ajout de `audio_profile: afrobeat_restaurants_maquis` au JSON canonique, sans changer `template_id: T2` ni la version de gabarit `0.1.0` ;
- nouveaux contrats additifs de sélection, mix et runtime v0.7 ; contrats historiques v0.5/v0.6 conservés octet pour octet ;
- RenderJob, schéma strict, fixture, Cloudflare et workflow courant corrélés au candidat D ;
- quatre voix `1×`, scènes 6/8/7/9 s, douze écrans, visuel v0.3, 900 images et ducking −3/−10 dB préservés ;
- refus de publier une source audio autonome et refus d’écraser une Release existante ;
- aucun nouveau rendu vidéo ni aucune Release créé par cette intégration de code.

## 0.6.0 — runtime unifié T2 et plan de contrôle Cloudflare

- application mobile exécutable alimentée par les six questions et le contrat canonique des douze écrans ;
- caméra + microphone, décompte transitoire, auto-stop 6/8/7/9 s, relecture sonore 1×, `REFAIRE` et acceptation ;
- Worker Cloudflare + R2 : authentification pilote, idempotence, SHA-256, statuts, dispatch GitHub et callbacks ;
- RenderJob complet `1.1.0` reliant commerçant, captures, visuel, voix, musique B, ducking et publication ;
- trois modes voix, dont fallback par scène lorsque la prise ne contient aucune parole exploitable ;
- formats caméra MP4, WebM et QuickTime, revalidés avec `ffprobe` sur GitHub ;
- rendu, FFmpeg, mixage et QC toujours exclusivement sur GitHub Actions ;
- contrats stricts `RenderResult` et `RenderError` ;
- verrou du pipeline visuel v0.3 et preuve des 900 images, tout en gardant les données commerçant dynamiques ;
- intégrité visuelle bloquée sur le flux H.264 copié bit à bit ; empreinte du conteneur MP4 conservée comme provenance non visuelle ;
- 53 tests Python, test d’intégration Worker/R2 et dry-build Wrangler ;
- tests préexistants conservés octet pour octet ; T1 reste intact en lecture seule.

## 0.5.0 — exemplaire complet voix française + musique B

- choix utilisateur B enregistré pour cet exemplaire unique, sans créer de défaut musical T2 ;
- quatre exemples vocaux S1–S4 avec une seule identité française, à vitesse 1× ;
- stem voix continu de 30 s et placement 1,20 / 6,80 / 14,70 / 21,80 s ;
- architecture audio T1 verrouillée par commit et SHA-256, sans aucune modification de T1 ;
- musique −3 dB hors parole et −10 dB sous parole, attaque 120 ms, relâchement 450 ms ;
- master −16 LUFS / −2 dBTP, AAC stéréo 48 kHz à 192 kb/s ;
- flux vidéo v0.3 copié sans réencodage et contrôlé bit à bit ;
- rapport de niveaux, rapport parole/musique par scène, automation CSV et validation indépendante ;
- production et publication exclusivement sur GitHub Actions ;
- exactement un MP4 public, aucun MP3/WAV/stem autonome publié ;
- avertissement Content ID de la piste B conservé dans le contrat et la Release.

## 0.4.0 — quatre auditions musicales Afrobeat

- quatre pages Pixabay et leur licence vérifiées dans un manifeste public ;
- quatre MP4 d’audition de 30 secondes sur le montage v0.3 validé ;
- flux vidéo v0.3 copié bit à bit, sans changer textes, police, mouvements ni vitesse ;
- aucun MP3 source redistribué de façon autonome ;
- badges Content ID consignés avant le choix ;
- aucune musique finale sélectionnée automatiquement ;
- futur ducking réservé pour garder les voix intelligibles à vitesse 1× ;
- construction, validation et publication exclusivement sur GitHub Actions.

## 0.3.0 — textes dynamiques liés aux scènes

- six réponses commerçant liées à quatre blocs graphiques S1 à S4 ;
- police calligraphique Pinyon Script incorporée et verrouillée ;
- un RenderJob réunit `merchant_payload`, `captures` et sortie ;
- tests de pixels prouvant que les changements de données changent réellement les images ;
- timeline caméra/voix à 1,0× réservée pour le futur mixage ;
- rendu et publication exclusivement sur GitHub Actions ;
- contrôle actuel encore sans musique ni voix.

## 0.2.0 — correction de phase

- rendu déplacé intégralement sur GitHub Actions ;
- vidéo de validation rendue muette, sans flux audio ;
- suppression de tous les textes superposés du montage ;
- questions commerçant formalisées séparément ;
- mécanisme aligné sur le contrat T1 public : réponses → `merchant_payload` + quatre `captures` → RenderJob ;
- base T1 publique verrouillée en lecture seule ;
- suppression du moteur musical prématuré et de la première vidéo sonore.

## 0.1.0

- première exploration des six transitions ; version remplacée car elle contenait un son et des textes non autorisés.
