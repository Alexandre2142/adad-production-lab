"""Reject private artifacts in the Git index (also checks staged additions)."""
from pathlib import PurePosixPath
import subprocess
import sys


def private_path(name):
    path = PurePosixPath(name)
    parts = {part.lower() for part in path.parts}
    return bool(parts & {"audio", "annotations", "reports", "lyrics", "prompts", "uploads", ".venv", "__pycache__"}
                or path.suffix.lower() in {".wav", ".mp3", ".flac", ".pem", ".key", ".zip"}
                or path.name.lower() == "secrets.toml"
                or (path.name.startswith(".env") and path.name != ".env.example"))


if __name__ == "__main__":
    names = subprocess.check_output(["git", "ls-files", "-z"]).decode("utf-8").split("\0")
    unsafe = [name for name in names if name and private_path(name)]
    if unsafe:
        print("Private paths in Git index:", *unsafe, sep="\n")
        sys.exit(1)
    print("No private data paths in Git index. This path check does not detect embedded secrets.")
