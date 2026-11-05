from copy import deepcopy
import json
import os
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from suno_lab.annotations import PHASES, phases_for
from suno_lab.annotation_ui import parse_position, track_from_fields, waveform, report_readiness, generate_report
from suno_lab.storage import read_annotations, save_annotations


@pytest.mark.parametrize("value,expected", [("", None), (" 12.5 ", 12.5), ("01:02.25", 62.25), ("1:02,5", 62.5), ("0", 0)])
def test_positions(value, expected):
    assert parse_position(value) == expected


@pytest.mark.parametrize("value", ["-1", "nan", "inf", "1:60", "1:2:3", "a", "1:-2"])
def test_invalid_positions(value):
    with pytest.raises(ValueError):
        parse_position(value)


@pytest.fixture
def project(tmp_path):
    audio = tmp_path / "audio" / "prototypes"
    audio.mkdir(parents=True)
    for name in ("ASCENSION.wav", "FRACTURE.wav"):
        samples = np.zeros((16000, 2))
        samples[100, 0], samples[101, 1] = .9, -.7
        sf.write(audio / name, samples, 8000, subtype="FLOAT")
    doc = {"project": "ADAD", "tracks": {name: {"notes": "track metadata", "proclamation_s": None,
        "phases": {key: {"start_s": None, "end_s": None, "status": "unverified", "notes": ""} for key in PHASES}}
        for name in ("ASCENSION.wav", "FRACTURE.wav")}}
    dest = tmp_path / "annotations" / "the_signal.json"
    dest.parent.mkdir()
    dest.write_text(json.dumps(doc), encoding="utf-8")
    return tmp_path, dest, sorted(audio.glob("*.wav"))


def fields_for(track):
    return {p["phase"]: {"start": "" if p["start_s"] is None else str(p["start_s"]),
                          "end": "" if p["end_s"] is None else str(p["end_s"]),
                          "status": p["status"], "notes": p["notes"]} for p in phases_for(track, 2)}


def test_save_preserves_schema_and_sources(project):
    root, dest, files = project
    originals = [p.read_bytes() for p in files]
    doc, revision = read_annotations(dest)
    before = deepcopy(doc)
    track = doc["tracks"][files[0].name]
    track["phases"]["tension"]["custom"] = "keep"
    fields = fields_for(track)
    fields["tension"].update(start="0:00.25", end="1.5", status="validated", notes="écoute")
    doc["tracks"][files[0].name] = track_from_fields(track, fields, 2)
    returned = save_annotations(dest, doc, revision)
    saved, content = read_annotations(dest)
    assert content == returned
    assert saved["project"] == before["project"]
    assert saved["tracks"][files[1].name] == before["tracks"][files[1].name]
    assert saved["tracks"][files[0].name]["phases"]["tension"]["custom"] == "keep"
    assert saved["tracks"][files[0].name]["proclamation_s"] is None
    assert [p.read_bytes() for p in files] == originals
    assert not list(dest.parent.glob("*.tmp"))
    assert not Path(str(dest) + ".lock").exists()


@pytest.mark.parametrize("start,end,status", [("0", "3", "validated"), ("1", "0.5", "unverified"), ("", "", "validated")])
def test_bounds_reuse_validator(project, start, end, status):
    _, dest, files = project
    doc, _ = read_annotations(dest)
    track = doc["tracks"][files[0].name]
    original = deepcopy(track)
    fields = fields_for(track)
    fields["tension"].update(start=start, end=end, status=status)
    with pytest.raises(ValueError):
        track_from_fields(track, fields, 2)
    assert track == original


def test_failed_replace_keeps_previous_json(project, monkeypatch):
    _, dest, _ = project
    doc, revision = read_annotations(dest)
    def fail(source, target):
        assert Path(source).parent == Path(target).parent
        assert Path(target).read_bytes() == revision
        json.loads(Path(source).read_text(encoding="utf-8"))
        raise OSError("simulated failure")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        save_annotations(dest, doc, revision)
    assert dest.read_bytes() == revision
    assert not list(dest.parent.glob("*.tmp"))
    assert not Path(str(dest) + ".lock").exists()


