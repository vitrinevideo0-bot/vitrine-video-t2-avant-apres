# T2 v0.7 — correction de reproductibilité du master visuel

## Incident privé, sans publication

Le run GitHub Actions privé `44512321062` a été arrêté avant le mixage final parce que le visuel reconstruit présentait le SHA-256 de flux H.264 suivant :

```text
a54b3db5e18aa40cf86f997e7b10b5c3095289c7b046f3f2c1e32551a705697c
```

Le verrou canonique de la Release v0.3 est :

```text
2ed8b3813410df8b9497da7b00877b208bed115038965f73989f00550d3941f5
```

Le garde-fou a fonctionné : aucune Release v0.7 et aucun MP4 final public n’ont été produits.

## Diagnostic

Le run v0.6 réussi `44504063336` avait reconstruit le flux canonique exact sur l’image GitHub `ubuntu-26.04` version `20261116.202.1`. Le run v0.7 en échec a reçu une autre génération de la même famille d’image, version `20261111.196.1`. Les versions Python verrouillées et FFmpeg système consignées dans les deux logs étaient identiques.

Un réencodage H.264 régénéré ne constitue donc pas un moyen portable de rematérialiser, sur n’importe quel runner hébergé, le bitstream exact d’un master déjà approuvé. Le verrou ne doit pas être remplacé par l’empreinte observée et aucun relâchement du contrôle visuel n’est acceptable.

## Correction à sûreté fermée

Pour le seul exemplaire canonique reconnu par ses réponses, ses quatre captures et ses voix enregistrées :

1. GitHub Actions matérialise le MP4 public de la Release historique `t2-avant-apres-v0.3.0-text-motion` ;
2. l’URL, le tag, le nom d’asset et les empreintes sont recroisés entre le RenderJob et le contrat de mix ;
3. le téléchargement est atomique ;
4. le SHA-256 du fichier doit être exactement :
   `67c447dae81241fc9ecc34ee9edfbf8c354a6ddf76e7fa465a62cdac59550ada` ;
5. le SHA-256 du flux H.264 doit être exactement :
   `2ed8b3813410df8b9497da7b00877b208bed115038965f73989f00550d3941f5` ;
6. le média doit rester H.264, 720×1280, 30 i/s, 900 images, sans audio ni sous-titres ;
7. le mix final copie ce flux sans réencodage vidéo.

Toute divergence arrête le workflow avant mixage et publication.

Les jobs commerçants dynamiques ne réutilisent pas ce master fixe : ils continuent à reconstruire leurs propres captures et textes depuis leur RenderJob. La correction ne transforme donc pas le runtime dynamique en vidéo statique.

## Portée historique

Aucune Release historique n’est modifiée ou écrasée. La Release v0.3 sert uniquement de source visuelle approuvée et vérifiée ; v0.5 et v0.6 restent intactes. La publication v0.7 demeure désactivée tant que le MP4 privé corrigé n’a pas été écouté et accepté.
