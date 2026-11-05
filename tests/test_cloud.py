import io
import json
from pathlib import Path
import tempfile
import zipfile
import numpy as np
import pytest
import soundfile as sf
from suno_lab import cloud
from suno_lab.annotations import PHASES


def wav(seconds=1, sr=8000, channels=1, format="WAV"):
    stream = io.BytesIO()
    sf.write(stream, np.zeros((int(seconds*sr), channels)), sr, format=format)
    return stream.getvalue()


def doc_for(names):
    return {"project": "Synthetic test", "tracks": {name: {"phases": {
        key: {"start_s": .1 if key == "tension" else None,
              "end_s": .5 if key == "tension" else None,
              "status": "validated" if key == "tension" else "unverified", "notes": ""}
        for key in PHASES}} for name in names}}


def test_upload_validation():
    data = wav()
    assert cloud.validate_uploads([("A.wav", data)]) == {"A.wav": data}
    for name in ("../a.wav", "a/b.wav", "C:\\a.wav", ".hidden.wav", "a.wav\x00", "a.mp3"):
        with pytest.raises(ValueError):
            cloud.validate_uploads([(name, data)])
    with pytest.raises(ValueError):
        cloud.validate_uploads([("a.wav", data), ("A.wav", data)])
    for items in ([], [("a.wav", data)]*3, [("a.wav", b"bad")], [("a.wav", wav(format="FLAC"))]):
        with pytest.raises(ValueError):
            cloud.validate_uploads(items)


@pytest.mark.parametrize("seconds,sr,channels", [(301, 8000, 1), (1, 96000, 1), (1, 8000, 3)])
def test_decoded_limits(seconds, sr, channels):
    with pytest.raises(ValueError):
        cloud.validate_uploads([("a.wav", wav(seconds, sr, channels))])


def test_byte_and_sample_limits(monkeypatch):
    data = wav()
    monkeypatch.setattr(cloud, "MAX_FILE_BYTES", len(data)-1)
    with pytest.raises(ValueError, match="50 Mio"):
        cloud.validate_uploads([("a.wav", data)])
    monkeypatch.setattr(cloud, "MAX_FILE_BYTES", len(data))
    monkeypatch.setattr(cloud, "MAX_TOTAL_BYTES", len(data))
    with pytest.raises(ValueError, match="totale"):
        cloud.validate_uploads([("a.wav", data), ("b.wav", data)])
    monkeypatch.setattr(cloud, "MAX_CHANNEL_SAMPLES", 1)
    with pytest.raises(ValueError, match="décodage"):
        cloud.validate_uploads([("a.wav", data)])


def test_annotations_keep_schema_and_validate(monkeypatch):
    audio = {"a.wav": wav()}
    doc = doc_for(audio)
    doc["extra"] = "keep"
    content = json.dumps(doc).encode()
    assert cloud.import_annotations(content, audio) == doc
    invalid = doc_for(audio)
    invalid["tracks"]["a.wav"]["phases"]["tension"]["end_s"] = 2
    with pytest.raises(ValueError):
        cloud.import_annotations(json.dumps(invalid).encode(), audio)
    with pytest.raises(ValueError):
        cloud.import_annotations(content, {})
    monkeypatch.setattr(cloud, "MAX_JSON_BYTES", 1)
    with pytest.raises(ValueError):
        cloud.import_annotations(content, audio)


def test_report_temporary_cleanup_and_no_audio_archive(monkeypatch):
    audio = {"a.wav": wav(), "b.wav": wav()}
    original = dict(audio)
    roots = []
    temporary = tempfile.TemporaryDirectory
    def capture(**kwargs):
        directory = temporary(**kwargs)
        roots.append(Path(directory.name))
        return directory
    monkeypatch.setattr(cloud.tempfile, "TemporaryDirectory", capture)
    assets, archive = cloud.report_bundle(audio, doc_for(audio))
    assert roots and all(not root.exists() for root in roots)
    assert "report.md" in assets and "aligned_tension.png" in assets
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        assert all(not name.endswith(".wav") for name in zipped.namelist())
        assert set(zipped.namelist()) == set(assets)
    assert audio == original
    def fail(*args):
        raise ValueError("synthetic failure")
    monkeypatch.setattr(cloud, "generate_report", fail)
    with pytest.raises(ValueError):
        cloud.report_bundle(audio, doc_for(audio))
    assert all(not root.exists() for root in roots)


def test_cloud_ui_sessions_are_separate_and_no_local_files(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("SUNO_LAB_ROOT", str(tmp_path / "must-not-be-used"))
    entry = Path(__file__).resolve().parents[1] / "cloud/streamlit_app.py"
    first = AppTest.from_file(str(entry), default_timeout=30).run()
    second = AppTest.from_file(str(entry), default_timeout=30).run()
    assert not first.exception and not second.exception
    assert not first.text_input and not second.text_input
    first.session_state["cloud_audio"] = {"a.wav": wav()}
    first.session_state["cloud_doc"] = {"tracks": {}}
    first.run()
    assert not first.exception
    assert len(first.text_input) == 10
    assert all(field.value == "" for field in first.text_input)
    assert not second.text_input
    first.text_input[0].input("0.1")
    first.text_input[1].input("0.5")
    first.selectbox[1].select("validated")
    first.button[3].click().run()
    assert not first.exception
    assert first.session_state["cloud_doc"]["tracks"]["a.wav"]["phases"]["tension"]["status"] == "validated"
    second.run()
    assert not second.text_input
    assert not (tmp_path / "must-not-be-used").exists()


def test_deployment_configuration_and_python_syntax():
    import ast
    import tomllib
    root = Path(__file__).resolve().parents[1]
    local = tomllib.loads((root / ".streamlit/config.toml").read_text(encoding="utf-8-sig"))
    remote = tomllib.loads((root / "cloud/.streamlit/config.toml").read_text(encoding="utf-8-sig"))
    assert local["server"]["address"] == "127.0.0.1"
    assert remote["server"]["address"] == "0.0.0.0"
    assert remote["server"]["maxUploadSize"] == 50
    assert remote["server"]["enableXsrfProtection"]
    for path in (root / "src").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8-sig"), feature_version=(3, 10))


def test_report_busy_rejected():
    audio = {"a.wav": wav(), "b.wav": wav()}
    with cloud.REPORT_LOCK:
        with pytest.raises(ValueError, match="déjà en cours"):
            cloud.report_bundle(audio, doc_for(audio))
