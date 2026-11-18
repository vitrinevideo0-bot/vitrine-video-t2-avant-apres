# T2 — exemplaire historique complet voix française + musique B

> **Archive v0.5.** Cette ancienne piste B reste rejetée en raison de son badge Content ID Registered. D — Afrofire lui a succédé dans l’exemplaire historique v0.7, puis le runtime courant v1 l’a remplacée par le pool final `300340 → 293956 → 300333 → 328624`. Les Releases historiques ne sont pas modifiées.

## Portée historique

La v0.5 produit **un seul MP4 complet de 30 secondes** pour l’écoute de l’équilibre voix/musique. Elle ne modifie ni les 900 images, ni les textes dynamiques, ni la police, ni les mouvements du montage v0.3 validé.

La piste **B — Afro Pop Vlog Sunshine · alex-morgan** a été choisie explicitement pour cet exemplaire. Ce choix reste limité à cette vidéo de validation et ne devient pas une musique par défaut du gabarit T2. Sa page Pixabay affiche le statut **Content ID Registered**.

## Quatre voix, un stem

Une seule identité vocale française (`voice-01`, masculine, publicitaire) prononce les quatre exemples exacts de `capture-guide/consignes_T2.json`.

| Scène | Fenêtre | Départ voix | Texte |
|---|---:|---:|---|
| S1 | 0–6 s | 1,20 s | Voici le poulet, l'alloco et les épices avant la préparation. |
| S2 | 6–14 s | 6,80 s | Regardez, nous retournons le poulet sur le feu pour bien le griller. |
| S3 | 14–21 s | 14,70 s | Voilà notre poulet braisé avec alloco, le plat est prêt ! |
| S4 | 21–30 s | 21,80 s | Notre poulet braisé avec alloco est prêt. Venez goûter ! |

Les prises restent à vitesse `1×`, sans time-stretch et sans sous-titres. GitHub Actions les normalise individuellement, puis les place dans un stem mono de 1 440 000 échantillons, soit exactement 30 s à 48 kHz.

## Architecture audio copiée de T1

La référence publique T1 est verrouillée au commit `c656510ab81d31d413dc4dfd74b42671532cd978`. Les quatre fichiers structurants T1 sont contrôlés par SHA-256 via `baseline/T1_AUDIO_REFERENCE.lock.json` avant chaque production.

Le contrat repris est :

- programme musical préparé à −17 LUFS ;
- musique à **−3 dB** hors parole ;
- musique à **−10 dB** sous chaque prise ;
- profondeur de ducking **−7 dB** ;
- attaque **120 ms**, relâchement **450 ms**, courbes linéaires en dB ;
- voix à **0 dB** ;
- aucun SFX ;
- master **−16 LUFS**, plafond WAV **−2 dBTP** ;
- livraison AAC stéréo 48 kHz, cible 192 kb/s.

L’enveloppe est calculée d’après la durée réelle de chaque prise normalisée. La baisse commence 120 ms avant le premier échantillon de parole et la remontée s’achève 450 ms après la fin de la prise.

## Contrôles publiés

Le workflow `.github/workflows/server-render-complete-voice.yml` :

1. clone T1 au commit canonique, en lecture seule, et vérifie ses quatre empreintes audio ;
2. compile et exécute toute la suite de tests T2 ;
3. télécharge temporairement le MP4 visuel v0.3 et la source officielle Pixabay B ;
4. vérifie le SHA-256 du conteneur et du flux vidéo v0.3 ;
5. construit le stem voix, le programme musical, le ducking et le master sur le runner ;
6. copie le flux vidéo sans réencodage et encode uniquement l’AAC ;
7. mesure LUFS, dBTP, écrêtage, débit, durée et rapport parole/musique par scène ;
8. effectue une deuxième validation indépendante ;
9. publie exactement un MP4, les rapports JSON/Markdown, l’automation CSV, le graphique et les checksums.

Aucun MP3 source Pixabay, WAV voix, stem voix ou master WAV autonome n’est publié dans la Release.

## Livrable

- Release : `t2-avant-apres-v0.5.0-complete-voice-mix`
- MP4 : `VIDEO_T2_COMPLET_VOIX_MUSIQUE_B_A_VALIDER.mp4`
- Rapport lisible : `RAPPORT_NIVEAUX_T2.md`
- Rapport machine : `T2_VOICE_MUSIC_LEVELS_VALIDATION_V0_5_0.json`
- Validation indépendante : `T2_GITHUB_SERVER_VALIDATION_V0_5_0.json`

L’approbation créative finale reste une écoute humaine de l’unique MP4.
