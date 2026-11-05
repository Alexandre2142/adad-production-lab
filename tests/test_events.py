import hashlib
import json
import sys
import numpy as np
import pytest
import soundfile as sf
from suno_lab.analysis import analyze
from suno_lab.annotations import PHASES, annotate, phases_for, timestamp
from suno_lab.cli import main


def audio(tmp_path, samples, sr=8000):
    path = tmp_path / "synthetic.wav"
    sf.write(path, samples, sr, subtype="FLOAT")
    return path


def test_silence(tmp_path):
    result = analyze(audio(tmp_path, np.zeros(8000)), .3, 8000)
    assert len(result["windows"]) == 4
    assert result["windows"][-1]["end_s"] == 1
    for w in result["windows"]:
        assert w["rms_dbfs"] == -240
        assert w["crest_db"] == w["centroid_hz"] == w["bandwidth_hz"] == w["rolloff85_hz"] == 0


def test_spectral_and_crest(tmp_path):
    t = np.arange(8000) / 8000
    path = audio(tmp_path, .25*np.sin(2*np.pi*440*t))
    w = analyze(path, 1, 8000)["windows"][0]
    assert w["rms_dbfs"] == pytest.approx(-15.051, abs=.01)
    assert w["crest_db"] == pytest.approx(3.01, abs=.01)
    assert w["centroid_hz"] == pytest.approx(440, abs=1)
    assert w["rolloff85_hz"] == pytest.approx(440, abs=2)
    assert w["bandwidth_hz"] < 2


def test_event_contrast_and_original(tmp_path):
    sr = 8000
    t = np.arange(4*sr)/sr
    x = np.sin(2*np.pi*400*t) * np.repeat([.1, .2], 2*sr)
    path = audio(tmp_path, x, sr)
    original = path.read_bytes()
    annotation = {"phases": {"proclamation_vocale": {"start_s": 2, "end_s": 3, "status": "validated"}}}
    result = analyze(path, .5, sr, annotation, 1)
    event = result["events"][0]
    assert event["after_minus_before_rms_db"] == pytest.approx(6.021, abs=.01)
    assert event["before_duration_s"] == event["after_duration_s"] == 1
    assert [w["relative_start_s"] for w in event["windows"]] == [-1, -.5, 0, .5]
    assert event["interval_features"]["rms_dbfs"] == pytest.approx(-16.99, abs=.01)
    assert result["rms_window_range_db"] == pytest.approx(6.021, abs=.01)
    assert path.read_bytes() == original
    assert result["sha256"] == hashlib.sha256(original).hexdigest()


@pytest.mark.parametrize("anchor", [0, 1])
def test_boundary_events(tmp_path, anchor):
    path = audio(tmp_path, np.zeros(8000))
    result = analyze(path, .3, 8000, {"proclamation_s": anchor}, event_radius=2)
    event = result["events"][0]
    assert event["after_minus_before_rms_db"] is None
    assert sum(w["end_s"]-w["start_s"] for w in event["windows"]) == pytest.approx(1)
    assert all(0 <= w["start_s"] < w["end_s"] <= 1 for w in event["windows"])
    assert event["status"] == "unverified"


def test_stereo_resampling(tmp_path):
    t = np.arange(16000)/16000
    x = .2*np.sin(2*np.pi*440*t)
    path = audio(tmp_path, np.column_stack([x, -x]), 16000)
    result = analyze(path, .25, 8000)
    assert result["channels"] == 2
    assert result["sample_rate_hz"] == 16000
    assert result["analysis_sample_rate_hz"] == 8000
    assert result["windows"][0]["rms_dbfs"] == -240


@pytest.mark.parametrize("phase", [
    {"start_s": -1}, {"start_s": 2}, {"start_s": float("nan")}, {"start_s": True},
    {"start_s": 0, "end_s": 0}, {"end_s": .5}, {"status": "validated"}, {"status": "detected"},
])
def test_bad_annotations(phase):
    with pytest.raises(ValueError):
        phases_for({"phases": {"tension": phase}}, 1)


