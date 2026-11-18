# Vitrine Vidéo — T2 « Avant / Après »

Dépôt public indépendant du gabarit **Restaurants / Maquis — T2**. T1 reste intact et sert uniquement de référence technique publique en lecture seule.

## État actuel : pool A–D approuvé et rotation persistante v1

Le propriétaire a validé le pool final **A — Naija Flow / B — Savanna Beats / C — Vibe Republic / D — Adolescence (Pixabay 328624)**. La piste D remplace Afrofire 300338. Les anciennes auditions voix + musique restent uniquement des preuves historiques : les quatre actifs de production sont désormais des **instrumentales propres de 30 secondes, sans voix** dans `audio/music/t2-afrobeat-v1/`.

Le runtime `auto` suit exclusivement le cycle persistant **A → B → C → D → A**. Le premier succès utilise A ; un callback `COMPLETED` validé avance d’un seul cran ; `FAILED` ou un QC refusé laisse l’état inchangé ; le rejeu d’un même succès reste idempotent même après un tour complet. Cloudflare stocke l’état et le registre `successful_render_jobs` dans R2 sous `music/t2-last-success.json`, avec écriture conditionnelle et protection contre les callbacks concurrents. Le writer local équivalent est `tools/record_t2_music_result.py`.

Cette évolution ne modifie pas la création approuvée :

- `template_id` reste `T2` et la version du gabarit reste `0.1.0` ;
- `audio_profile` reste `afrobeat_restaurants_maquis` ;
- les scènes restent 6 / 8 / 7 / 9 s, soit 30 s et 900 images ;
- les douze écrans, les six champs commerçant, le visuel v0.3 et ses liaisons dynamiques restent inchangés ;
- les quatre voix restent à vitesse naturelle `1×` ;
- le ducking reste à −3 dB hors parole et −10 dB sous parole, attaque 120 ms, relâchement 450 ms ;
- aucune source Pixabay complète n’est publiée ; quatre éditions instrumentales adaptées de 30 s sont embarquées comme actifs du gabarit, sans voix d’audition.

Tout rendu vidéo de production reste exclusivement exécuté par GitHub Actions.

## Sources de vérité du pool v1

- `config/T2_music_pool_v1_0_0.json` — catalogue approuvé, provenance, hashes et contrat de sélection ;
- `approvals/T2_MUSIC_POOL_APPROVAL_2026-11-18.json` — décision propriétaire et remplacement de 300338 par 328624 ;
- `audio/music/t2-afrobeat-v1/` — quatre instrumentales propres de 30 s, preuves, provenance et sommes SHA-256 ;
- `config/T2_complete_voice_mix_v1_0_0_A.json` à `D.json` — mixages homogènes des quatre pistes ;
- `config/T2_runtime_contract_v1_0_0.json` — liaisons runtime et stockage après succès ;
- `schemas/T2_music_pool_v1_0_0.schema.json` et `schemas/T2_music_selection_state.schema.json` — contrats stricts ;
- `engine/complete_adapter.py` — sélection, état persistant local et compatibilité historique explicite ;
- `cloudflare/src/music_pool_contract.ts` et `cloudflare/src/index.ts` — pool runtime, stockage après succès et dispatch GitHub ;
- `music/auditions/v1/` — anciennes comparaisons voix + musique, conservées uniquement pour audit et jamais utilisées en production ;
- `music/T2_music_shortlist_v0_4_0.json` — preuve historique séparée, jamais réactivée par le pool v1 ;
- `demo/render_job_complete_demo.json` et `config/T2_complete_voice_mix_v0_7_0.json` — exemplaire D historique immuable ;
- [Architecture et plan de contrôle Cloudflare](docs/T2_UNIFIED_RUNTIME_CLOUDFLARE.md).

## Provenance du pool approuvé

| ID | Piste | SHA-256 source |
|---|---|---|
| A | Naija Flow — DPStudioMusic | `a7f990fb3891aee07e55ae144ed8f7dd65aa549c10c1bf9e4247ddb522c6d943` |
| B | Savanna Beats — DPStudioMusic | `9d803e54f0833de5537334890b8edbd85ed9f384257d943beaaf3ccedee73740` |
| C | Vibe Republic — DPStudioMusic | `71b20e916467d79ff4c59a674a2e3d66695cb613ddca76342cc02177fb629fec` |
| D | Adolescence — 47643651 (Pixabay 328624) | `b5a928c000a7943b845271f2fd8eba1c635cccb6e5487e80f6f14c53b0c2e8d0` |

Pour chaque page source, aucun badge « Content ID Registered » n’était affiché lors du contrôle daté archivé. Cette observation n’est pas une garantie juridique absolue ; la licence Pixabay et les éventuels droits tiers restent applicables.

## Parcours commerçant inchangé

Les six réponses définies par `form/questions_T2.json` alimentent `merchant_payload.nom`, `produit`, `prix`, `whatsapp`, `quartier` et `accroche`. Elles restent reliées aux quatre captures et aux blocs graphiques par le contrat courant `config/T2_runtime_contract_v1_0_0.json` ; les contrats v0.6/v0.7 restent archivés pour leurs exemplaires historiques.

Le parcours conserve quatre scènes et trois états stables par scène : **A Guide / B Enregistrement / C Validation**. Caméra et microphone sont relus à `1×`; le décompte 3–2–1 reste transitoire et ne crée pas un treizième écran.

## Production exclusivement sur GitHub

Le Worker Cloudflare valide, stocke, impose le successeur musical exact, orchestre et déclenche GitHub ; il ne rend jamais de vidéo. GitHub Actions reçoit le même RenderJob que le formulaire et les captures. Les jobs commerçants reconstruisent leur visuel dynamique ; la fixture manuelle canonique et les exemplaires historiques matérialisent le master v0.3 verrouillé et en vérifient les empreintes. GitHub vérifie ensuite l’instrumentale locale sélectionnée par SHA-256, applique voix et ducking, puis exécute le QC indépendant. Le Worker ne valide la nouvelle valeur de rotation qu’après un `RenderResult` réussi et conforme.

Le workflow courant utilise `--music auto`, refuse la publication d’audio autonome et refuse d’écraser une Release portant déjà le même tag. Son option de pré-Release additive est désactivée par défaut.

## Historique public conservé

Les Releases v0.3, v0.5 et v0.6 restent accessibles comme preuves historiques et ne sont ni remplacées ni écrasées. Les MP4 v0.5/v0.6 contiennent toutefois la piste B désormais rejetée et ne représentent plus la sélection musicale courante.

- [Base visuelle v0.3 à préserver](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.3.0-text-motion)
- [Présélection A/B/C/D historique](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.4.0-music-shortlist)
- [Runtime v0.6 historique, musique B rejetée](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.6.0-unified-runtime)

Aucun rendu de production local n’est autorisé. T1 n’est jamais modifié.
