"""Clone the local DB, then rebuild operational history only in the new clone."""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import environ
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent


def pg_binary(name):
    binary = Path(r"C:\Program Files\PostgreSQL\18\bin") / f"{name}.exe"
    return str(binary) if binary.exists() else name


def main():
    env = environ.Env()
    environ.Env.read_env(ROOT / ".env")
    source = env.db("DATABASE_URL")
    if source["HOST"] not in ("127.0.0.1", "localhost") or source["NAME"] != "sitrap":
        raise SystemExit("Solo se admite la base local original sitrap.")
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"sitrap_demo_{tag}"
    backup = ROOT / ".local" / "backups" / name
    backup.mkdir(parents=True)
    dump = backup / "sitrap.dump"
    private = Path(env("CUY_SALES_PRIVATE_ROOT", default=str(ROOT / ".local" / "private-sales")))
    if not private.is_absolute():
        private = ROOT / private
    if private.is_dir():
        shutil.copytree(private, backup / "private-sales")
    pg_env = {**os.environ, "PGPASSWORD": source["PASSWORD"], "PGCONNECT_TIMEOUT": "5"}
    conn = dict(host=source["HOST"], port=int(source["PORT"] or 5432),
                user=source["USER"], password=source["PASSWORD"], connect_timeout=5)
    args = ["-h", conn["host"], "-p", str(conn["port"]), "-U", conn["user"]]
    subprocess.run([pg_binary("pg_dump"), *args, "-d", "sitrap", "-Fc", "-f", str(dump)],
                   env=pg_env, check=True, cwd=ROOT)
    with psycopg.connect(**conn, dbname="postgres", autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
    subprocess.run([pg_binary("pg_restore"), *args, "--exit-on-error", "-d", name, str(dump)],
                   env=pg_env, check=True, cwd=ROOT)
    url = urlsplit(env("DATABASE_URL"))
    demo_env = {**pg_env, "DATABASE_URL": urlunsplit(url._replace(path=f"/{name}")),
                "CUY_SALES_PRIVATE_ROOT": str(ROOT / ".local" / name / "private-sales"),
                "SITRAP_DEMO_REBUILD": name}
    for command in (["migrate", "--noinput"], ["seed_direction_demo"]):
        subprocess.run([sys.executable, "manage.py", *command], env=demo_env, check=True, cwd=ROOT)
    print(f"Base de demostración: {name}. Respaldo: {backup.relative_to(ROOT)}.")
    print("La base original y su almacenamiento privado no fueron modificados.")


if __name__ == "__main__":
    main()
