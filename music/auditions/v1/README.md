# Auditions musicales T2 — remplacement de A/B/C

**Instantané d’audition historique.** Le statut `audition_only_no_selection` ci-dessous décrit le paquet au moment de sa génération. Il a depuis été remplacé par la décision explicite `approvals/T2_MUSIC_POOL_APPROVAL_2026-11-18.json` : **A, B et C sont approuvées avec D**. Le manifeste d’audition n’est pas réécrit rétroactivement.

Ce paquet compare quatre extraits de 30 secondes avec exactement les mêmes voix T2, placements, fondus, normalisation et ducking. **D — Afrofire reste la piste historiquement conservée.**

## Écoute

1. `T2_AUDITION_A_NAIJA_FLOW.m4a` — **Naija Flow**, DPStudioMusic
2. `T2_AUDITION_B_SAVANNA_BEATS.m4a` — **Savanna Beats**, DPStudioMusic
3. `T2_AUDITION_C_VIBE_REPUBLIC.m4a` — **Vibe Republic**, DPStudioMusic
4. `T2_AUDITION_D_AFROFIRE.m4a` — **Afrofire**, DPStudioMusic (témoin conservé)

## Comparabilité verrouillée

- durée : 30,000 s chacune ;
- même début de source : 0,0 s ;
- mêmes quatre WAV de voix et même cadence (aucun retiming) ;
- programme musical : cible −17 LUFS ;
- mix final : cible −16 LUFS, AAC stéréo 48 kHz / 192 kb/s ;
- musique ouverte : −3 dB ; sous la voix : −10 dB ;
- attaque/release du ducking : 120/450 ms ;
- fondus : 0,35/0,80 s.

Les mesures AAC observées vont de **−16,12 à −16,19 LUFS**, ce qui rend le vote comparable sans avantage de volume significatif.

## Pages et contrôle Content ID observé le 19 novembre 2026

| ID | Piste | Page officielle | Observation de page |
|---|---|---|---|
| A | Naija Flow | https://pixabay.com/music/afrobeat-naija-flow-300340/ | Badge « AI generated » affiché ; badge « Content ID Registered » non affiché |
| B | Savanna Beats | https://pixabay.com/music/afrobeat-savanna-beats-293956/ | Badge « AI generated » affiché ; badge « Content ID Registered » non affiché |
| C | Vibe Republic | https://pixabay.com/music/afrobeat-vibe-republic-300333/ | Badge « AI generated » affiché ; badge « Content ID Registered » non affiché |
| D | Afrofire | https://pixabay.com/music/afrobeat-afrofire-300338/ | Badge « AI generated » affiché ; badge « Content ID Registered » non affiché |

Les quatre pages affichent « Free for use under the Pixabay Content License ». L’absence de badge Content ID est une **observation datée**, pas une garantie juridique permanente. Pixabay recommande de conserver la page, le nom du fichier et les preuves de téléchargement ; ces éléments et les SHA-256 sont consignés dans `T2_AUDITIONS_MANIFEST.json`.

## Décision reçue

Le propriétaire a choisi **« approuver A/B/C avec D »**. L’activation machine est décrite séparément dans `config/T2_music_pool_v1_0_0.json`, afin de préserver ce paquet comme preuve d’audition et de ne jamais confondre décision créative, provenance et statut Content ID historique.
