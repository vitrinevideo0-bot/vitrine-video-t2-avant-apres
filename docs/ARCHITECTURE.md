# Architecture du pilote T2

## Sources de vérité

1. `config/T2_avant_apres_template_v0_1_0.json` — chronologie, format, champs et transitions ;
2. `capture-guide/consignes_T2.json` — textes commerçant ;
3. `schemas/render_job.schema.json` — entrée de rendu ;
4. `rushes/manifest.json` — médias de démonstration, segments et empreintes ;
5. `engine/` — implémentation Python de référence.

## Pipeline

```text
RenderJob
  → contrôle des six champs
  → vérification SHA-256 des quatre rushes
  → lecture monotone et recadrage 9:16
  → étalonnage chaud modéré
  → 6 transitions originales
  → habillage Playfair Display condensé à 66 %
  → 900 images MP4 intermédiaires
  → musique originale générée à 120 BPM
  → encodage H.264 High + AAC, yuv420p, faststart
  → manifeste de preuve
```

## Capture

Le contrat possède exactement quatre scènes et trois états stables par scène :

- A — Guide ;
- B — Enregistrement ;
- C — Validation.

Le décompte `3 · 2 · 1` est transitoire. Il n’existe ni cinquième scène ni treizième écran stable.

## Audio

Le pilote de démonstration utilise une musique synthétisée par `engine/audio.py`, sans échantillon tiers. Dans l’application de production :

- la parole reste facultative ;
- le microphone reste actif ;
- la voix réellement enregistrée doit être conservée ;
- aucun sous-titre automatique n’est ajouté.

## Limites

Ce moteur Python prouve le contrat et la recette visuelle. Il ne constitue pas encore un composant Android Media3 qualifié hors ligne.