def test_concurrent_save_is_rejected(project):
    _, dest, _ = project
    doc, revision = read_annotations(dest)
    changed = deepcopy(doc)
    changed["project"] = "changed"
    save_annotations(dest, changed, revision)
    with pytest.raises(ValueError, match="modifiées"):
        save_annotations(dest, doc, revision)
    assert read_annotations(dest)[0] == changed
    lock = Path(str(dest) + ".lock")
    lock.touch()
    with pytest.raises(ValueError, match="cours"):
        save_annotations(dest, changed, dest.read_bytes())
    assert lock.exists()


def test_no_audio_destination(project):
    _, _, files = project
    original = files[0].read_bytes()
    with pytest.raises(ValueError):
        save_annotations(files[0], {}, original)
    assert files[0].read_bytes() == original


def test_waveform_retains_peaks_and_channels(project):
    _, _, files = project
    before = files[0].read_bytes()
    t, low, high = waveform(files[0], max_points=50)
    assert len(t) <= 50
    assert low.shape == high.shape == (len(t), 2)
    assert high[:, 0].max() == pytest.approx(.9)
    assert low[:, 1].min() == pytest.approx(-.7)
    assert all(0 < point < 2 for point in t)
    assert files[0].read_bytes() == before


def validated_doc(dest):
    doc, _ = read_annotations(dest)
    for track in doc["tracks"].values():
        track["phases"]["proclamation_vocale"].update(start_s=.5, end_s=1, status="validated")
    return doc


def test_report_requires_saved_validated_events(project):
    root, dest, files = project
    doc, _ = read_annotations(dest)
    assert report_readiness(files, doc)
    with pytest.raises(ValueError):
        generate_report(files, doc, root / "reports")
    doc = validated_doc(dest)
    assert not report_readiness(files, doc)
    doc["tracks"][files[0].name]["phases"]["tension"]["start_s"] = .1
    assert report_readiness(files, doc)


def test_generate_report_with_missing_optional_phases(project):
    root, dest, files = project
    originals = [p.read_bytes() for p in files]
    doc = validated_doc(dest)
    report = generate_report(files, doc, root / "reports")
    assert report.exists()
    assert (report.parent / "aligned_proclamation_vocale.png").exists()
    assert "unverified" in report.read_text(encoding="utf-8")
    assert [p.read_bytes() for p in files] == originals


def app(project, monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    root, _, _ = project
    monkeypatch.setenv("SUNO_LAB_ROOT", str(root))
    return AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=30).run()


def test_ui_initial_state_and_invalid_bounds(project, monkeypatch):
    at = app(project, monkeypatch)
    assert not at.exception
    assert len(at.text_input) == 10
    assert all(field.value == "" for field in at.text_input)
    assert at.button[2].disabled
    original = project[1].read_bytes()
    at.text_input[0].input("3").run()
    assert at.button[1].disabled
    assert at.error
    assert project[1].read_bytes() == original


def test_ui_save_switch_reload_and_report(project, monkeypatch):
    at = app(project, monkeypatch)
    at.text_input[0].input("0:00.25")
    at.text_input[1].input("0:01.25")
    at.selectbox[1].select("validated")
    at.text_area[0].input("Human listening").run()
    at.selectbox[0].select("FRACTURE.wav").run()
    at.selectbox[0].select("ASCENSION.wav").run()
    assert at.text_input[0].value == "0:00.25"
    at.button[1].click().run()
    assert not at.exception
    saved = read_annotations(project[1])[0]
    assert saved["tracks"]["ASCENSION.wav"]["phases"]["tension"]["status"] == "validated"
    at.selectbox[0].select("FRACTURE.wav").run()
    at.text_input[0].input(".3")  # strict seconds syntax rejects a missing leading zero
    at.text_input[1].input("1.2")
    at.selectbox[1].select("validated").run()
    assert at.button[1].disabled
    at.text_input[0].input("0.3").run()
    at.button[1].click().run()
    assert not at.button[2].disabled
    at.button[2].click().run()
    assert not at.exception
    assert (project[0] / "reports" / "interface" / "report.md").exists()
    at.text_input[0].input("0.4").run()
    assert at.button[2].disabled
    at.button[0].click().run()
    assert at.text_input[0].value == "0.3"
