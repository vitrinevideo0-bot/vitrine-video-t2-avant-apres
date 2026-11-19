# Vitrine Vidéo — T2 « Avant / Après »

Dépôt public indépendant du gabarit **Restaurants / Maquis — T2**. T1 reste intact et sert uniquement de référence technique publique en lecture seule.

## Étape actuelle : runtime unifié v0.6

T2 dispose maintenant d’un parcours interconnecté : **formulaire exécutable + 12 écrans + caméra/micro + RenderJob complet + rendu GitHub + voix/musique + QC + résultat/erreur + statut Cloudflare**. Le montage visuel v0.3, ses 900 images, ses textes dynamiques, ses polices et ses mouvements restent la base inchangée. La musique et les quatre voix v0.5 ne sont pas modifiées.

- [Architecture et déploiement du runtime unifié](docs/T2_UNIFIED_RUNTIME_CLOUDFLARE.md)
- `cloudflare/public/` — application mobile qui consomme réellement les contrats formulaire/capture ;
- `cloudflare/src/index.ts` — plan de contrôle Worker + R2, sans rendu vidéo ;
- `.github/workflows/server-render-unified.yml` — unique plan de rendu de production ;
- `demo/render_job_complete_demo.json` — fixture canonique complète `1.1.0`.

## Exemplaire complet voix + musique déjà validé

Le montage visuel v0.3 validé reste inchangé. La v0.5 lui ajoute quatre voix françaises réunies dans un stem de 30 s et la musique **B — Afro Pop Vlog Sunshine**, avec le ducking exact de T1.

- [Ouvrir la Release complète v0.5](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.5.0-complete-voice-mix)
- [Télécharger directement l’unique MP4](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/download/t2-avant-apres-v0.5.0-complete-voice-mix/VIDEO_T2_COMPLET_VOIX_MUSIQUE_B_A_VALIDER.mp4)
- [Lire le contrat et les contrôles](docs/T2_COMPLETE_VOICE_MIX.md)
- [Conserver le rendu visuel v0.3 validé comme base](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.3.0-text-motion)
- [Voir la présélection A/B/C/D historique](https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres/releases/tag/t2-avant-apres-v0.4.0-music-shortlist)

Le choix B vaut pour **cet exemplaire unique de validation** et n’est pas défini comme musique par défaut du gabarit. La page Pixabay de B affiche « Content ID Registered ».

## Audio v0.5

- une seule identité vocale française pour S1 à S4 ;
- quatre exemples exacts de `capture-guide/consignes_T2.json` ;
- départs : 1,20 s · 6,80 s · 14,70 s · 21,80 s ;
- voix à vitesse naturelle `1×`, sans sous-titres ;
- musique à −3 dB hors parole et −10 dB sous parole ;
- attaque 120 ms, relâchement 450 ms ;
- master −16 LUFS, plafond WAV −2 dBTP ;
- AAC stéréo 48 kHz, cible 192 kb/s ;
- un seul MP4 public, aucun fichier audio source autonome.

## Questions commerçant qui alimentent le JSON

1. Comment s’appelle ton restaurant ou ton maquis ?
2. Quel plat allons-nous montrer avant et après ?
3. Quel est le prix de ce plat ?
4. Quel numéro WhatsApp les clients doivent-ils utiliser ?
5. Dans quel quartier peut-on te trouver ?
6. Veux-tu ajouter une petite phrase ? — facultatif.

La définition machine est `form/questions_T2.json`. L’application la charge par `/v1/contracts/form`. Les réponses deviennent `merchant_payload.nom`, `merchant_payload.produit`, `merchant_payload.prix`, `merchant_payload.whatsapp`, `merchant_payload.quartier` et `merchant_payload.accroche`. Elles restent liées aux captures et aux quatre blocs graphiques par `config/T2_runtime_contract_v0_6_0.json`.

## Contrat visuel conservé

- quatre scènes : 6 s · 8 s · 7 s · 9 s ;
- douze écrans stables : quatre scènes × A Guide / B Enregistrement / C Validation ;
- 720 × 1280, 30 i/s, 900 images, 30,000 s ;
- six transitions de 0,42 s ;
- Pinyon Script et textes dynamiques incorporés ;
- flux vidéo v0.3 copié bit à bit dans le MP4 v0.5 ;
- pour une reconstruction v0.6, l’invariant bloquant est le SHA-256 du flux H.264 copié ; le SHA-256 du conteneur MP4 complet reste consigné comme provenance, car l’empaquetage peut varier sans changer une seule image.

## Production exclusivement sur GitHub

Le workflow canonique `.github/workflows/server-render-unified.yml` reçoit le même RenderJob que le formulaire et les quatre captures, reconstruit le visuel, sélectionne les voix capturées ou leur fallback enregistré, vérifie la musique B, applique le ducking, exécute le QC indépendant et produit `RenderResult` ou `RenderError`. Le Worker Cloudflare ne rend jamais la vidéo.

Le workflow v0.5 historique `.github/workflows/server-render-complete-voice.yml` reste conservé comme preuve de l’exemplaire déjà validé. Il vérifie l’architecture audio T1 au commit canonique, exécute tous les tests, télécharge temporairement la source Pixabay, construit le stem voix et le mix, mesure les niveaux, effectue une validation indépendante puis publie une Release avec :

1. `VIDEO_T2_COMPLET_VOIX_MUSIQUE_B_A_VALIDER.mp4` — unique vidéo ;
2. le rapport des niveaux LUFS/dBTP, débit AAC et rapport parole/musique ;
3. l’automation de ducking à 10 ms et son graphique ;
4. les empreintes SHA-256 et le verrou T1.

Aucun rendu de production local n’est autorisé. T1 n’est jamais modifié.
