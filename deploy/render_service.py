"""Render a user systemd unit with this machine's paths; do not install/start it."""

import argparse
from pathlib import Path


def quote_unit(value: Path) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=project / "backend" / ".venv" / "bin" / "python")
    parser.add_argument("--output", type=Path, default=project / ".local" / "delaylens-recorder.service")
    args = parser.parse_args()
    interpreter = args.python.resolve()
    if not interpreter.is_file():
        parser.error("Python interpreter not found; create the backend virtual environment first")
    template = (project / "deploy" / "delaylens-recorder.service.in").read_text(encoding="utf-8")
    rendered = template.replace("@BACKEND@", quote_unit(project / "backend")).replace("@PYTHON@", quote_unit(interpreter))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print("Recorder unit rendered; no service was installed or started.")


if __name__ == "__main__":
    main()
