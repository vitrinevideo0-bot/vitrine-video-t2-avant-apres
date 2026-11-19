# Vitrine Vidéo — T2 « Avant / Après »

Dépôt public indépendant pour le gabarit **Restaurants / Maquis — T2**. Le dépôt T1 reste intact et sert uniquement de base technique en lecture seule, verrouillée par `baseline/T1_BASELINE.lock.json`.

## Étape actuelle : validation des textes dynamiques

- [Télécharger le test des textes produit sur GitHub Actions](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/download/t2-avant-apres-v0.3.0-text-motion/T2_AVANT_APRES_TEXTES_DYNAMIQUES_V0_3_0.mp4)
- [Ouvrir la Release des textes](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.3.0-text-motion)
- [Conserver le montage silencieux v0.2 comme référence visuelle validée](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.2.0-silent)

La v0.3 conserve le montage validé et ajoute les six informations commerçant avec leur motion design. Le nom utilise la police calligraphique **Pinyon Script**, choisie d’après la capture fournie. Cette étape reste sans musique et sans voix uniquement pour valider les textes avant le mixage.

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

Le workflow `.github/workflows/server-render-silent.yml` :

1. vérifie la base T1 publique sans la modifier ;
2. construit et valide le RenderJob à partir des réponses et des quatre captures ;
3. teste les liaisons formulaire → textes → scènes, les durées caméra et la timeline de future voix ;
4. télécharge les rushes sur le runner GitHub ;
5. rend transitions et textes dynamiques sur le runner GitHub ;
6. contrôle les quatre blocs graphiques et l’absence de flux audio à cette étape ;
7. publie le MP4, la planche de police, les preuves JSON et le RenderJob dans une Release GitHub.

Aucun rush brut n’est publié. Aucun rendu local n’est requis.

## Ordre de validation

Références → 12 écrans → montage silencieux → quatre musiques propres au gabarit → choix musical → voix off → mixage → vidéo complète → validation finale.
