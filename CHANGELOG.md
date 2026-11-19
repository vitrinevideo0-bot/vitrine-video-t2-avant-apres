# Changelog

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
