import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime


# SCRAPING obtenir les preguntes i respostes
def scrape_faqs(url: str):
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    q_tags = soup.select('#collapse-base a[data-toggle="collapse"][href^="#collapse-"]')
    faqs = []

    for q in q_tags:
        question = q.get_text(" ", strip=True)

        target_id = q.get("href", "").lstrip("#")
        collapse_div = soup.find(id=target_id)
        if not collapse_div:
            continue

        body = collapse_div.select_one(".panel-body") or collapse_div
        answer = body.get_text(" ", strip=True)

        faqs.append((question, answer))

    return faqs

# GOOGLE SHEETS obtenir la pagina de google sheets on anirà
def get_worksheet_by_title(spreadsheet_title: str, worksheet_name: str):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    client = gspread.authorize(creds)

    # IMPORTANT: open() busca per títol a Drive. Si hi ha duplicats, pot confondre.
    sh = client.open(spreadsheet_title)
    ws = sh.worksheet(worksheet_name)

    # Debug útil: confirma on estàs escrivint
    print("CONNECTED SPREADSHEET TITLE:", sh.title)
    print("CONNECTED WORKSHEET TITLE:", ws.title)
    print("SPREADSHEET ID:", sh.id)

    return ws

# GOOGLE SHEETS Sincronitza les FAQs del web amb el full de càlcul aplicant control de duplicats i registre de canvis.
def append_with_traceability(ws, faqs, font_url: str):

    #1 Lectura del sheets
    values = ws.get_all_values()

    #2 Validació de la capçalera
    if not values:
        raise RuntimeError("El full està buit: falta la capçalera (fila 1).")
    header = values[0]

    #3 Obtenció dels índexs de columnes
    # Tema | Pregunta | Resposta | Estat | Data creació | Darrera modificació | Persona darrera modificació | Dades amb actualització anual | Font
    idx_tema = header.index("Tema")
    idx_preg = header.index("Pregunta")
    idx_resp = header.index("Resposta")
    idx_data_creacio = header.index("Data creació")
    idx_darrera_mod = header.index("Darrera modificació")
    idx_persona_mod = header.index("Persona darrera modificació")
    idx_font = header.index("Font")

    #4 Creació dels conjunts per evitar duplicats
    existing_questions = set()
    existing_pairs = set()
    question_to_row = {}  # (tema, pregunta) -> row_num (1-indexed)
    question_to_creation = {}  # (tema, pregunta) -> data_creacio_original

    #5 Recorregut de files existents
    for i, row in enumerate(values[1:], start=2):  # fila real a Sheets (1-indexed) ✅ NEW
        if len(row) <= max(idx_tema, idx_preg, idx_resp):
            continue
        tema = row[idx_tema].strip()
        preg = row[idx_preg].strip()
        resp = row[idx_resp].strip()
        existing_pairs.add((preg,resp))
        question_to_row[(tema, preg)] = i
        created = row[idx_data_creacio].strip() if len(row) > idx_data_creacio else ""
        if preg not in question_to_creation and created:
            question_to_creation[preg] = created

    #6 Generació del Timestamp
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    #7 Definició de valors per defecte
    tema_default = "-"         # segons el teu cap
    estat_default = "Pendent"
    persona_default = "Agent IA"
    anual_default = "-"
    last_modified_default = "" # “a mirar” → buit
    new_rows = []
    skipped_same = 0
    skipped_question_only = 0
    added_new = 0
    updated_changed = 0
    added_changed = 0

    #8 Recorregut de FAQs scrapejades
    for pregunta, resposta in faqs:
        pregunta = pregunta.strip()
        resposta = resposta.strip()

        pair_key = (pregunta, resposta)
        q_key = pregunta

        # 8.1 Mateixa pregunta i Mateixa resposta -> NO afegir
        if pair_key in existing_pairs:
            skipped_same += 1
            continue

        # 8.2 Mateixa pregunta i Diferent resposta -> Actualitzar
        if q_key in question_to_creation:
            added_changed += 1
            created_ts = question_to_creation[q_key]
        else:
            added_new += 1
            created_ts = now_ts  # primera vegada que la veiem

        # 8.3 Diferent pregunta i Diferent resposta -> afegeix nova fila
        new_rows.append([
            tema_default, pregunta, resposta, estat_default,
            created_ts, now_ts, persona_default, anual_default, font_url
        ])

    #9 Construcció de noves files
    before_rows = len(values)
    if new_rows:
        ws.append_rows(new_rows, value_input_option="RAW")
        after_rows = len(ws.get_all_values())
        print(f"OK: afegides {len(new_rows)} files.")
        print(f"- Noves (pregunta no existia): {added_new}")
        print(f"- Canvis (pregunta existia, resposta diferent): {added_changed}")
        print(f"- Saltades (mateixa pregunta i mateixa resposta): {skipped_same}")
        print(f"FILES ABANS: {before_rows} | FILES DESPRÉS: {after_rows}")
    else:
        print("OK: no s'ha afegit res (tot era duplicat exactament).")
        print(f"- Saltades (mateixa pregunta i mateixa resposta): {skipped_same}")
        print(f"FILES ACTUALS: {before_rows}")

# MAIN
if __name__ == "__main__":

    url = "https://www.upc.edu/ca/graus/faqs/preinscripcio-i-assignacio"

    faqs = scrape_faqs(url)
    print("TOTAL FAQS SCRAPEJADES:", len(faqs))

    SPREADSHEET_TITLE = "Proves-faqs-mentors"
    WORKSHEET_NAME = "FAQs"   # IMPORTANT: posa el nom exacte de la pestanya

    ws = get_worksheet_by_title(SPREADSHEET_TITLE, WORKSHEET_NAME)
    append_with_traceability(ws, faqs, font_url=url)