@pytest.mark.parametrize("window,radius,sr", [(0, 30, 8000), (float("nan"), 30, 8000), (1, -1, 8000), (1, float("inf"), 8000), (1, 30, 0)])
def test_bad_settings(tmp_path, window, radius, sr):
    with pytest.raises(ValueError):
        analyze(tmp_path / "not_needed.wav", window, sr, event_radius=radius)


def test_missing_phases():
    phases = phases_for({}, 1)
    assert len(phases) == 5
    assert all(p["status"] == "unverified" and p["start_s"] is None for p in phases)
    assert timestamp(61.5) == "01:01.500"
    with pytest.raises(ValueError):
        phases_for({"phases": {"emotion_detected": {}}}, 1)


def test_annotation_workflow(tmp_path, monkeypatch):
    path = audio(tmp_path, np.zeros(16000))
    original = path.read_bytes()
    dest = tmp_path / "annotations.json"
    answers = iter(["0:00.2", "0:00.8", "y", "Human listening", *([""] * 16)])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    annotate(path, dest)
    phases = json.loads(dest.read_text(encoding="utf-8"))["tracks"][path.name]["phases"]
    assert phases["tension"]["status"] == "validated"
    assert phases["tension"]["start_s"] == .2
    assert phases["resonance_intime"]["status"] == "unverified"
    assert path.read_bytes() == original


def test_cli_reports(tmp_path, monkeypatch):
    first = audio(tmp_path, np.zeros(8000))
    second = tmp_path / "other.wav"
    sf.write(second, np.zeros(8000), 8000)
    annotation = tmp_path / "annotations.json"
    annotation.write_text(json.dumps({"tracks": {first.name: {"proclamation_s": .5}, second.name: {"proclamation_s": .5}}}), encoding="utf-8")
    out = tmp_path / "report"
    monkeypatch.setattr(sys, "argv", ["suno-lab", "compare", str(first), str(second), "--annotations", str(annotation), "--out", str(out), "--window", ".25"])
    main()
    doc = json.loads((out / "analysis.json").read_text(encoding="utf-8"))
    assert len(doc["tracks"]) == 2
    assert (out / "rms_comparison.png").stat().st_size > 0
    assert (out / "spectral_comparison.png").stat().st_size > 0
    assert (out / "aligned_proclamation_vocale.png").stat().st_size > 0
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "00:00.500" in report
    assert "ne détecte pas automatiquement les émotions" in report
    assert "unverified" in report


def test_cli_without_timestamps(tmp_path, monkeypatch):
    first = audio(tmp_path, np.zeros(8000))
    second = tmp_path / "other.wav"
    sf.write(second, np.zeros(8000), 8000)
    out = tmp_path / "report"
    monkeypatch.setattr(sys, "argv", ["suno-lab", "compare", str(first), str(second), "--out", str(out)])
    main()
    assert "Aucun horodatage fourni" in (out / "report.md").read_text(encoding="utf-8")
    assert not list(out.glob("aligned_*.png"))

@pytest.mark.parametrize("key", list(PHASES))
def test_each_phase_interval(tmp_path, key):
    path = audio(tmp_path, np.zeros(8000))
    result = analyze(path, .2, 8000, {"phases": {key: {"start_s": .25, "end_s": .75, "status": "validated"}}}, .5)
    event = result["events"][0]
    assert event["phase"] == key
    assert event["interval_features"]["rms_dbfs"] == -240
    assert event["before_duration_s"] == .25
    assert event["after_duration_s"] == .5


def test_invalid_annotation_preserves_json(tmp_path, monkeypatch):
    path = audio(tmp_path, np.zeros(8000))
    dest = tmp_path / "annotations.json"
    original = '{"tracks": {}}'
    dest.write_text(original, encoding="utf-8")
    answers = iter(["2", "", "", "", *([""] * 16)])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    with pytest.raises(ValueError):
        annotate(path, dest)
    assert dest.read_text(encoding="utf-8") == original


def test_annotation_cannot_overwrite_audio(tmp_path):
    path = audio(tmp_path, np.zeros(8000))
    original = path.read_bytes()
    with pytest.raises(ValueError):
        annotate(path, path)
    assert path.read_bytes() == original
