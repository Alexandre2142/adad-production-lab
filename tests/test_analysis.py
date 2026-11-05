import numpy as np
import soundfile as sf
from suno_lab.analysis import analyze


def test_sine_audio(tmp_path):
    sr = 22050
    t = np.arange(sr * 2) / sr
    p = tmp_path / "test.wav"
    sf.write(p, (0.25 * np.sin(2*np.pi*440*t)).astype("float32"), sr)
    result = analyze(p, window_seconds=1)
    assert result["duration_s"] == 2.0
    assert len(result["windows"]) == 2
    assert -16 < result["windows"][0]["rms_dbfs"] < -14
    assert 400 < result["windows"][0]["centroid_hz"] < 500
