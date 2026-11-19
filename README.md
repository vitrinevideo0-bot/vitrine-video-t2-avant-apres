# Vitrine Vidéo — T2 « Avant / Après »

Dépôt public indépendant du gabarit **Restaurants / Maquis — T2**. T1 reste intact et sert uniquement de référence technique publique en lecture seule.

## État actuel : Afrofire approuvé, préparation runtime v0.7

La piste B historique a été rejetée à cause du badge **Content ID Registered** affiché par sa page. La sélection T2 courante est désormais **D — Afrofire · DPStudioMusic**, approuvée explicitement pour l’ambiance Afrobeat Restaurants/Maquis.

Cette évolution change uniquement la sélection musicale et les contrats d’orchestration associés :

- `template_id` reste `T2` ;
- la version du gabarit reste `0.1.0` ;
- `audio_profile` vaut `afrobeat_restaurants_maquis` et ne contient ni nom de piste ni nom de fichier ;
- les scènes restent 6 / 8 / 7 / 9 s, soit 30 s et 900 images ;
- les douze écrans, les six champs commerçant, le visuel v0.3 et ses liaisons dynamiques restent inchangés ;
- les quatre voix restent à vitesse naturelle `1×` ;
- le ducking reste à −3 dB hors parole et −10 dB sous parole, attaque 120 ms, relâchement 450 ms ;
- aucune source musicale ou stem audio n’est publié comme fichier autonome.

Aucun nouveau MP4 n’est publié par ce changement de code. Tout futur rendu de production doit être déclenché explicitement et exécuté exclusivement sur GitHub Actions.

## Sources de vérité v0.7

- `config/T2_avant_apres_template_v0_1_0.json` — identité canonique du gabarit et profil audio sémantique ;
- `config/T2_music_selection_v0_7_0.json` — décision approuvée, remplacement de B, preuve de droits observée et invariants ;
- `config/T2_complete_voice_mix_v0_7_0.json` — quatre voix, Afrofire et calibrations audio ;
- `config/T2_runtime_contract_v0_7_0.json` — liaisons formulaire, captures, visuel, audio et serveur ;
- `demo/render_job_complete_demo.json` — RenderJob complet courant, sélection explicite D ;
- `schemas/render_job.schema.json` — corrélation stricte entre candidat D, contrat v0.7 et sortie Afrofire ;
- `.github/workflows/server-render-unified.yml` — plan de rendu GitHub, sans écrasement de Release existante ;
- `cloudflare/src/render_job_template.ts` — snapshot généré du même RenderJob ;
- [Intégration Afrofire v0.7 et preuve de provenance](docs/T2_AFROFIRE_INTEGRATION_V0_7.md) ;
- [Rapport QC prépublication](reports/T2_AFROFIRE_INTEGRATION_QC_V0_7_0.md) ;
- [Architecture et plan de contrôle Cloudflare](docs/T2_UNIFIED_RUNTIME_CLOUDFLARE.md).

## Preuve musicale conservée

| Élément | Valeur verrouillée |
|---|---|
| Candidat | `D` |
| Titre / auteur | Afrofire — DPStudioMusic |
| Page | `https://pixabay.com/music/afrobeat-afrofire-300338/` |
| Licence | Pixabay Content License — usage commercial et adaptation permis, attribution non obligatoire |
| Source | CDN Pixabay, téléchargée seulement de façon éphémère au moment du rendu |
| Taille | `7 680 768` octets |
| SHA-256 | `24e9606e14e4708e8c8ffa3a6a97429dbfc95049d388481392d72b971e932c61` |
| Observation datée | badge AI generated visible ; aucun badge Content ID visible le 2026-11-19 |
| Publication autonome | interdite |

L’absence de badge Content ID visible est une observation datée, pas une garantie juridique absolue. La licence Pixabay et d’éventuels droits tiers restent à respecter.

## Parcours commerçant inchangé

Les six réponses définies par `form/questions_T2.json` alimentent `merchant_payload.nom`, `produit`, `prix`, `whatsapp`, `quartier` et `accroche`. Elles restent reliées aux quatre captures et aux blocs graphiques par `config/T2_runtime_contract_v0_7_0.json`.

Le parcours conserve quatre scènes et trois états stables par scène : **A Guide / B Enregistrement / C Validation**. Caméra et microphone sont relus à `1×`; le décompte 3–2–1 reste transitoire et ne crée pas un treizième écran.

## Production exclusivement sur GitHub

Le Worker Cloudflare valide, stocke, orchestre et déclenche GitHub ; il ne rend jamais de vidéo. GitHub Actions reçoit le même RenderJob que le formulaire et les captures. Un job commerçant dynamique reconstruit son propre visuel. L’exemplaire canonique déjà approuvé matérialise au contraire le master exact de la Release v0.3, puis vérifie le SHA-256 du fichier **et** du flux H.264 avant tout mixage. GitHub vérifie aussi la source Afrofire par SHA-256, applique voix et ducking, puis exécute le QC indépendant.

Le workflow refuse la publication d’audio autonome et refuse d’écraser une Release portant déjà le même tag. Son option de publication de Release est désactivée par défaut.

## Historique public conservé

Les Releases v0.3, v0.5 et v0.6 restent accessibles comme preuves historiques et ne sont ni remplacées ni écrasées. Les MP4 v0.5/v0.6 contiennent toutefois la piste B désormais rejetée et ne représentent plus la sélection musicale courante.

- [Base visuelle v0.3 à préserver](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.3.0-text-motion)
- [Présélection A/B/C/D historique](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.4.0-music-shortlist)
- [Runtime v0.6 historique, musique B rejetée](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.6.0-unified-runtime)

Aucun rendu de production local n’est autorisé. T1 n’est jamais modifié.
