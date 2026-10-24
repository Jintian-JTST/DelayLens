"""Render the API systemd unit and the Caddyfile for this machine; install nothing."""

import argparse
import re
from pathlib import Path

from render_service import quote_unit

HOSTNAME = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$")


def caddy_path(value: Path) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True, help="public hostname, e.g. 203-0-113-7.sslip.io")
    parser.add_argument("--python", type=Path, default=project / "backend" / ".venv" / "bin" / "python")
    parser.add_argument("--dist", type=Path, default=project / "frontend" / "dist")
    parser.add_argument("--output-dir", type=Path, default=project / ".local")
    args = parser.parse_args()
    if not HOSTNAME.match(args.site):
        parser.error("--site must be a plain hostname such as 203-0-113-7.sslip.io")
    # absolute(), not resolve(): a venv's bin/python is a symlink to the base interpreter,
    # and following it would drop the venv's installed packages.
    interpreter = args.python.absolute()
    if not interpreter.is_file():
        parser.error("Python interpreter not found; create the backend virtual environment first")

    deploy = project / "deploy"
    unit = (deploy / "delaylens-api.service.in").read_text(encoding="utf-8")
    unit = unit.replace("@BACKEND@", quote_unit(project / "backend")).replace("@PYTHON@", quote_unit(interpreter))
    caddy = (deploy / "Caddyfile.in").read_text(encoding="utf-8")
    caddy = caddy.replace("@SITE@", args.site).replace("@DIST@", caddy_path(args.dist.absolute()))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "delaylens-api.service").write_text(unit, encoding="utf-8", newline="\n")
    (args.output_dir / "Caddyfile").write_text(caddy, encoding="utf-8", newline="\n")
    if not args.dist.is_dir():
        print(f"Note: {args.dist} does not exist yet; build the frontend before starting Caddy.")
    print("API unit and Caddyfile rendered; nothing was installed or started.")


if __name__ == "__main__":
    main()
