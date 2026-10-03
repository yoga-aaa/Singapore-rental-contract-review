"""Build the public offline demo from pinned sources, without keys/model calls."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    for script in ("bootstrap.py", "bootstrap_official_v18.py"):
        subprocess.run([sys.executable, "scripts/" + script], cwd=ROOT, check=True)
    from src.application import load_retriever
    from src.official_sources import load_official_index
    templates = load_retriever()
    official = load_official_index(ROOT)
    if len(templates.chunks) != 135 or len(official) != 49:
        raise ValueError("Unexpected source counts; refusing to deploy.")
    print(json.dumps({
        "mode": "offline", "model_api_calls": 0,
        "template_sections": len(templates.chunks),
        "official_sections": len(official),
        "entrypoint_sha256": hashlib.sha256((ROOT / "webapp.py").read_bytes()).hexdigest(),
        "note": "Build checks are not a new quality evaluation."
    }))


if __name__ == "__main__":
    main()
