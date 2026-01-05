# app.py
import qrcode
import sqlite3
from pathlib import Path
from flask import Flask, render_template, request, session, redirect, url_for, send_file
from io import BytesIO
from fpdf import FPDF
from datetime import datetime



BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "dades" / "nutricio.db"
LOGO_PATH = BASE_DIR / "static" / "img" / "logo_masgrau.png"

app = Flask(__name__)
app.secret_key = "masgrau_valor_nutricional_secret_key"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _recepta_linies_ingredient_col(conn: sqlite3.Connection) -> str:
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(recepta_linies);").fetchall()]
    if "ingredient_codi" in cols:
        return "ingredient_codi"
    if "codi" in cols:
        return "codi"
    raise RuntimeError("La taula 'recepta_linies' no té columna 'ingredient_codi' ni 'codi'.")


def guardar_recepta_a_db(nom_recepta: str, linies: list[dict]) -> int:
    nom_recepta = (nom_recepta or "").strip()
    if not nom_recepta:
        raise ValueError("El nom de la recepta és obligatori.")
    if not linies:
        raise ValueError("No hi ha ingredients per guardar.")

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute("INSERT INTO receptes (nom) VALUES (?)", (nom_recepta,))
        recepta_id = cur.lastrowid

        ing_col = _recepta_linies_ingredient_col(conn)
        sql = f"INSERT INTO recepta_linies (recepta_id, {ing_col}, grams) VALUES (?, ?, ?)"

        inserts = 0
        for linia in linies:
            codi = (linia.get("codi") or "").strip()
            try:
                grams = float(linia.get("grams", 0) or 0)
            except ValueError:
                grams = 0.0

            if not codi or grams <= 0:
                continue

            cur.execute(sql, (recepta_id, codi, grams))
            inserts += 1

        if inserts == 0:
            raise ValueError("No hi ha línies vàlides (grams > 0) per guardar.")

        conn.commit()
        return recepta_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def generar_pdf_recepta(
    nom_recepta: str,
    linies: list[dict],
    resultat_100g: dict | None,
    resultat_racio: dict | None
) -> BytesIO:
    nom_recepta = (nom_recepta or "").strip() or "Recepta sense nom"

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    # --- LOGO (debug + inserció) ---
    print("LOGO_PATH:", LOGO_PATH)
    print("EXISTE LOGO?:", LOGO_PATH.exists())

    try:
        if LOGO_PATH.exists():
            # Logo a dalt-esquerra (marges 15mm)
            pdf.image(str(LOGO_PATH), x=15, y=12, w=35)
        else:
            print("⚠️ No trobo el logo en aquesta ruta.")
    except Exception as e:
        print("❌ Error carregant logo:", e)

    # baixem el cursor perquè el títol no es solapi
    pdf.set_y(32)

    # --- LOGO (a dalt a l'esquerra) ---
    try:
        if LOGO_PATH.exists():
            pdf.image(str(LOGO_PATH), x=15, y=12, w=35)  # ajusta w si el vols més gran/petit
    except Exception:
        # Si el logo falla, no trenquem el PDF
        pass

    # Deixem espai perquè el títol no es solapi amb el logo
    pdf.set_y(32)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Recepta: {nom_recepta}", ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Generat: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Ingredients", ln=True)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(120, 7, "Ingredient", border=1)
    pdf.cell(30, 7, "Codi", border=1)
    pdf.cell(30, 7, "Grams", border=1, ln=True)

    pdf.set_font("Helvetica", "", 10)

    total_grams = 0.0
    for l in linies or []:
        ingredient = str(l.get("ingredient", "") or "")
        codi = str(l.get("codi", "") or "")
        grams = float(l.get("grams", 0) or 0)

        total_grams += grams

        if len(ingredient) > 60:
            ingredient = ingredient[:57] + "..."

        pdf.cell(120, 7, ingredient, border=1)
        pdf.cell(30, 7, codi, border=1)
        pdf.cell(30, 7, f"{grams:.2f}", border=1, ln=True)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(150, 7, "Pes total (g)", border=1)
    pdf.cell(30, 7, f"{total_grams:.2f}", border=1, ln=True)
    pdf.ln(6)

    if resultat_100g:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Informacio nutricional (per 100 g)", ln=True)

        pdf.set_font("Helvetica", "", 10)

        def fila(label, key):
            pdf.cell(90, 7, label, border=1)
            pdf.cell(0, 7, str(resultat_100g.get(key, "")), border=1, ln=True)

        fila("Energia (kcal)", "energia_kcal_100g")
        fila("Energia (kJ)", "energia_kj_100g")
        fila("Greixos (g)", "greixos_100g")
        fila("Greixos saturats (g)", "greixos_saturats_100g")
        fila("Hidrats de carboni (g)", "hidrats_carboni_100g")
        fila("Sucres (g)", "sucres_100g")
        fila("Proteines (g)", "proteines_100g")
        fila("Fibra (g)", "fibra_100g")
        fila("Sal (g)", "sal_100g")
        pdf.ln(6)

    if resultat_racio:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"Informacio nutricional (per racio: {resultat_racio.get('racio_g', '')} g)", ln=True)

        pdf.set_font("Helvetica", "", 10)

        def fila_r(label, key):
            pdf.cell(90, 7, label, border=1)
            pdf.cell(0, 7, str(resultat_racio.get(key, "")), border=1, ln=True)

        fila_r("Energia (kcal)", "energia_kcal")
        fila_r("Energia (kJ)", "energia_kj")
        fila_r("Greixos (g)", "greixos")
        fila_r("Greixos saturats (g)", "greixos_saturats")
        fila_r("Hidrats de carboni (g)", "hidrats_carboni")
        fila_r("Sucres (g)", "sucres")
        fila_r("Proteines (g)", "proteines")
        fila_r("Fibra (g)", "fibra")
        fila_r("Sal (g)", "sal")

    # --- COPYRIGHT (peu de pàgina) ---
    auto = pdf.auto_page_break
    margin = pdf.b_margin

    pdf.set_auto_page_break(auto=False)  # evita que creï una pàgina nova pel footer
    pdf.set_y(-15)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, "by Lyu La Cruz", align="C")

    pdf.set_auto_page_break(auto=auto, margin=margin)  # restaura

    output = BytesIO()
    pdf_data = pdf.output(dest="S")  # puede ser str o bytearray según versión
    if isinstance(pdf_data, str):
        pdf_bytes = pdf_data.encode("latin1")
    else:
        pdf_bytes = bytes(pdf_data)  # bytearray -> bytes
    output.write(pdf_bytes)
    output.seek(0)
    return output

