import json
from pathlib import Path
from inventory import experiment

ROOT = Path(__file__).resolve().parent


def render():
    template = (ROOT / "explorer.html").read_text(encoding="utf-8")
    return template.replace("<!-- REPORT -->", json.dumps(experiment(), separators=(",", ":")))


if __name__ == "__main__":
    (ROOT / "index.html").write_text(render(), encoding="utf-8", newline="\n")
