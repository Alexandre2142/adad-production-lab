from pathlib import Path
import math
from .storage import read_annotations, save_annotations

PHASES = {
    "tension": "Tension",
    "montee_instrumentale": "Montée instrumentale",
    "proclamation_vocale": "Proclamation vocale",
    "liberation_emotionnelle": "Libération émotionnelle",
    "resonance_intime": "Résonance intime",
}


def phases_for(track, duration):
    phases = track.get("phases", {})
    if not isinstance(phases, dict) or set(phases) - PHASES.keys():
        raise ValueError("Unknown phase or invalid phases object")
    result = []
    for key, label in PHASES.items():
        phase = dict(phases.get(key, {}))
        legacy = {"proclamation_vocale": "proclamation_s", "resonance_intime": "resonance_intime_s"}.get(key)
        if not phase and legacy and track.get(legacy) is not None:
            phase = {"start_s": track[legacy], "status": "unverified", "notes": "Legacy timestamp; validation pending"}
        status = phase.get("status", "unverified")
        start, end = phase.get("start_s"), phase.get("end_s")
        if status not in ("unverified", "validated"):
            raise ValueError(f"Invalid status for {key}")
        for value in (start, end):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= duration):
                raise ValueError(f"Timestamp outside audio for {key}")
        if end is not None and (start is None or end <= start):
            raise ValueError(f"End must follow start for {key}")
        if status == "validated" and (start is None or end is None):
            raise ValueError(f"Validated phase needs start and end: {key}")
        result.append({"phase": key, "label": label, "status": status, "start_s": start,
                       "end_s": end, "notes": phase.get("notes", "")})
    return result


def timestamp(value):
    if value is None:
        return "à localiser"
    minutes, seconds = divmod(value, 60)
    return f"{int(minutes):02d}:{seconds:06.3f}"


def annotate(path, annotation_path, play=False):
    import soundfile as sf
    path, annotation_path = Path(path), Path(annotation_path)
    if annotation_path.suffix.lower() != ".json" or annotation_path.resolve() == path.resolve():
        raise ValueError("Annotations must be saved to a separate JSON file")
    doc, revision = read_annotations(annotation_path)
    track = doc.setdefault("tracks", {}).setdefault(path.name, {})
    duration = sf.info(path).duration
    phases = phases_for(track, duration)
    print(f"{path} — {duration:.3f} s. Positions: seconds or mm:ss; blank keeps current value.")
    print("Listen first. Missing phases stay unverified. Validation is a human listening judgment.")
    if play:
        import winsound
        winsound.PlaySound(str(path.resolve()), winsound.SND_FILENAME | winsound.SND_ASYNC)
    try:
        for phase in phases:
            print(f"\n{phase['label']} ({phase['status']}) {phase['notes']}")
            for field in ("start_s", "end_s"):
                value = input(f"{field} [{timestamp(phase[field])}]: ").strip()
                if value == "-":
                    phase[field] = None
                elif value:
                    parts = value.split(":")
                    if len(parts) > 2:
                        raise ValueError("Use seconds or mm:ss")
                    phase[field] = float(parts[-1]) + (60 * float(parts[0]) if len(parts) == 2 else 0)
            answer = input("Validate by listening? [y / n / blank=keep]: ").strip().lower()
            if answer not in ("", "y", "n"):
                raise ValueError("Use y, n or blank")
            if answer:
                phase["status"] = "validated" if answer == "y" else "unverified"
            note = input("Listening notes [blank=keep]: ").strip()
            if note:
                phase["notes"] = note
        track["phases"] = {p["phase"]: {k: p[k] for k in ("start_s", "end_s", "status", "notes")} for p in phases}
        phases_for(track, duration)
        save_annotations(annotation_path, doc, revision)
    finally:
        if play:
            winsound.PlaySound(None, 0)
