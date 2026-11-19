# Rapport de rendu — T2 v0.1.0

## Fichier

`output/T2_AVANT_APRES_DEMO_V0_1_0.mp4`

```text
SHA-256 : 0688a821ed0072e2bbb42e46b6fc0b5486ce36d878c116f5d2b0656fbe42ea64
Taille   : 10 752 995 octets
```

## Contrôles observés

| Contrôle | Résultat |
|---|---:|
| largeur × hauteur | 720 × 1280 |
| rapport | 9:16 |
| cadence | 30 i/s |
| images | 900 |
| durée | 30,000 s |
| vidéo | H.264 High, yuv420p |
| audio | AAC LC, 44,1 kHz, stéréo |
| volume moyen FFmpeg | −23,9 dB |
| crête audio FFmpeg | −4,7 dB |
| décodage complet | 900/900 images, aucune erreur |

## Transitions

- six événements de 0,42 s ;
- deux événements par référence ;
- 0,84 s par référence ;
- total : 2,52 s ;
- aucun média issu des références.

La preuve visuelle se trouve dans `proofs/T2_TRANSITIONS_CONTACT_SHEET.jpg`.

## Écrans

`ui-screens/manifest.json` déclare exactement douze écrans `720 × 1280`, dans l’ordre A/B/C pour chacune des quatre scènes. La planche est `ui-screens/T2_PLANCHE_12_ECRANS.png`.

## Rushes

Les quatre SHA-256 source ont été vérifiés avant le rendu. Les fichiers bruts restent exclus du dépôt. Voir `docs/LICENCES_RUSHS.md`.

## Audio

La musique est générée intégralement par code, à 120 BPM, sans sample externe. Cette démo n’imite pas la voix du commerçant ; le contrat de production conserve la voix réellement captée.
