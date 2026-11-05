from pathlib import Path
import json
import os
import tempfile
from contextlib import contextmanager


@contextmanager
def annotation_lock(path):
    lock = Path(str(path) + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("Une sauvegarde est déjà en cours (.lock). Réessayer après sa fin.") from exc
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def read_annotations(path):
    path = Path(path)
    content = path.read_bytes() if path.exists() else None
    doc = json.loads(content.decode("utf-8-sig")) if content is not None else {"tracks": {}}
    if not isinstance(doc, dict) or not isinstance(doc.get("tracks"), dict):
        raise ValueError("Le JSON doit contenir un objet tracks.")
    return doc, content


def save_annotations(path, doc, expected):
    """Replace a JSON in the same directory, only if the loaded revision still exists."""
    path = Path(path)
    if path.suffix.lower() != ".json" or path.resolve().suffix.lower() != ".json":
        raise ValueError("Les annotations doivent rester dans un fichier JSON distinct des WAV.")
    content = (json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with annotation_lock(path):
        current = path.read_bytes() if path.exists() else None
        if current != expected:
            raise ValueError("Annotations modifiées depuis leur chargement. Recharger avant de sauvegarder.")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as output:
                temporary = Path(output.name)
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    return content