def generar_qr(url: str) -> BytesIO:
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


def calcular_nutricio_per_100g(linies):
    if not linies:
        return None

    try:
        total_grams = sum(float(l["grams"]) for l in linies)
    except Exception:
        return None

    if total_grams <= 0:
        return None

    totals = {
        "energia_kcal": 0.0,
        "energia_kj": 0.0,
        "greixos": 0.0,
        "greixos_saturats": 0.0,
        "hidrats_carboni": 0.0,
        "sucres": 0.0,
        "proteines": 0.0,
        "fibra": 0.0,
        "sal": 0.0,
    }

    def v(x):
        return float(x) if x is not None else 0.0

    conn = get_db_connection()
    try:
        for l in linies:
            codi = (l.get("codi") or "").strip()
            try:
                grams = float(l.get("grams", 0) or 0)
            except ValueError:
                grams = 0.0

            if not codi or grams <= 0:
                continue

            row = conn.execute(
                """
                SELECT
                    energia_kcal_100g,
                    energia_kj_100g,
                    greixos_100g,
                    greixos_saturats_100g,
                    hidrats_carboni_100g,
                    sucres_100g,
                    proteines_100g,
                    fibra_100g,
                    sal_100g
                FROM ingredients
                WHERE codi = ?
                """,
                (codi,),
            ).fetchone()

            if row is None:
                continue

            factor = grams / 100.0
            totals["energia_kcal"] += v(row["energia_kcal_100g"]) * factor
            totals["energia_kj"] += v(row["energia_kj_100g"]) * factor
            totals["greixos"] += v(row["greixos_100g"]) * factor
            totals["greixos_saturats"] += v(row["greixos_saturats_100g"]) * factor
            totals["hidrats_carboni"] += v(row["hidrats_carboni_100g"]) * factor
            totals["sucres"] += v(row["sucres_100g"]) * factor
            totals["proteines"] += v(row["proteines_100g"]) * factor
            totals["fibra"] += v(row["fibra_100g"]) * factor
            totals["sal"] += v(row["sal_100g"]) * factor
    finally:
        conn.close()

    escala = 100.0 / total_grams
    return {
        "pes_total_g": round(total_grams, 2),
        "energia_kcal_100g": round(totals["energia_kcal"] * escala, 2),
        "energia_kj_100g": round(totals["energia_kj"] * escala, 2),
        "greixos_100g": round(totals["greixos"] * escala, 2),
        "greixos_saturats_100g": round(totals["greixos_saturats"] * escala, 2),
        "hidrats_carboni_100g": round(totals["hidrats_carboni"] * escala, 2),
        "sucres_100g": round(totals["sucres"] * escala, 2),
        "proteines_100g": round(totals["proteines"] * escala, 2),
        "fibra_100g": round(totals["fibra"] * escala, 2),
        "sal_100g": round(totals["sal"] * escala, 2),
    }


