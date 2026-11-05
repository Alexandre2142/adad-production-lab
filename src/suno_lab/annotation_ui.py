from copy import deepcopy
import math
from pathlib import Path
import re
import numpy as np
import soundfile as sf
from .annotations import PHASES, phases_for
from .analysis import analyze
from .report import write_report


def parse_position(text):
    text = text.strip().replace(",", ".")
    if not text:
        return None
    if not re.fullmatch(r"(?:\d+:)?\d+(?:\.\d+)?", text):
        raise ValueError("Position attendue : secondes ou mm:ss (vide = absent).")
    parts = text.split(":")
    seconds = float(parts[-1])
    if len(parts) == 2:
        if seconds >= 60:
            raise ValueError("La partie secondes de mm:ss doit être inférieure à 60.")
        seconds += 60 * int(parts[0])
    if not math.isfinite(seconds):
        raise ValueError("La position doit être finie.")
    return seconds


def track_from_fields(track, fields, duration):
    updated = deepcopy(track)
    phases = updated.setdefault("phases", {})
    for key, label in PHASES.items():
        entry = fields[key]
        try:
            phase = phases.setdefault(key, {})
            phase.update(start_s=parse_position(entry["start"]), end_s=parse_position(entry["end"]),
                         status=entry["status"], notes=entry["notes"])
        except ValueError as exc:
            raise ValueError(f"{label} : {exc}") from exc
    phases_for(updated, duration)
    return updated


def waveform(path, max_points=2000):
    """Min/max envelope per channel; retain short peaks without rewriting the WAV."""
    if max_points <= 0:
        raise ValueError("max_points must be positive")
    times, low, high = [], [], []
    with sf.SoundFile(path) as audio:
        if audio.frames == 0:
            raise ValueError("WAV vide")
        block = max(1, math.ceil(audio.frames/max_points))
        for start in range(0, audio.frames, block):
            samples = audio.read(block, dtype="float32", always_2d=True)
            times.append((start + len(samples)/2)/audio.samplerate)
            low.append(samples.min(axis=0))
            high.append(samples.max(axis=0))
    return np.array(times), np.array(low), np.array(high)


def report_readiness(files, doc):
    reasons = []
    if len(files) < 2:
        reasons.append("Choisir au moins deux WAV pour comparer.")
    if len({Path(f).name for f in files}) != len(files):
        reasons.append("Les noms de fichiers WAV doivent être distincts.")
    for path in files:
        name = Path(path).name
        phases = phases_for(doc.get("tracks", {}).get(name, {}), sf.info(path).duration)
        if not any(p["status"] == "validated" for p in phases):
            reasons.append(f"{name} : valider au moins une phase après écoute.")
        if any((p["start_s"] is not None or p["end_s"] is not None) and p["status"] != "validated" for p in phases):
            reasons.append(f"{name} : des repères saisis restent unverified.")
    return reasons


def generate_report(files, doc, out):
    reasons = report_readiness(files, doc)
    if reasons:
        raise ValueError("\n".join(reasons))
    data = [analyze(path, annotations=doc.get("tracks", {}).get(Path(path).name, {})) for path in files]
    write_report(data, doc, out)
    return Path(out) / "report.md"
