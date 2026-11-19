# T2 — logique formulaire, caméras, textes et future voix

## Source publique de référence

T1 est consulté uniquement en lecture au commit `c656510ab81d31d413dc4dfd74b42671532cd978`.

Les mécanismes repris sont :

- formulaire → `merchant_payload` ;
- quatre prises → `captures.S1` à `captures.S4` ;
- un même RenderJob réunit informations, vidéos et contrat de sortie ;
- les informations sont liées à des blocs graphiques et à des scènes ;
- la caméra et son éventuel microphone gardent une horloge identique à 1,0× ;
- la voix capturée est réservée pour le mixage ultérieur, sans sous-titres automatiques.

Aucun fichier, commit, tag, workflow ou asset de T1 n’est modifié.

## Ordre T2 programmé

1. Le commerçant répond aux six questions.
2. Les réponses deviennent `merchant_payload`.
3. Les douze écrans guident quatre captures de 6, 8, 7 et 9 secondes.
4. Les captures deviennent `captures.S1`…`captures.S4`.
5. `tools/build_render_job.py` produit un seul RenderJob.
6. `engine/render_text_motion.py` lit le même RenderJob pour les scènes et les textes.
7. Après validation visuelle, la piste voix reprend l’audio des captures qui en contiennent.
8. Après choix musical, le mixage baisse la musique sous la parole sans accélérer, couper ou sous-titrer la voix.

## Liaisons texte

| Champ JSON | Scènes / blocs |
|---|---|
| `merchant_payload.nom` | S1 identité, S3 signature, S4 final |
| `merchant_payload.produit` | S1 identité, S2 offre, S4 final |
| `merchant_payload.prix` | S2 offre, S4 final |
| `merchant_payload.whatsapp` | S4 final |
| `merchant_payload.quartier` | S4 final |
| `merchant_payload.accroche` | S3 révélation ; omise si vide |

La configuration machine est `config/T2_runtime_contract_v0_3_0.json`.

## Police de la capture

Le titre calligraphique de la capture fournie a été traduit par **Pinyon Script**, police libre SIL OFL incorporée au dépôt et verrouillée par SHA-256. La capture elle-même n’est pas redistribuée.

- nom du restaurant : Pinyon Script ;
- plat et accroche : Playfair Display ;
- prix, quartier et WhatsApp : DejaVu Sans.

## Étape actuelle

Le rendu v0.3 montre les données dynamiques et leur motion design, mais reste sans flux audio. La musique et la voix ne sont pas supprimées de l’architecture : leur timeline est réservée et testée, mais leur mixage reste bloqué jusqu’aux validations prévues.
