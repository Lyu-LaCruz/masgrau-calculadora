import sqlite3
from pathlib import Path
from typing import Any, Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "dades" / "nutricio.db"
EXCEL_PATH = BASE_DIR / "dades" / "ingredients_maestre.xlsx"
SHEET_NAME = "ingredients"


COLS_OBLIGATORIES = [
    "codi",
    "ingredient",
    "proveidor",
    "unitat_base",
    "data_fitxa",
    "font",
    "ingredient_compost",
    "alergens",
    "observacions",
    "energia_kcal_100g",
    "energia_kj_100g",
    "greixos_100g",
    "greixos_saturats_100g",
    "hidrats_carboni_100g",
    "sucres_100g",
    "proteines_100g",
    "fibra_100g",
    "sal_100g",
]


NUMERIC_COLS = [
    "energia_kcal_100g",
    "energia_kj_100g",
    "greixos_100g",
    "greixos_saturats_100g",
    "hidrats_carboni_100g",
    "sucres_100g",
    "proteines_100g",
    "fibra_100g",
    "sal_100g",
]


def _to_float_or_none(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, float) and pd.isna(x):
        return None
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return None
        # Permetem coma decimal
        s = s.replace(",", ".")
        # Treiem espais
        s = s.replace(" ", "")
        try:
            return float(s)
        except ValueError:
            return None
    try:
        return float(x)
    except Exception:
        return None


def _clean_text(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, float) and pd.isna(x):
        return None
    s = str(x).strip()
    return s if s != "" else None


def carregar_excel() -> pd.DataFrame:
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"No s'ha trobat l'Excel: {EXCEL_PATH}")

    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, dtype=str)

    # Normalitzem noms de columnes (per si Excel afegeix espais)
    df.columns = [c.strip() for c in df.columns]

    faltants = [c for c in COLS_OBLIGATORIES if c not in df.columns]
    if faltants:
        raise ValueError(
            "Falten columnes a l'Excel: " + ", ".join(faltants)
        )

    # Netegem text
    for c in df.columns:
        if c in NUMERIC_COLS:
            continue
        df[c] = df[c].apply(_clean_text)

    # Convertim numèrics
    for c in NUMERIC_COLS:
        df[c] = df[c].apply(_to_float_or_none)

    # Eliminem files sense codi o ingredient
    df = df[df["codi"].notna() & df["ingredient"].notna()].copy()

    # Assegurem codi en majúscules i sense espais
    df["codi"] = df["codi"].astype(str).str.strip().str.upper()

    return df


def importar_a_sqlite(df: pd.DataFrame) -> tuple[int, int]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"No s'ha trobat la BD: {DB_PATH} (executa crear_db.py)")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    inserits = 0
    actualitzats = 0

    sql_upsert = """
    INSERT INTO ingredients (
        codi, ingredient, proveidor, unitat_base, data_fitxa, font,
        ingredient_compost, alergens, observacions,
        energia_kcal_100g, energia_kj_100g, greixos_100g, greixos_saturats_100g,
        hidrats_carboni_100g, sucres_100g, proteines_100g, fibra_100g, sal_100g
    )
    VALUES (
        :codi, :ingredient, :proveidor, :unitat_base, :data_fitxa, :font,
        :ingredient_compost, :alergens, :observacions,
        :energia_kcal_100g, :energia_kj_100g, :greixos_100g, :greixos_saturats_100g,
        :hidrats_carboni_100g, :sucres_100g, :proteines_100g, :fibra_100g, :sal_100g
    )
    ON CONFLICT(codi) DO UPDATE SET
        ingredient=excluded.ingredient,
        proveidor=excluded.proveidor,
        unitat_base=excluded.unitat_base,
        data_fitxa=excluded.data_fitxa,
        font=excluded.font,
        ingredient_compost=excluded.ingredient_compost,
        alergens=excluded.alergens,
        observacions=excluded.observacions,
        energia_kcal_100g=excluded.energia_kcal_100g,
        energia_kj_100g=excluded.energia_kj_100g,
        greixos_100g=excluded.greixos_100g,
        greixos_saturats_100g=excluded.greixos_saturats_100g,
        hidrats_carboni_100g=excluded.hidrats_carboni_100g,
        sucres_100g=excluded.sucres_100g,
        proteines_100g=excluded.proteines_100g,
        fibra_100g=excluded.fibra_100g,
        sal_100g=excluded.sal_100g
    ;
    """

    # Comptem inserits vs actualitzats mirant si existeix abans
    for _, row in df.iterrows():
        params = row.to_dict()

        cur.execute("SELECT 1 FROM ingredients WHERE codi = ?", (params["codi"],))
        exists = cur.fetchone() is not None

        cur.execute(sql_upsert, params)

        if exists:
            actualitzats += 1
        else:
            inserits += 1

    conn.commit()
    conn.close()
    return inserits, actualitzats


def main():
    print("📄 Llegint Excel:", EXCEL_PATH)
    df = carregar_excel()
    print(f"✅ Files vàlides a importar: {len(df)}")

    print("🗄️ Important a SQLite:", DB_PATH)
    inserits, actualitzats = importar_a_sqlite(df)

    print("✅ Importació completada")
    print(f"   - Inserits: {inserits}")
    print(f"   - Actualitzats: {actualitzats}")


if __name__ == "__main__":
    # Requereix: pip install pandas openpyxl
    main()
