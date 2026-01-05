import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "dades" / "nutricio.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Taula de receptes (capçalera)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receptes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            creada_el TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
    """)

    # Taula de línies de recepta (detall)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recepta_linies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recepta_id INTEGER NOT NULL,
            codi_ingredient TEXT NOT NULL,
            grams REAL NOT NULL,
            FOREIGN KEY (recepta_id) REFERENCES receptes(id) ON DELETE CASCADE,
            FOREIGN KEY (codi_ingredient) REFERENCES ingredients(codi)
        );
    """)

    # Índex per velocitat quan consultem receptes
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_recepta_linies_recepta_id
        ON recepta_linies(recepta_id);
    """)

    conn.commit()
    conn.close()

    print("✅ Migració feta: creades taules receptes i recepta_linies a", DB_PATH)


if __name__ == "__main__":
    main()
