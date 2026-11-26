"""Run Django against a validated demo database, without editing .env."""
import argparse
import os
import re
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

import environ
from create_direction_demo import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    args = parser.parse_args()
    name = args.database
    if not re.fullmatch(r"sitrap_demo_\d{8}_\d{6}", name):
        parser.error("Indica el nombre de una base aislada sitrap_demo_YYYYMMDD_HHMMSS.")
    env = environ.Env()
    environ.Env.read_env(ROOT / ".env")
    url = urlsplit(env("DATABASE_URL"))
    if url.hostname not in ("127.0.0.1", "localhost"):
        parser.error("La demostración requiere PostgreSQL local.")
    demo_env = {
        **os.environ,
        "DATABASE_URL": urlunsplit(url._replace(path=f"/{name}")),
        "CUY_SALES_PRIVATE_ROOT": str(ROOT / ".local" / name / "private-sales"),
        "SITRAP_DEMO_MODE": "1",
    }
    subprocess.run([sys.executable, "manage.py", "runserver", "127.0.0.1:8002"], env=demo_env, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
