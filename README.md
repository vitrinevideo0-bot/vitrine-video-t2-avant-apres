# Vitrine Vidéo — T2 « Avant / Après »

Dépôt public indépendant pour le gabarit **Restaurants / Maquis — T2**. Le dépôt T1 reste intact et sert uniquement de base technique en lecture seule, verrouillée par `baseline/T1_BASELINE.lock.json`.

## Étape actuelle : validation visuelle silencieuse

- [Télécharger directement la vidéo silencieuse produite sur GitHub Actions](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/download/t2-avant-apres-v0.2.0-silent/T2_AVANT_APRES_TRANSITIONS_SILENT_V0_2_0.mp4)
- [Ouvrir la Release](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.2.0-silent)

Cette version contient uniquement les rushes et les six transitions validées. Elle ne contient **aucune musique, aucune voix, aucun flux audio et aucun texte superposé**.

## Questions commerçant qui alimentent le JSON

1. Comment s’appelle ton restaurant ou ton maquis ?
2. Quel plat allons-nous montrer avant et après ?
3. Quel est le prix de ce plat ?
4. Quel numéro WhatsApp les clients doivent-ils utiliser ?
5. Dans quel quartier peut-on te trouver ?
6. Veux-tu ajouter une petite phrase ? — facultatif.

La définition machine est `form/questions_T2.json`. Les réponses deviennent `merchant_payload.nom`, `merchant_payload.produit`, `merchant_payload.prix`, `merchant_payload.whatsapp`, `merchant_payload.quartier` et `merchant_payload.accroche` dans le RenderJob. Ce nommage et le chemin formulaire → `merchant_payload` → `captures` → rendu reprennent le contrat public T1 verrouillé. Les valeurs sont conservées dès maintenant, mais elles ne sont jamais dessinées pendant l’étape de validation silencieuse.

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
3. exécute les tests ;
4. télécharge les rushes sur le runner GitHub ;
5. rend la vidéo muette sur le runner GitHub ;
6. contrôle l’absence de flux audio ;
7. publie un artefact et une Release GitHub.

Aucun rush brut n’est publié. Aucun rendu local n’est requis.

## Ordre de validation

Références → 12 écrans → montage silencieux → quatre musiques propres au gabarit → choix musical → voix off → mixage → vidéo complète → validation finale.