@app.route("/")
def inici():
    return render_template("inici.html")


@app.route("/receptes/pdf", methods=["POST"])
def descarregar_pdf_recepta():
    nom_recepta = (request.form.get("nom_recepta", "") or "").strip()
    linies = session.get("linies", [])

    if not linies:
        session["missatge"] = "❌ No hi ha ingredients a la recepta."
        return redirect(url_for("calculadora"))

    resultat_100g = calcular_nutricio_per_100g(linies)

    resultat_racio = None
    try:
        racio_g = float(session.get("racio_g", 0) or 0)
    except ValueError:
        racio_g = 0.0

    if resultat_100g and racio_g > 0:
        factor = racio_g / 100.0
        resultat_racio = {
            "racio_g": round(racio_g, 2),
            "energia_kcal": round(resultat_100g["energia_kcal_100g"] * factor, 2),
            "energia_kj": round(resultat_100g["energia_kj_100g"] * factor, 2),
            "greixos": round(resultat_100g["greixos_100g"] * factor, 2),
            "greixos_saturats": round(resultat_100g["greixos_saturats_100g"] * factor, 2),
            "hidrats_carboni": round(resultat_100g["hidrats_carboni_100g"] * factor, 2),
            "sucres": round(resultat_100g["sucres_100g"] * factor, 2),
            "proteines": round(resultat_100g["proteines_100g"] * factor, 2),
            "fibra": round(resultat_100g["fibra_100g"] * factor, 2),
            "sal": round(resultat_100g["sal_100g"] * factor, 2),
        }

    pdf_io = generar_pdf_recepta(nom_recepta, linies, resultat_100g, resultat_racio)

    safe_name = "".join(
        c for c in (nom_recepta or "recepta")
        if c.isalnum() or c in (" ", "_", "-")
    ).strip().replace(" ", "_")
    filename = f"{safe_name or 'recepta'}.pdf"

    return send_file(
        pdf_io,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


@app.route("/ingredients")
def ingredients():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                codi, ingredient, proveidor,
                energia_kcal_100g, energia_kj_100g
            FROM ingredients
            ORDER BY codi
            """
        ).fetchall()
    finally:
        conn.close()
    return render_template("ingredients.html", ingredients=rows)


@app.route("/calculadora", methods=["GET", "POST"])
def calculadora():
    if "linies" not in session:
        session["linies"] = []

    linies = session.get("linies", [])
    racio_str = session.get("racio_g", "")
    missatge = session.pop("missatge", "")

    conn = get_db_connection()
    try:
        ingredients = conn.execute(
            """
            SELECT codi, ingredient
            FROM ingredients
            ORDER BY ingredient
            """
        ).fetchall()
    finally:
        conn.close()

    if request.method == "POST":
        codi = (request.form.get("codi", "") or "").strip()
        unitat = (request.form.get("unitat", "g") or "g").strip()

        try:
            quantitat = float(request.form.get("quantitat", "0") or 0)
        except ValueError:
            quantitat = 0.0

        racio_form = (request.form.get("racio_g", "") or "").strip()
        session["racio_g"] = racio_form
        racio_str = racio_form

        grams = quantitat * 1000 if unitat == "kg" else quantitat

        nom = ""
        for it in ingredients:
            if it["codi"] == codi:
                nom = it["ingredient"]
                break

        trobat = False
        for item in linies:
            if item.get("codi") == codi:
                item["grams"] = round(float(item.get("grams", 0) or 0) + grams, 2)
                trobat = True
                break

        if not trobat:
            linies.append({"codi": codi, "ingredient": nom, "grams": round(grams, 2)})

        session["linies"] = linies

    resultat = calcular_nutricio_per_100g(session.get("linies", []))

    try:
        racio_g = float(racio_str or 0)
    except ValueError:
        racio_g = 0.0

    resultat_racio = None
    if resultat and racio_g > 0:
        factor = racio_g / 100.0
        resultat_racio = {
            "racio_g": round(racio_g, 2),
            "energia_kcal": round(resultat["energia_kcal_100g"] * factor, 2),
            "energia_kj": round(resultat["energia_kj_100g"] * factor, 2),
            "greixos": round(resultat["greixos_100g"] * factor, 2),
            "greixos_saturats": round(resultat["greixos_saturats_100g"] * factor, 2),
            "hidrats_carboni": round(resultat["hidrats_carboni_100g"] * factor, 2),
            "sucres": round(resultat["sucres_100g"] * factor, 2),
            "proteines": round(resultat["proteines_100g"] * factor, 2),
            "fibra": round(resultat["fibra_100g"] * factor, 2),
            "sal": round(resultat["sal_100g"] * factor, 2),
        }

    return render_template(
        "calculadora.html",
        ingredients=ingredients,
        linies=session.get("linies", []),
        resultat=resultat,
        resultat_racio=resultat_racio,
        racio_g=racio_str,
        missatge=missatge,
    )


@app.route("/calculadora/netejar", methods=["POST"])
def netejar_calculadora():
    session["linies"] = []
    session["racio_g"] = ""
    return redirect(url_for("calculadora"))

@app.route("/qr", methods=["GET"])
def descarregar_qr():
    url = request.host_url.rstrip("/") + url_for("calculadora")
    qr_io = generar_qr(url)

    return send_file(
        qr_io,
        mimetype="image/png",
        as_attachment=True,
        download_name="qr_calculadora_masgrau.png"
    )


@app.route("/calculadora/eliminar/<int:index>", methods=["POST"])
def eliminar_linia(index):
    linies = session.get("linies", [])
    if 0 <= index < len(linies):
        linies.pop(index)
        session["linies"] = linies
    return redirect(url_for("calculadora"))


@app.route("/receptes/guardar", methods=["POST"])
def guardar_recepta_post():
    nom_recepta = (request.form.get("nom_recepta", "") or "").strip()
    linies = session.get("linies", [])

    try:
        recepta_id = guardar_recepta_a_db(nom_recepta, linies)
        session["missatge"] = f"✅ Recepta guardada (ID {recepta_id}): {nom_recepta}"
    except Exception as e:
        session["missatge"] = f"❌ No s'ha pogut guardar: {e}"

    return redirect(url_for("calculadora"))


if __name__ == "__main__":
    app.run(debug=True)
