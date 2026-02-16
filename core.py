import csv
from datetime import datetime
from typing import List, Tuple, Optional
import os
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials


SHEETS_COLUMNS = [
    "Tema",
    "Pregunta",
    "Resposta",
    "Estat",
    "Data creació",
    "Darrera modificació",
    "Persona darrera modificació",
    "Dades amb actualització anual",
    "Font",
]

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

def get_oauth_client(oauth_client_json: str = "oauth_client.json", token_file: str = "token.json"):
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, OAUTH_SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(oauth_client_json, OAUTH_SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return gspread.authorize(creds)

def export_rows_to_google_sheets_oauth(
    rows: list[list[str]],
    spreadsheet_name: str,
    worksheet_name: str = "FAQs",
    oauth_client_json: str = "oauth_client.json",
    token_file: str = "token.json",
    log=None
):
    def _log(m):
        if log: log(m)

    client = get_oauth_client(oauth_client_json=oauth_client_json, token_file=token_file)

    # Obrir o crear el spreadsheet
    try:
        sh = client.open(spreadsheet_name)
        _log(f"📄 Obert Sheet: {spreadsheet_name}")
    except Exception:
        sh = client.create(spreadsheet_name)
        _log(f"🆕 Creat Sheet: {spreadsheet_name}")

    # Obrir o crear worksheet
    try:
        ws = sh.worksheet(worksheet_name)
    except Exception:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=len(SHEETS_COLUMNS))

    # Si està buit, posa capçalera
    if not ws.get_all_values():
        ws.append_row(SHEETS_COLUMNS, value_input_option="RAW")

    # Escriu dades
    if rows:
        ws.append_rows(rows, value_input_option="RAW")
        _log(f"✅ Files afegides: {len(rows)}")

# ---------- GOOGLE ----------
def get_client(credentials_json: str):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(credentials_json, scopes=scopes)
    return gspread.authorize(creds)


def open_ws(client, spreadsheet_title: str, worksheet_name: str):
    sh = client.open(spreadsheet_title)
    return sh.worksheet(worksheet_name)


# ---------- INPUT ----------
def read_sources_csv(path: str) -> List[Tuple[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        out = []
        for r in reader:
            url = (r.get("URL") or r.get("url") or "").strip()
            topic = (r.get("topic") or r.get("Topic") or "").strip()
            if url:
                out.append((url, topic))
        return out


def read_sources_sheet(credentials_json: str, spreadsheet_title: str, worksheet_name: str) -> List[Tuple[str, str]]:
    client = get_client(credentials_json)
    ws = open_ws(client, spreadsheet_title, worksheet_name)
    rows = ws.get_all_records()

    out = []
    for r in rows:
        url = str(r.get("URL") or r.get("url") or "").strip()
        topic = str(r.get("topic") or r.get("Topic") or "").strip()
        if url:
            out.append((url, topic))
    return out


# ---------- SCRAPE ----------
def scrape_faqs(url: str) -> List[Tuple[str, str]]:
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


# ---------- OUTPUT ----------
def export_like_sheets_csv(rows: list[list[str]], output_path: str):
    try:
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")  # Excel ES
            w.writerow(SHEETS_COLUMNS)
            w.writerows(rows)
    except PermissionError:
        raise PermissionError(
            f"No puc escriure '{output_path}'. Tanca el fitxer si el tens obert (Excel) o tria un altre nom."
        )


def export_like_sheets_sheet(credentials_json: str, spreadsheet_title: str, worksheet_name: str, rows: list[list[str]]):
    client = get_client(credentials_json)
    ws = open_ws(client, spreadsheet_title, worksheet_name)

    values = ws.get_all_values()
    if not values:
        ws.append_row(SHEETS_COLUMNS, value_input_option="RAW")

    if rows:
        ws.append_rows(rows, value_input_option="RAW")


# ---------- PIPELINE ----------
def run_pipeline(
    input_mode: str,                   # "csv" o "sheets"
    output_mode: str,                  # "csv" o "sheets"

    sources_csv_path: Optional[str] = None,
    sources_sheet_title: Optional[str] = None,
    sources_sheet_tab: Optional[str] = None,

    output_csv_path: Optional[str] = None,
    output_sheet_title: Optional[str] = None,
    output_sheet_tab: Optional[str] = None,

    credentials_json: Optional[str] = None,
    log=None
):
    def _log(msg: str):
        if log:
            log(msg)

    # --- INPUT ---
    if input_mode == "csv":
        if not sources_csv_path:
            raise RuntimeError("Falta el fitxer sources.csv")
        sources = read_sources_csv(sources_csv_path)
    else:
        if not credentials_json:
            raise RuntimeError("Falten credencials per llegir de Google Sheets.")
        if not (sources_sheet_title and sources_sheet_tab):
            raise RuntimeError("Falten dades del Google Sheet de sources (títol i pestanya).")
        sources = read_sources_sheet(credentials_json, sources_sheet_title, sources_sheet_tab)

    _log(f"📥 Sources llegides: {len(sources)}")

    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    estat_default = "Pendent"
    persona_default = "Agent IA"
    anual_default = "-"

    out_rows = []
    for i, (url, topic) in enumerate(sources, start=1):
        _log(f"\n[{i}/{len(sources)}] Processant URL: {url}")
        _log(f"   Topic: {topic}")

        faqs = scrape_faqs(url)
        _log(f"   FAQs trobades: {len(faqs)}")

        for pregunta, resposta in faqs:
            out_rows.append([
                topic,
                pregunta.strip(),
                resposta.strip(),
                estat_default,
                now_ts,
                now_ts,
                persona_default,
                anual_default,
                url,
            ])

    # --- OUTPUT ---
    if output_mode == "csv":
        if not output_csv_path:
            raise RuntimeError("Falta el fitxer CSV de sortida.")
        export_like_sheets_csv(out_rows, output_csv_path)
        _log(f"\n📤 Exportat a CSV: {output_csv_path}")
    else:
        if not credentials_json:
            raise RuntimeError("Falten credencials per escriure a Google Sheets.")
        if not (output_sheet_title and output_sheet_tab):
            raise RuntimeError("Falten dades del Google Sheet de sortida (títol i pestanya).")
        export_like_sheets_sheet(credentials_json, output_sheet_title, output_sheet_tab, out_rows)
        _log(f"\n📤 Exportat a Google Sheets: {output_sheet_title} / {output_sheet_tab}")

    _log(f"✅ Total files exportades: {len(out_rows)}")
    return {"total_urls": len(sources), "total_rows": len(out_rows)}

def build_rows_from_sources(sources_csv: str, log=None):
    # és literalment el teu run_pipeline_export_csv però EN LLOC d’escriure, retorna out_rows
    ...
    return out_rows, {"total_urls": len(sources), "total_rows": len(out_rows)}
