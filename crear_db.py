import sqlite3
from pathlib import Path

# Ruta base del projecte
BASE_DIR = Path(__file__).resolve().parent

# Ruta de la base de dades
DB_PATH = BASE_DIR / "dades" / "nutricio.db"

def crear_base_dades():
    # Assegurem que existeix la carpeta dades
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Connexió (això crea el fitxer .db)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingredients (
            codi TEXT PRIMARY KEY,
            ingredient TEXT NOT NULL,
            proveidor TEXT,
            unitat_base TEXT,
            data_fitxa TEXT,
            font TEXT,
            ingredient_compost TEXT,
            alergens TEXT,
            observacions TEXT,
            energia_kcal_100g REAL,
            energia_kj_100g REAL,
            greixos_100g REAL,
            greixos_saturats_100g REAL,
            hidrats_carboni_100g REAL,
            sucres_100g REAL,
            proteines_100g REAL,
            fibra_100g REAL,
            sal_100g REAL
        );
    """)

    conn.commit()
    conn.close()

    print("✅ Base de dades creada correctament a:", DB_PATH)

if __name__ == "__main__":
    crear_base_dades()
