# Vitrine Vidéo — T2 « Avant / Après »

Dépôt public indépendant pour le gabarit **Restaurants / Maquis — T2**. Le dépôt T1 reste intact et sert uniquement de base technique en lecture seule, verrouillée par `baseline/T1_BASELINE.lock.json`.

## Étape actuelle : quatre auditions musicales Afrobeat

Le montage T2 v0.3, ses textes, sa police et ses mouvements sont validés. La v0.4 compare maintenant quatre musiques, sans choisir ni modifier définitivement la base visuelle.

- [Ouvrir la Release des quatre auditions](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.4.0-music-shortlist)
- [A — Feelgood Groove · chaleureux et gourmand](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/download/t2-avant-apres-v0.4.0-music-shortlist/T2_MUSIC_A_FEELGOOD_GROOVE_AUDITION_30S.mp4)
- [B — Afro Pop Sunshine · solaire et léger](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/download/t2-avant-apres-v0.4.0-music-shortlist/T2_MUSIC_B_AFRO_POP_SUNSHINE_AUDITION_30S.mp4)
- [C — Amapiano Log Drum · moderne et profond](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/download/t2-avant-apres-v0.4.0-music-shortlist/T2_MUSIC_C_AMAPIANO_LOG_DRUM_AUDITION_30S.mp4)
- [D — Afrofire · énergique et premium](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/download/t2-avant-apres-v0.4.0-music-shortlist/T2_MUSIC_D_AFROFIRE_AUDITION_30S.mp4)
- [Conserver le rendu v0.3 validé comme base](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.3.0-text-motion)

Chaque audition reprend exactement les 900 images de la v0.3 et ajoute uniquement une musique de comparaison. Les MP3 Pixabay ne sont pas redistribués seuls. Aucune musique n'est définitive avant le vote A/B/C/D.

## Questions commerçant qui alimentent le JSON

1. Comment s’appelle ton restaurant ou ton maquis ?
2. Quel plat allons-nous montrer avant et après ?
3. Quel est le prix de ce plat ?
4. Quel numéro WhatsApp les clients doivent-ils utiliser ?
5. Dans quel quartier peut-on te trouver ?
6. Veux-tu ajouter une petite phrase ? — facultatif.

La définition machine est `form/questions_T2.json`. Les réponses deviennent `merchant_payload.nom`, `merchant_payload.produit`, `merchant_payload.prix`, `merchant_payload.whatsapp`, `merchant_payload.quartier` et `merchant_payload.accroche` dans le RenderJob. Ce nommage et le chemin formulaire → `merchant_payload` → `captures` → rendu reprennent le contrat public T1 verrouillé. Les valeurs sont maintenant dessinées dynamiquement dans S1 à S4 selon `config/T2_runtime_contract_v0_3_0.json`.

## Contrat

- quatre scènes : 6 s · 8 s · 7 s · 9 s ;
- douze écrans stables : quatre scènes × A Guide / B Enregistrement / C Validation ;
- 720 × 1280, 30 i/s, 900 images, 30,000 s ;
- six transitions de 0,42 s ;
- deux transitions et 0,84 s par référence ;
- parole facultative dans toute langue maîtrisée ;
- aucun sous-titre automatique.

## Tout se fait sur GitHub

Les workflows GitHub conservent le rendu v0.3 et ajoutent la présélection v0.4 :

1. `.github/workflows/server-render-text-motion.yml` conserve la vidéo v0.3 validée ;
2. `.github/workflows/server-build-music-shortlist.yml` vérifie T1 en lecture seule et le SHA-256 de la v0.3 ;
3. télécharge quatre sources officielles Pixabay uniquement dans le runner éphémère ;
4. copie le flux visuel v0.3 sans réencodage et crée quatre MP4 d’audition ;
5. prouve que les 900 images sont identiques et qu’aucun MP3 source n’est publié ;
6. publie les quatre auditions, le manifeste de licence et les preuves dans une Release GitHub.

Aucun rush brut n’est publié. Aucun rendu local n’est requis.

## Ordre de validation

Références → 12 écrans → montage silencieux → quatre musiques propres au gabarit → choix musical → voix off → mixage → vidéo complète → validation finale.
