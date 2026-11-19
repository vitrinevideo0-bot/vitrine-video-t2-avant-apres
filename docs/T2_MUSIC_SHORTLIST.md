# T2 — présélection musicale Afrobeat v0.4

## But

Comparer quatre couleurs Afrobeat sur **le même montage T2 v0.3 validé**, pendant exactement 30 secondes, avant tout choix définitif. Les quatre auditions sont produites sur GitHub Actions; aucune production locale n'est autorisée.

## Propositions

| Choix | Morceau Pixabay | Auteur | Couleur | Content ID affiché sur la page |
|---|---|---|---|---|
| A | Afrobeat Music - Feelgood Groove | MusicInMedia | chaleureux, gourmand, lounge/bar/cooking | oui |
| B | Afro Pop Vlog Sunshine | alex-morgan | solaire, léger, vertical/social | oui |
| C | Amapiano Beats Log Drum Groove | alex-morgan | moderne, profond, log drum | oui |
| D | Afrofire | DPStudioMusic | énergique, cuivres, publicité | non affiché lors de la vérification |

Les pages officielles, URLs de source, durées, dates, mots-clés et statuts sont verrouillés dans `music/T2_music_shortlist_v0_4_0.json`. La vérification a été faite le 18 novembre 2026.

## Licence et publication

Les quatre pages indiquent une utilisation sous la [Pixabay Content License](https://pixabay.com/service/license-summary/). La licence permet l'utilisation gratuite, sans attribution obligatoire, et l'adaptation dans une nouvelle œuvre; elle interdit la redistribution du contenu seul, sans effort créatif.

En conséquence :

- les MP3 Pixabay ne sont jamais publiés dans le dépôt, l'artefact ou la Release;
- seul un MP4 dérivé est publié pour chaque choix, en associant la musique au montage T2 validé;
- la page officielle et l'auteur restent consignés dans le manifeste et la preuve serveur;
- les trois badges Content ID visibles sont signalés avant le choix final.

## Garantie visuelle

Le workflow télécharge le MP4 v0.3 public et vérifie son SHA-256 canonique. Le flux vidéo est copié bit à bit (`-c:v copy`) dans chacune des quatre auditions. Un hash du flux élémentaire prouve que les 900 images, la cadence 30 i/s, les dimensions 720 × 1280, les textes, la police et les mouvements ne changent pas.

## Audio actuel et futur

Les auditions contiennent uniquement la musique, normalisée de façon identique pour comparer les morceaux. Elles ne constituent pas le mix final.

Après le vote A/B/C/D :

- les prises et les voix restent à vitesse 1×;
- le remappage caméra et audio reste à l'identité;
- la musique s'abaisse automatiquement lorsque quelqu'un parle;
- aucun sous-titre automatique n'est ajouté;
- un nouveau rendu complet devra repasser les validations GitHub.
