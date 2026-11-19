# Rapport QC — intégration T2 Afrofire v0.7

## Conclusion prépublication

**PASS pour l’intégration de code et de contrats.** Aucun rendu vidéo de production n’a été lancé et aucune Release n’a été créée ou remplacée.

La sélection courante est **D — Afrofire · DPStudioMusic**. La piste B reste uniquement dans les contrats et Releases historiques, marquée rejetée pour la production courante.

## Verrou source

- page : `https://pixabay.com/music/afrobeat-afrofire-300338/`
- licence : Pixabay Content License — usage commercial et adaptation permis, attribution non obligatoire, redistribution autonome interdite ;
- source locale d’audition : 7 680 768 octets ;
- SHA-256 : `24e9606e14e4708e8c8ffa3a6a97429dbfc95049d388481392d72b971e932c61` ;
- observation datée du 2026-11-19 : badge AI generated visible, aucun badge Content ID visible ;
- réserve : cette absence de badge n’est pas une garantie juridique absolue ;
- publication autonome : interdite par les contrats et workflows.

Le MP3 source ne fait pas partie du dépôt. Les quatre WAV suivis sont uniquement les voix historiques S1–S4.

## Identité canonique

Le fichier `config/T2_avant_apres_template_v0_1_0.json` contient exactement :

- `template_id: "T2"` ;
- `version: "0.1.0"` ;
- `audio_profile: "afrobeat_restaurants_maquis"`.

Le profil est sémantique : il ne contient ni nom de piste ni extension audio.

## Contrats validés

| Document | SHA-256 |
|---|---|
| `config/T2_music_selection_v0_7_0.json` | `b158d56230eabf1af172a7aede4704a928d9cd4a478cc3848a3adf77977a634c` |
| `schemas/T2_music_selection_v0_7_0.schema.json` | `7cb04782513c63b9617719c71f6d45885ea6373870e34c2341fb95ef85d647ea` |
| `config/T2_complete_voice_mix_v0_7_0.json` | `0f5dd52b4340d34453f212a4b2c4d7dd5760d915525f94d8a3831ee5db021d3e` |
| `schemas/T2_complete_voice_mix_v0_7_0.schema.json` | `fe480135814f12496d87b2a1a1c4e8a5276a6cff02ac1084301df0dd3ce358bc` |
| `config/T2_runtime_contract_v0_7_0.json` | `83e84b59eb0235b7d53c190ff9766a595ddb17053f764e9a67fdd674e1705178` |
| `demo/render_job_complete_demo.json` | `70469c6faea953881be3dce5c5ca4c9e6df3553d7b8d1092e0ad20d383e6cfa2` |

Les deux couples document/schéma v0.7 passent `Draft202012Validator` avec contrôle des formats. Le schéma RenderJob refuse notamment un job D lié au contrat B ou à un autre SHA-256 musical.

## Invariants métier, voix et image

- domaine : `AVANT_APRES` ;
- scènes : 6 / 8 / 7 / 9 s ;
- écrans stables : 12 ;
- sortie visuelle : 720 × 1280, 30 i/s, 900 images, 30 s ;
- flux H.264 de référence : `2ed8b3813410df8b9497da7b00877b208bed115038965f73989f00550d3941f5` ;
- six réponses commerçant et liaisons scène/capture inchangées ;
- quatre voix inchangées, vitesse `1×`, time map identité ;
- ducking : −3 dB / −10 dB, attaque 120 ms, relâchement 450 ms ;
- visuel v0.3 et composants graphiques verrouillés ;
- contrats historiques v0.5/v0.6 byte-identiques.

Le contrôle visuel autorise une seule différence dans le JSON canonique : l’ajout non visuel de `audio_profile`. La suppression de cette clé reconstruit exactement le SHA-256 historique du contrat visuel.

## Résultats des contrôles locaux

| Contrôle | Résultat |
|---|---|
| `python tools/validate_contract.py` | PASS |
| verrou des quatre tests pré-v0.6 | PASS, byte-identiques |
| `python tools/verify_visual_pipeline.py` | PASS, 11 composants et flux H.264 verrouillés |
| reconstruction des RenderJobs silencieux, textes et D/Afrofire | PASS, fixtures reproductibles |
| compatibilité explicite du RenderJob historique B | PASS |
| génération des trois contrats Cloudflare | PASS, reproductible sans dérive |
| suite Python | PASS, 58/58 |
| TypeScript Cloudflare | PASS |
| `npm audit --audit-level=low` | PASS, 0 vulnérabilité |
| dry-build Wrangler 4.165.0 avec Node 22.12.0 | PASS |
| intégration Worker/R2/dispatch/callback | PASS, y compris rejet d’un résultat portant un mauvais SHA musical |
| actionlint 1.7.12 sur les sept workflows | PASS |
| `git diff --check` | PASS |

## Frontières de validation

Ce rapport valide les JSON, schémas, moteurs, adaptateurs, contrats générés, plan de contrôle, workflows et invariants visuels. Conformément à la consigne, il ne prétend pas valider un nouveau MP4, des mesures LUFS/dBTP issues d’un nouveau rendu ou une écoute humaine : aucun nouveau rendu n’a été demandé ni exécuté.

Tout futur rendu complet reste bloqué hors GitHub Actions. La publication de Release est désactivée par défaut, refuse les fichiers audio autonomes et refuse d’écraser un tag existant.
