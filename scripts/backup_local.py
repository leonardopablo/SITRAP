"""Explicit development-only PostgreSQL backup before additive local migrations."""
import os
import subprocess
from datetime import datetime
from pathlib import Path

import environ

ROOT = Path(__file__).resolve().parent.parent


def main():
    env = environ.Env()
    environ.Env.read_env(ROOT / ".env")
    db = env.db("DATABASE_URL")
    if db["HOST"] not in ["127.0.0.1", "localhost"]:
        raise SystemExit("Refusing to back up a non-local database with this development helper.")
    destination = ROOT / ".local" / "backups"
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / f"before-cuyes-{datetime.now():%Y%m%d-%H%M%S}.dump"
    executable = Path(r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe")
    args = [
        str(executable) if executable.exists() else "pg_dump",
        "-h", db["HOST"], "-p", str(db["PORT"] or 5432), "-U", db["USER"],
        "-d", db["NAME"], "-Fc", "-f", str(output),
    ]
    subprocess.run(args, env={**os.environ, "PGPASSWORD": db["PASSWORD"]}, check=True)
    print(f"Local backup: {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
