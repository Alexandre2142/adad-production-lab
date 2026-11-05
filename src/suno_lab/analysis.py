from pathlib import Path
import hashlib
import math
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd
from .annotations import phases_for


def features(x, sr):
    x = x.astype(np.float64)
    rms = float(np.sqrt(np.mean(x*x)))
    peak = float(np.max(np.abs(x)))
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freq = np.fft.rfftfreq(len(x), 1 / sr)
    total = float(np.sum(spec))
    centroid = float(np.dot(freq, spec) / total) if total > 1e-12 else 0.0
    bandwidth = float(np.sqrt(np.dot((freq-centroid)**2, spec) / total)) if total > 1e-12 else 0.0
    rolloff = float(freq[min(np.searchsorted(np.cumsum(spec), .85 * total), len(freq)-1)]) if total > 1e-12 else 0.0
    rms_db = 20*np.log10(max(rms, 1e-12))
    peak_db = 20*np.log10(max(peak, 1e-12))
    return {"rms_dbfs": round(float(rms_db), 3), "peak_dbfs": round(float(peak_db), 3),
            "crest_db": round(float(peak_db-rms_db), 3), "centroid_hz": round(centroid, 1),
            "bandwidth_hz": round(bandwidth, 1), "rolloff85_hz": round(rolloff, 1)}


def analyze(path: str | Path, window_seconds: float = 5.0, target_sr: int = 22050,
            annotations=None, event_radius: float = 30.0):
    """Compute non-perceptual features on mono audio, with deterministic windows."""
    path = Path(path)
    if not math.isfinite(window_seconds) or window_seconds <= 0:
        raise ValueError("window_seconds must be positive and finite")
    if not math.isfinite(event_radius) or event_radius <= 0:
        raise ValueError("event_radius must be positive and finite")
    if isinstance(target_sr, bool) or not isinstance(target_sr, int) or target_sr <= 0:
        raise ValueError("target_sr must be a positive integer")
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(source.read()).hexdigest()
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    if len(data) == 0:
        raise ValueError(f"Empty audio: {path}")
    if not np.isfinite(data).all():
        raise ValueError(f"Non-finite audio: {path}")
    duration = len(data) / sr
    phases = phases_for(annotations or {}, duration)
    mono = np.mean(data, axis=1)
    if sr != target_sr:
        divisor = gcd(sr, target_sr)
        mono = resample_poly(mono, target_sr // divisor, sr // divisor)
    # Keep boundaries within the original duration, even after resampling rounding.
    def segment(start, end):
        return mono[max(0, round(start*target_sr)):min(len(mono), round(end*target_sr))]

    n = max(1, int(round(window_seconds * target_sr)))
    windows = []
    for start in range(0, len(mono), n):
        x = mono[start:start+n]
        windows.append({"start_s": round(start/target_sr, 3),
                        "end_s": round(min((start+len(x))/target_sr, duration), 3), **features(x, target_sr)})
    events = []
    for phase in phases:
        anchor = phase["start_s"]
        if anchor is None:
            continue
        local = []
        for offset in np.arange(-event_radius, event_radius, window_seconds):
            start = max(0.0, anchor + float(offset))
            end = min(duration, anchor + min(float(offset)+window_seconds, event_radius))
            x = segment(start, end)
            if end <= start or not len(x):
                continue
            local.append({"start_s": round(start, 3), "end_s": round(end, 3),
                          "relative_start_s": round(start-anchor, 3),
                          "relative_end_s": round(end-anchor, 3), **features(x, target_sr)})
        before = segment(max(0, anchor-event_radius), anchor)
        after = segment(anchor, min(duration, anchor+event_radius))
        contrast = None
        if len(before) and len(after):
            contrast = round(features(after, target_sr)["rms_dbfs"] - features(before, target_sr)["rms_dbfs"], 3)
        interval = segment(anchor, phase["end_s"]) if phase["end_s"] is not None else []
        events.append({**phase, "anchor_s": anchor, "requested_radius_s": event_radius,
                       "before_duration_s": round(len(before)/target_sr, 3),
                       "after_duration_s": round(len(after)/target_sr, 3),
                       "after_minus_before_rms_db": contrast,
                       "interval_features": features(interval, target_sr) if len(interval) else None,
                       "windows": local})
    levels = [w["rms_dbfs"] for w in windows]
    return {"file": path.name, "sha256": digest, "duration_s": round(duration, 3), "sample_rate_hz": sr,
            "analysis_sample_rate_hz": target_sr, "channels": data.shape[1], "window_seconds": window_seconds,
            "rms_window_range_db": round(max(levels)-min(levels), 3),
            "windows": windows, "phases": phases, "events": events}
