"""Read-only verification for the generated local demonstration against its source."""
import argparse
import re

import environ
import psycopg
from create_direction_demo import ROOT


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    name = parser.parse_args().database
    require(re.fullmatch(r"sitrap_demo_\d{8}_\d{6}", name), "Nombre de base de demostración no válido.")
    env = environ.Env()
    environ.Env.read_env(ROOT / ".env")
    cfg = env.db("DATABASE_URL")
    require(cfg["HOST"] in ("localhost", "127.0.0.1") and cfg["NAME"] == "sitrap", "Solo se admite PostgreSQL local.")
    conn = dict(host=cfg["HOST"], port=cfg["PORT"] or 5432, user=cfg["USER"], password=cfg["PASSWORD"], connect_timeout=5,
                options="-c default_transaction_read_only=on")
    with psycopg.connect(**conn, dbname="sitrap") as original, psycopg.connect(**conn, dbname=name) as demo:
        for table, fields in (
            ("accounts_user", "id, username, password, is_active, password_change_required"),
            ("accounts_roleassignment", "id, user_id, role_id, location_id, scope, starts_at, ends_at"),
        ):
            # Both table names and column lists are fixed above. Never print password hashes.
            query = f"SELECT {fields} FROM {table} ORDER BY id"
            require(original.execute(query).fetchall() == demo.execute(query).fetchall(), f"No coincide {table}.")
        data = demo.execute("""
          SELECT s.code, count(DISTINCT p.id), sum(b.quantity), min(p.capacity), count(DISTINCT p.purpose)
          FROM cuyes_shed s JOIN cuyes_pen p ON p.shed_id=s.id
          JOIN cuyes_occupation o ON o.pen_id=p.id JOIN cuyes_balance b ON b.occupation_id=o.id
          GROUP BY s.code ORDER BY s.code
        """).fetchall()
        require(data == [("CAN-G01", 48, 1500, 48, 4), ("KOT-G01", 24, 750, 48, 4),
                         ("KOT-G02", 24, 750, 48, 4)], f"Inventario inesperado: {data}")
        pens = demo.execute("""
          SELECT p.code, coalesce(sum(b.quantity),0), p.capacity FROM cuyes_pen p
          LEFT JOIN cuyes_occupation o ON o.pen_id=p.id LEFT JOIN cuyes_balance b ON b.occupation_id=o.id
          GROUP BY p.id
        """).fetchall()
        require(all(0 < n <= cap for _, n, cap in pens) and len({n for _, n, _ in pens}) >= 8,
                "Conteos de poza no variados o fuera de capacidad.")
        mismatches = demo.execute("""
          WITH ledger AS (
            SELECT occupation_id, category, quality, sum(delta) AS quantity FROM cuyes_ledgerline GROUP BY 1,2,3
          ) SELECT count(*) FROM ledger l FULL JOIN cuyes_balance b USING (occupation_id, category, quality)
            WHERE coalesce(l.quantity,0) <> coalesce(b.quantity,0)
        """).fetchone()[0]
        require(mismatches == 0, "Los saldos no concilian con el Kardex.")
        require(demo.execute("""
          SELECT count(*) FROM catalog_animalstay s JOIN catalog_location l ON l.id=s.center_id WHERE l.code='0001'
        """).fetchone()[0] == 12
                and demo.execute("SELECT count(*) FROM catalog_animal").fetchone()[0] == 12,
                "Las 12 vacas no están exclusivamente en Kotosh.")
        milk = demo.execute("SELECT count(*), min(date), max(date) FROM milk_milking").fetchone()
        modes = demo.execute("SELECT mode, state, count(*) FROM cuyes_saleorder GROUP BY 1,2 ORDER BY 1,2").fetchall()
        journeys = demo.execute("SELECT state, count(*) FROM traceability_transfer GROUP BY 1 ORDER BY 1").fetchall()
        missing = demo.execute("""
          SELECT count(*) FROM cuyes_saledispatch s
          WHERE (SELECT coalesce(sum(quantity),0) FROM cuyes_saledispatchdetail WHERE dispatch_id=s.id)
             <> (SELECT coalesce(-sum(delta),0) FROM cuyes_ledgerline WHERE movement_id=s.movement_id)
        """).fetchone()[0]
        require(missing == 0 and {mode for mode, state, _ in modes if state == "ENTREGADO"} == {"DIRECTO", "PUNTO"},
                "Faltan entregas en ambas modalidades o no coinciden con Kardex.")
        require(any(state == "RECIBIDO" for state, _ in journeys), "Sin recepciones de leche.")
        print("Usuarios y asignaciones conservados; Kardex y saldos conciliados.")
        print(f"Galpones: {data}; ordeños: {milk}; ventas: {modes}; traslados de leche: {journeys}")


if __name__ == "__main__":
    main()
