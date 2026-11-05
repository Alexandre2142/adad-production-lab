from copy import deepcopy
import io
import json
from pathlib import Path
import re
import tempfile
import zipfile
from threading import Lock
import soundfile as sf
from .annotations import phases_for
from .annotation_ui import generate_report

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_FILES = 2
MAX_JSON_BYTES = 1024 * 1024
MAX_DURATION_S = 300
MAX_CHANNEL_SAMPLES = 24_000_000
REPORT_LOCK = Lock()


def validate_uploads(items):
    if not 1 <= len(items) <= MAX_FILES:
        raise ValueError("Charger un ou deux WAV par session.")
    if sum(len(data) for _, data in items) > MAX_TOTAL_BYTES:
        raise ValueError("Limite totale : 100 Mio par session.")
    result = {}
    for name, data in items:
        if len(name) > 128 or not re.fullmatch(r"[\w () .-]+\.wav", name, flags=re.IGNORECASE) or name.startswith("."):
            raise ValueError("Nom WAV invalide : lettres, chiffres, espaces, parenthèses, tirets ou points uniquement.")
        if name.casefold() in {n.casefold() for n in result}:
            raise ValueError("Les noms des WAV doivent être distincts.")
        if not 0 < len(data) <= MAX_FILE_BYTES:
            raise ValueError("Limite : 50 Mio par WAV non vide.")
        try:
            with sf.SoundFile(io.BytesIO(data)) as audio:
                if audio.format not in ("WAV", "WAVEX", "RF64"):
                    raise ValueError("Le contenu doit être un WAV réel.")
                if not 1 <= audio.channels <= 2 or not 8000 <= audio.samplerate <= 48000:
                    raise ValueError("WAV mono/stéréo, de 8 à 48 kHz uniquement.")
                if not 0 < audio.frames/audio.samplerate <= MAX_DURATION_S:
                    raise ValueError("Durée WAV : plus de zéro et au plus 5 minutes.")
                if audio.frames * audio.channels > MAX_CHANNEL_SAMPLES:
                    raise ValueError("WAV trop volumineux après décodage (24 millions d’échantillons de canaux maximum).")
        except RuntimeError as exc:
            raise ValueError("WAV illisible.") from exc
        result[name] = data
    return result


def import_annotations(content, audio):
    if len(content) > MAX_JSON_BYTES:
        raise ValueError("Annotations : 1 Mio maximum.")
    doc = json.loads(content.decode("utf-8-sig"))
    if not isinstance(doc, dict) or not isinstance(doc.get("tracks"), dict):
        raise ValueError("Le JSON doit contenir un objet tracks.")
    json.dumps(doc, allow_nan=False)
    for name, track in doc["tracks"].items():
        if name not in audio:
            raise ValueError("Charger les WAV correspondant aux pistes du JSON avant son import.")
        if not isinstance(track, dict):
            raise ValueError("Chaque piste doit être un objet JSON.")
        phases_for(track, sf.info(io.BytesIO(audio[name])).duration)
    return deepcopy(doc)


def report_bundle(audio, doc):
    # Names and limits are checked again at this boundary before any disk write.
    audio = validate_uploads(list(audio.items()))
    doc = import_annotations(json.dumps(doc, ensure_ascii=False, allow_nan=False).encode("utf-8"), audio)
    if not REPORT_LOCK.acquire(blocking=False):
        raise ValueError("Un calcul est déjà en cours. Réessayer dans quelques instants.")
    try:
        with tempfile.TemporaryDirectory(prefix="adad-report-") as directory:
            root = Path(directory)
            files = []
            for name, content in audio.items():
                path = root / name
                path.write_bytes(content)
                files.append(path)
            report = generate_report(files, doc, root / "report")
            assets = {p.name: p.read_bytes() for p in report.parent.iterdir() if p.is_file()}
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, content in assets.items():
                    archive.writestr(name, content)
            return assets, output.getvalue()
    finally:
        REPORT_LOCK.release()
