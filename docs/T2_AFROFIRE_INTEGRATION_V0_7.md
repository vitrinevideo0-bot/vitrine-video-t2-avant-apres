# T2 — intégration Afrofire v0.7

## Décision

La piste historique **B — Afro Pop Vlog Sunshine** est rejetée pour la production courante parce que sa page Pixabay affiche **Content ID Registered**.

La sélection explicitement approuvée pour T2 est le candidat existant **D — Afrofire · DPStudioMusic**. Il ne s’agit ni d’un renommage de B, ni d’un choix musical implicite du gabarit.

Le gabarit canonique conserve :

```json
{
  "template_id": "T2",
  "version": "0.1.0",
  "audio_profile": "afrobeat_restaurants_maquis"
}
```

`version` décrit le gabarit visuel. `audio_profile` décrit une ambiance et ne contient jamais un nom de MP3 ou de piste.

## Provenance et droits observés

| Champ | Valeur |
|---|---|
| Titre | Afrofire |
| Auteur | DPStudioMusic |
| Candidat catalogue | D |
| Page Pixabay | https://pixabay.com/music/afrobeat-afrofire-300338/ |
| Source CDN | https://cdn.pixabay.com/download/audio/2025/02/12/audio_bf52f1c5ad.mp3?filename=dpstudiomusic-afrofire-300338.mp3 |
| Licence affichée | Pixabay Content License |
| Résumé de licence | https://pixabay.com/service/license-summary/ |
| Taille vérifiée | 7 680 768 octets |
| SHA-256 vérifié | `24e9606e14e4708e8c8ffa3a6a97429dbfc95049d388481392d72b971e932c61` |
| Badge AI generated | visible |
| Badge Content ID | aucun badge visible lors de la vérification datée du 2026-11-19 |
| Publication de la source seule | interdite par le contrat T2 |

Le résumé de licence observé autorise l’usage commercial et l’adaptation sans attribution obligatoire, mais interdit la redistribution autonome du contenu. Cette preuve décrit ce qui était affiché lors de la vérification. L’absence de badge Content ID visible n’est pas une garantie juridique absolue. Pixabay précise que des droits tiers supplémentaires peuvent s’appliquer.

La source musicale n’est pas suivie dans Git. Lors d’un rendu autorisé, GitHub Actions la télécharge dans un répertoire temporaire, vérifie exactement son SHA-256, crée le mix dérivé, puis ne publie ni MP3, ni WAV, ni stem autonome.

## Contrats

- `config/T2_music_selection_v0_7_0.json` : décision, preuve datée, rejet de B et invariants ;
- `schemas/T2_music_selection_v0_7_0.schema.json` : schéma strict, propriétés supplémentaires interdites ;
- `config/T2_complete_voice_mix_v0_7_0.json` : source D, quatre voix, niveaux et politique de publication ;
- `schemas/T2_complete_voice_mix_v0_7_0.schema.json` : verrou strict du mix ;
- `config/T2_runtime_contract_v0_7_0.json` : parcours unifié sans modification des liaisons visuelles ;
- `schemas/render_job.schema.json` : corrèle D avec le contrat v0.7, la sortie Afrofire et le statut de production courant ;
- `demo/render_job_complete_demo.json` : fixture exécutable courante ;
- `cloudflare/src/render_job_template.ts` : snapshot généré depuis cette fixture.

Les contrats historiques v0.5 et v0.6 restent inchangés pour préserver les Releases existantes et leur auditabilité.

## Invariants préservés

- domaine : T2 **Avant / Après** ;
- scènes : 6 s, 8 s, 7 s, 9 s ;
- durée : 30 s ;
- image : 720 × 1280, 30 i/s, 900 images ;
- douze écrans stables et même machine de capture ;
- six réponses commerçant toujours reliées aux captures et aux quatre blocs graphiques ;
- flux H.264 visuel de référence : `2ed8b3813410df8b9497da7b00877b208bed115038965f73989f00550d3941f5` ;
- quatre voix enregistrées inchangées, même identité, vitesse `1×`, sans sous-titres automatiques ;
- musique à −3 dB hors parole et −10 dB sous parole ;
- attaque 120 ms, relâchement 450 ms ;
- master −16 LUFS, plafond WAV −2 dBTP, AAC stéréo 48 kHz cible 192 kb/s ;
- exactement un MP4 lors d’une publication de rendu et aucun audio autonome.

## Validation sans rendu local

Les contrôles locaux valident uniquement les contrats, le moteur, les fixtures, Cloudflare et l’invariance visuelle :

```bash
python tools/validate_contract.py
python tools/verify_existing_tests_unchanged.py
python tools/verify_visual_pipeline.py
python tools/build_cloudflare_contracts.py
git diff --exit-code -- cloudflare/src/capture_flow_contract.ts cloudflare/src/form_contract.ts cloudflare/src/render_job_template.ts
python -m unittest discover -s tests -v
npm run test --prefix cloudflare
```

Le code Python refuse le rendu complet si `GITHUB_ACTIONS != true`.

## Publication

Le workflow `.github/workflows/server-render-unified.yml` utilise explicitement `--music D`. La publication d’une Release est désactivée par défaut. Si elle est demandée ultérieurement, le workflow :

1. rend et valide sur GitHub Actions ;
2. exige `VIDEO_T2_COMPLET_VOIX_AFROFIRE_A_VALIDER.mp4` comme unique MP4 ;
3. refuse tout fichier audio autonome ;
4. vérifie les checksums ;
5. refuse d’écraser un tag ou une Release v0.7 déjà existants.

L’intégration du code et des contrats ne crée à elle seule aucun nouveau rendu vidéo et n’altère aucune Release stable.
