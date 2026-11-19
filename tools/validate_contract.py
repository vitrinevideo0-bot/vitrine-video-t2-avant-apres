#!/usr/bin/env python3
"""Contrôle bloquant du contrat T2 avant tout rendu serveur."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from build_render_job import build_job

ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def fail(message: str) -> None:
    raise SystemExit(f"ERREUR: {message}")


def main() -> None:
    config = read_json("config/T2_avant_apres_template_v0_1_0.json")
    guide = read_json("capture-guide/consignes_T2.json")
    questions = read_json("form/questions_T2.json")
    answers = read_json("demo/reponses_demo.json")
    job = read_json("demo/input_demo.json")
    schema = read_json("schemas/render_job.schema.json")
    manifest = read_json("rushes/manifest.json")
    baseline = read_json("baseline/T1_BASELINE.lock.json")
    current_answers = read_json("demo/reponses_textes_demo.json")
    current_job = read_json("demo/render_job_complete_demo.json")
    music_decision = read_json("config/T2_music_selection_v0_7_0.json")
    music_decision_schema = read_json("schemas/T2_music_selection_v0_7_0.schema.json")
    afrofire_mix = read_json("config/T2_complete_voice_mix_v0_7_0.json")
    afrofire_mix_schema = read_json("schemas/T2_complete_voice_mix_v0_7_0.schema.json")
    current_runtime = read_json("config/T2_runtime_contract_v0_7_0.json")

    if (config["template_id"], config["version"], config["audio_profile"]) != (
        "T2",
        "0.1.0",
        "afrobeat_restaurants_maquis",
    ):
        fail("identité canonique T2, version du gabarit ou profil audio")
    if ".mp3" in config["audio_profile"].lower() or "afrofire" in config["audio_profile"].lower():
        fail("audio_profile doit désigner une ambiance et non un fichier ou une piste")
    if current_runtime["domain"] != "AVANT_APRES":
        fail("le runtime v0.7 doit rester dans le domaine Avant / Après")
    if current_runtime["audio_profile"] != config["audio_profile"]:
        fail("le runtime et le JSON canonique n’utilisent pas le même profil audio")
    if current_runtime["music_selection_contract"] != "config/T2_music_selection_v0_7_0.json":
        fail("le runtime ne référence pas la décision musicale approuvée")

    if [item["seconds"] for item in config["scenes"]] != [6, 8, 7, 9]:
        fail("durées des scènes")
    if sum(item["seconds"] for item in config["scenes"]) != 30:
        fail("durée totale")
    if config["stable_screen_count"] != 12:
        fail("exactement 12 écrans stables")
    if len(config["scenes"]) * len(config["capture_states"]) != 12:
        fail("quatre scènes × trois états")

    events = config["transition_budget"]["events"]
    if len(events) != 6:
        fail("six transitions requises")
    references = [item["reference"] for item in events]
    if any(references.count(reference) != 2 for reference in (1, 2, 3)):
        fail("deux transitions par référence")
    if abs(config["transition_budget"]["duration_each_seconds"] * 2 - 0.84) > 1e-9:
        fail("équilibre 0,84 s par référence")

    expected_output = {
        "width": 720,
        "height": 1280,
        "fps": 30,
        "frames": 900,
        "duration_seconds": 30,
        "pixel_format": "yuv420p",
        "audio_sample_rate": 44100,
    }
    if config["output"] != expected_output:
        fail("contrat de sortie")

    expected_ids = ["nom", "produit", "prix", "whatsapp", "quartier", "accroche"]
    fields = questions["fields"]
    if [field["id"] for field in fields] != expected_ids:
        fail("six questions universelles dans l’ordre T1")
    if [field["required"] for field in fields] != [True, True, True, True, True, False]:
        fail("cinq réponses obligatoires et accroche facultative")
    if [field["json_target"] for field in fields] != [
        f"merchant_payload.{field_id}" for field_id in expected_ids
    ]:
        fail("liaison questions vers merchant_payload")

    Draft202012Validator(schema).validate(job)
    if build_job(answers) != job:
        fail("demo/input_demo.json ne correspond pas aux réponses transformées")
    if job["merchant_payload"] != answers:
        fail("les réponses n’alimentent pas merchant_payload")
    if [job["captures"][slot]["duration_ms"] for slot in ("S1", "S2", "S3", "S4")] != [
        6000,
        8000,
        7000,
        9000,
    ]:
        fail("liaison des quatre captures")
    if job["render_audio"] is not False or job["audio_mode"] != "silent_no_audio_stream":
        fail("rendu strictement muet")
    if job["render_business_text"] is not False:
        fail("aucun texte commerçant dans le rendu actuel")

    Draft202012Validator(
        music_decision_schema, format_checker=FormatChecker()
    ).validate(music_decision)
    Draft202012Validator(
        afrofire_mix_schema, format_checker=FormatChecker()
    ).validate(afrofire_mix)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(current_job)
    rebuilt_current = build_job(
        current_answers,
        stage="complete_voice_music_render",
        requested_music="D",
        voice_mode="registered_voice_clips",
        control_plane="github_actions_manual",
    )
    if rebuilt_current != current_job:
        fail("demo/render_job_complete_demo.json ne correspond pas à Afrofire approuvé")
    if current_job["audio_plan"]["music"]["selected_candidate_id"] != "D":
        fail("le RenderJob courant doit sélectionner explicitement D")
    if current_job["audio_plan"]["music"]["source_sha256"] != music_decision["selection"]["source_sha256"]:
        fail("le RenderJob et la décision musicale ne verrouillent pas la même source")
    if current_job["audio_plan"]["publication"]["publish_standalone_audio"] is not False:
        fail("publication audio autonome interdite")

    mention = (
        "Tu peux parler pendant que tu filmes, dans la langue que tu veux : "
        "fon, yoruba, français, anglais ou une autre langue que tu maîtrises."
    )
    if guide["mention_langues_commune"] != mention:
        fail("mention linguistique exacte")
    if len(guide["scenes"]) != 4 or [item["secondes"] for item in guide["scenes"]] != [6, 8, 7, 9]:
        fail("quatre guides")
    if guide["audio"] != {
        "parole_obligatoire": False,
        "conserver_voix_capturee": True,
        "sous_titres_automatiques": False,
    }:
        fail("règles de capture audio")
    if any(not item["exemple_facultatif"].strip() for item in guide["scenes"]):
        fail("exemple facultatif par scène")

    if len(manifest["sources"]) != 4 or [item["scene"] for item in manifest["sources"]] != [1, 2, 3, 4]:
        fail("quatre rushes déclarés")
    if baseline["source_commit"] != "c656510ab81d31d413dc4dfd74b42671532cd978":
        fail("verrou T1")
    if baseline["never_modify_source"] is not True:
        fail("T1 doit rester en lecture seule")

    render_source = (ROOT / "engine/render_silent.py").read_text(encoding="utf-8")
    transition_source = (ROOT / "engine/transitions.py").read_text(encoding="utf-8")
    forbidden_drawing_apis = ("cv2.putText", "ImageDraw", "draw.text")
    if any(token in render_source or token in transition_source for token in forbidden_drawing_apis):
        fail("API de dessin de texte détectée dans le chemin de rendu")
    if (ROOT / "engine/audio.py").exists():
        fail("moteur audio interdit à cette étape")

    print("T2_CONTRACT_OK")


if __name__ == "__main__":
    main()
