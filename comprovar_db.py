import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "dades" / "nutricio.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM ingredients;")
    total = cur.fetchone()[0]
    print(f"✅ Total ingredients a la BD: {total}")

    cur.execute("""
        SELECT codi, ingredient, proveidor
        FROM ingredients
        ORDER BY codi
        LIMIT 20;
    """)
    rows = cur.fetchall()

    print("\n📋 Mostra (codi | ingredient | proveidor):")
    for codi, ing, prov in rows:
        print(f"- {codi} | {ing} | {prov}")

    conn.close()

if __name__ == "__main__":
    main()
