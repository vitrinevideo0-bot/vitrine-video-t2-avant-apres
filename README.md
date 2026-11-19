# Vitrine Vidéo — T2 « Avant / Après »

Gabarit pilote **Restaurants / Maquis** : quatre prises commerçant, douze écrans de capture et un montage vertical original de 30 secondes.

> **Dépôt indépendant.** T2 possède son propre moteur et son propre historique. Le dépôt public T1 n’est ni une branche ni une dépendance modifiée : il reste une référence en lecture seule.

## Télécharger immédiatement la vidéo de démonstration

- [Téléchargement MP4 direct — 720 × 1280, 30 s](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/download/t2-avant-apres-v0.1.0-demo/T2_AVANT_APRES_DEMO_V0_1_0.mp4)
- [Page de la Release et preuves](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.1.0-demo)

SHA-256 attendu :

```text
0688a821ed0072e2bbb42e46b6fc0b5486ce36d878c116f5d2b0656fbe42ea64
```

Cette première vidéo sert à valider le **rythme**, les **six transitions** et la **dynamique générale**. Les quatre rushes sont des médias de démonstration sous licence Pexels ; ils ne remplacent pas les vraies prises d’un commerçant.

## Contrat T2

| Élément | Valeur verrouillée |
|---|---:|
| format | vertical 9:16 |
| sortie | 720 × 1280, 30 i/s |
| durée | 30,000 s / 900 images |
| scènes | exactement 4 |
| durées | 6 s · 8 s · 7 s · 9 s |
| états de capture | A Guide · B Enregistrement · C Validation |
| écrans stables | exactement 12 |
| transitions | 6 × 0,42 s |
| équilibre | 0,84 s par référence, soit un tiers chacune |
| parole | facultative, dans toute langue maîtrisée |
| voix commerçant | conservée en production |
| sous-titres automatiques | non |

## Les quatre scènes

1. **L’AVANT — 6 s** : montrer le plat ou les ingrédients avant la préparation.
2. **LA TRANSFORMATION — 8 s** : filmer un geste complet de préparation.
3. **LA RÉVÉLATION — 7 s** : découvrir le plat puis le laisser visible.
4. **L’APRÈS — 9 s** : servir ou présenter le résultat final.

Les textes simples destinés au commerçant sont dans [`capture-guide/consignes_T2.json`](capture-guide/consignes_T2.json).

La planche des douze états est dans [`ui-screens/T2_PLANCHE_12_ECRANS.png`](ui-screens/T2_PLANCHE_12_ECRANS.png) et leur ordre contractuel dans [`docs/CONTRAT_12_ECRANS.md`](docs/CONTRAT_12_ECRANS.md).

## Origine des transitions

Seul le **langage de mouvement** des trois références validées a été étudié :

1. volets et occultations obliques ;
2. expansion centrée et balayage couleur ;
3. bandes décalées et flash chaud.

Aucun JSON CapCut, média, texte, logo, identité, plan ou keyframe propriétaire n’a été copié. Les six transitions du moteur sont des implémentations originales décrites dans [`docs/REFERENCES_TRANSITIONS.md`](docs/REFERENCES_TRANSITIONS.md).

## Reproduire la démonstration

Prérequis : Python 3.13 et un environnement capable d’installer les dépendances.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python tools/validate_contract.py
python -m unittest discover -s tests -v
python tools/fetch_rushes.py
python engine/render_t2.py --job demo/input_demo.json
python tools/generate_ui_screens.py
```

Les rushes téléchargés restent dans `rushes/cache/`, ignoré par Git. Le dépôt ne redistribue pas les fichiers stock bruts.

## Arborescence utile

```text
capture-guide/   textes des quatre guides
config/          contrat du gabarit et chronologie
engine/          lecteur, transitions, habillage, musique et encodeur
demo/            RenderJob de démonstration
docs/            architecture, références, licences et rapport
output/          MP4 de démonstration
proofs/          manifeste, planche de transitions et contrôles FFmpeg
rushes/          manifeste de sources, sans rush brut publié
schemas/         schéma du RenderJob
tests/           tests du contrat
ui-screens/      douze captures stables et planche 4 × 3
```

## Limite du pilote

Le dépôt livre un **moteur Python de référence et des preuves visuelles**. Il ne prétend pas encore être une application Android Media3 finalisée. Une implémentation mobile devra reproduire le contrat, les douze états et les transitions après validation humaine de cette vidéo.

## Licences

- code original : MIT ;
- Playfair Display : SIL Open Font License 1.1 ;
- DejaVu Sans : licence incluse dans `assets/fonts/DEJAVU-LICENSE.txt` ;
- rushes de démonstration : Pexels License, détails dans [`docs/LICENCES_RUSHS.md`](docs/LICENCES_RUSHS.md).
