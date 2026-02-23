import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import yaml
# import pandas as pd  # per si vols importar .csv

def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def read_sources_from_sheet(client, spreadsheet_title: str, worksheet_name: str):
    sh = client.open(spreadsheet_title)
    ws = sh.worksheet(worksheet_name)

    rows = ws.get_all_records()  # llegeix com a diccionaris (capçalera -> valor)
    sources = []
    for r in rows:
        url = str(r.get("URL", "")).strip()
        topic = str(r.get("Topic", "")).strip()

        if url:
            sources.append((url, topic))

    return sources

def get_gspread_client(credentials_file: str):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
    return gspread.authorize(creds)


# GOOGLE SHEETS obtenir la pàgina de Google Sheets on anirà
def get_worksheet_by_title(client, spreadsheet_title: str, worksheet_name: str):

    sh = client.open(spreadsheet_title)
    ws = sh.worksheet(worksheet_name)

    print("CONNECTED:", sh.title, "/", ws.title)
    print("SPREADSHEET ID:", sh.id)

    return ws

# GOOGLE SHEETS Sincronitza les FAQs del web amb el full de càlcul aplicant control de duplicats i registre de canvis.
def append_with_traceability(ws, faqs, font_url: str, topic: str):

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
        existing_pairs.add((tema, preg, resp))
        question_to_row[(tema, preg)] = i

        created = row[idx_data_creacio].strip() if len(row) > idx_data_creacio else ""
        key = (tema, preg)
        if key not in question_to_creation and created:
            question_to_creation[key] = created

    #6 Generació del Timestamp
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    #7 Definició de valors per defecte
    tema_default = topic         # segons el teu cap
    estat_default = "Pendent"
    persona_default = "Agent IA"
    anual_default = "-"
    last_modified_default = "" # “a mirar” → buit
    new_rows = []
    skipped_same = 0
    added_new = 0
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
        print(f"- S'ha afegit {len(new_rows)} files.")
        print(f"- Noves (pregunta diferent): {added_new}")
        print(f"- Canvis (pregunta igual, resposta diferent): {added_changed}")
        print(f"- Saltades (pregunta igual, resposta igual): {skipped_same}")
        print(f"FILES ABANS: {before_rows} | FILES DESPRÉS: {after_rows}")
    else:
        print()
        print(">>> No s'ha afegit res (tot era duplicat exactament).")
        print(f"- Saltades: {skipped_same} (pregunta igual i resposta igual)")
        print(f"FILES ACTUALS: {before_rows}")

# MAIN
if __name__ == "__main__":

    config = load_config()

    CREDENTIALS_FILE = config["credentials_file"]

    # 1) Client google
    client = get_gspread_client(CREDENTIALS_FILE)

    # 2) Llegeix sources (URL+topic) des del Sheet faqs-sources
    SRC_TITLE = config["sources_sheet"]["spreadsheet_title"]
    SRC_TAB = config["sources_sheet"]["worksheet_name"]
    sources = read_sources_from_sheet(client, SRC_TITLE, SRC_TAB)

    print("TOTAL FILES A PROCESSAR:", len(sources))

    # 3) Obre Sheet destí (on vas guardant FAQs)
    DEST_TITLE = config["google_sheets"]["spreadsheet_title"]
    DEST_TAB = config["google_sheets"]["worksheet_name"]
    dest_ws = get_worksheet_by_title(client, DEST_TITLE, DEST_TAB)

    # 4) Executa per cada fila
    for url, topic in sources:
        print(f"\nPROCESSANT: {url} | TOPIC: {topic}")
        try:
            faqs = scrape_faqs(url)
            print("FAQS TROBADES:", len(faqs))
            append_with_traceability(dest_ws, faqs, font_url=url, topic=topic)
        except Exception as e:
            print(f"⚠️ ERROR amb {url}: {e}")
            continue
