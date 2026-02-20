import csv
import json
import os
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

import requests
from bs4 import BeautifulSoup

import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow



# ---------- Constants ----------
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
    "https://www.googleapis.com/auth/drive",
]


# ---------- OAuth (Google login) ----------
def get_oauth_client(oauth_client_json="oauth_client.json", token_file="token.json"):
    creds = None
    if os.path.exists(token_file):
        creds = OAuthCredentials.from_authorized_user_file(token_file, OAUTH_SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(oauth_client_json, OAUTH_SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return gspread.authorize(creds)


def get_client(credentials_json: str):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_service_account_file(credentials_json, scopes=scopes)
    return gspread.authorize(creds)


def open_sheet_by_title(client, spreadsheet_title: str):
    return client.open(spreadsheet_title)


def open_or_create_worksheet(sh, worksheet_name: str, rows: int = 1000, cols: int = 12):
    try:
        return sh.worksheet(worksheet_name)
    except Exception:
        return sh.add_worksheet(title=worksheet_name, rows=rows, cols=cols)


# ---------- INPUT ----------
def read_sources_csv(path: str) -> List[Tuple[str, str]]:
    """
    Accepta CSV amb o sense capçalera.
    - Amb capçalera: URL/topic (o variants)
    - Sense capçalera: col1=url, col2=topic
    Detecta delimitador , o ;
    """
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)

        # delimiter
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except Exception:
            dialect = csv.excel
            dialect.delimiter = ","

        # header?
        try:
            has_header = csv.Sniffer().has_header(sample)
        except Exception:
            has_header = False

        def parse_with_header() -> List[Tuple[str, str]]:
            reader = csv.DictReader(f, dialect=dialect)
            out_local: List[Tuple[str, str]] = []
            for r in reader:
                url = (r.get("URL") or r.get("url") or r.get("Url") or r.get("link") or "").strip()
                topic = (r.get("topic") or r.get("Topic") or r.get("tema") or r.get("Tema") or "").strip()
                if url:
                    out_local.append((url, topic))
            return out_local

        def parse_without_header() -> List[Tuple[str, str]]:
            reader = csv.reader(f, dialect=dialect)
            out_local: List[Tuple[str, str]] = []
            for row in reader:
                if not row:
                    continue
                first = (row[0] if len(row) > 0 else "").strip()
                if not first:
                    continue
                # si l'usuari ha posat "URL" a la primera fila, salta-la
                if first.lower() in ("url", "link"):
                    continue
                url = first
                topic = (row[1] if len(row) > 1 else "").strip()
                out_local.append((url, topic))
            return out_local

        if has_header:
            out = parse_with_header()
            if not out:
                f.seek(0)
                out = parse_without_header()
        else:
            out = parse_without_header()

        return out


# ---------- SCRAPE ----------
def scrape_faqs(url: str, log=None, debug: bool = False) -> List[Tuple[str, str]]:
    """
    Suporta dos formats:
    1) UPC antic (collapse-base / data-toggle="collapse")
    2) Genweb/Bootstrap 5 accordion (accordion-item / data-bs-target)
    """
    def _log(m: str):
        if log:
            log(m)

    r = requests.get(
        url,
        timeout=25,
        allow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "ca,en;q=0.8,es;q=0.7",
        },
    )

    if debug:
        _log(f"DEBUG status: {r.status_code} | final_url: {r.url} | bytes: {len(r.text)}")

    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    faqs: List[Tuple[str, str]] = []

    # --- Format 1: UPC antic ---
    q_tags = soup.select('#collapse-base a[data-toggle="collapse"][href^="#collapse-"]')
    if q_tags:
        for q in q_tags:
            question = q.get_text(" ", strip=True)
            target_id = q.get("href", "").lstrip("#")
            collapse_div = soup.find(id=target_id)
            if not collapse_div:
                continue
            body = collapse_div.select_one(".panel-body") or collapse_div
            answer = body.get_text(" ", strip=True)
            if question and answer:
                faqs.append((question, answer))

        if faqs:
            return faqs

    # --- Format 2: Bootstrap 5 accordion ---
    # Mètode 2.1: per cada accordion-item
    items = soup.select(".accordion-item")
    if debug:
        _log(f"DEBUG accordion-item: {len(items)}")

    for item in items:
        q_btn = item.select_one("button.accordion-button")
        a_body = item.select_one(".accordion-body")
        q = q_btn.get_text(" ", strip=True) if q_btn else ""
        a = a_body.get_text(" ", strip=True) if a_body else ""
        if q and a:
            faqs.append((q, a))

    if faqs:
        return faqs

    # Mètode 2.2: més robust via data-bs-target
    btns = soup.select('button.accordion-button[data-bs-target]')
    if debug:
        _log(f"DEBUG buttons with data-bs-target: {len(btns)}")

    for btn in btns:
        q = btn.get_text(" ", strip=True)
        target = (btn.get("data-bs-target") or "").strip()
        if not target.startswith("#"):
            continue
        panel = soup.select_one(target)
        if not panel:
            continue
        body = panel.select_one(".accordion-body") or panel
        a = body.get_text(" ", strip=True)
        if q and a:
            faqs.append((q, a))

    return faqs


# ---------- BUILD ----------
def build_outputs(
    sources: List[Tuple[str, str]],
    log=None,
    debug: bool = False,
) -> Tuple[List[List[str]], List[Dict[str, Any]], Dict[str, int], List[Dict[str, str]]]:
    """
    Retorna:
      - rows_for_csv_or_sheets: format SHEETS_COLUMNS
      - genweb_blocks: [{topic, source_url, items:[{q,a}]}]
      - stats
      - errors: [{url, topic, error}]
    """
    def _log(m: str):
        if log:
            log(m)

    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    estat_default = "Pendent"
    persona_default = "Agent IA"
    anual_default = "-"

    out_rows: List[List[str]] = []
    genweb_blocks: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    total_faqs = 0
    ok_urls = 0

    for i, (url, topic) in enumerate(sources, start=1):
        _log(f"\n[{i}/{len(sources)}] Processing URL: {url}")
        _log(f"    Topic: {topic}")

        try:
            faqs = scrape_faqs(url, log=log, debug=debug)
            _log(f"    FAQs found: {len(faqs)}")
            ok_urls += 1

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

            genweb_blocks.append({
                "topic": topic,
                "source_url": url,
                "items": [{"q": q.strip(), "a": a.strip()} for (q, a) in faqs]
            })

            total_faqs += len(faqs)

        except Exception as e:
            err = str(e)
            errors.append({"url": url, "topic": topic, "error": err})
            _log(f"⚠️ Error processing URL: {url}")
            _log(f"    → {err}")

            # també afegim bloc buit al JSON (opcional)
            genweb_blocks.append({
                "topic": topic,
                "source_url": url,
                "items": []
            })

    stats = {
        "total_urls": len(sources),
        "ok_urls": ok_urls,
        "total_errors": len(errors),
        "total_rows": len(out_rows),
        "total_faqs": total_faqs,
        "total_json_blocks": len(genweb_blocks),
    }
    return out_rows, genweb_blocks, stats, errors


# ---------- OUTPUT: CSV ----------
def export_like_sheets_csv(rows: List[List[str]], output_path: str):
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(SHEETS_COLUMNS)
        w.writerows(rows)


# ---------- OUTPUT: Sheets (OAuth) ----------
def export_rows_to_google_sheets_oauth(
    rows: List[List[str]],
    spreadsheet_title: str,
    worksheet_name: str,
    oauth_client_json: str = "oauth_client.json",
    token_file: str = "token.json",
    log=None
):
    def _log(m: str):
        if log:
            log(m)

    client = get_oauth_client(oauth_client_json=oauth_client_json, token_file=token_file)

    # 1) Obrir o crear spreadsheet
    try:
        sh = client.open(spreadsheet_title)
        _log(f"📄 Spreadsheet obert: {spreadsheet_title}")
    except Exception:
        sh = client.create(spreadsheet_title)
        _log(f"🆕 Spreadsheet creat: {spreadsheet_title}")

    # IMPORTANT: mostra ID i URL (això et garanteix que estàs mirant el correcte)
    try:
        _log(f"🔗 Spreadsheet URL: https://docs.google.com/spreadsheets/d/{sh.id}")
        _log(f"🆔 Spreadsheet ID: {sh.id}")
    except Exception:
        pass

    # 2) Obrir o crear pestanya
    try:
        ws = sh.worksheet(worksheet_name)
        _log(f"📑 Pestanya oberta: {worksheet_name}")
    except Exception:
        ws = sh.add_worksheet(
            title=worksheet_name,
            rows=max(1000, len(rows) + 10),
            cols=len(SHEETS_COLUMNS)
        )
        _log(f"🆕 Pestanya creada: {worksheet_name}")

    # 3) Capçalera: considera buit també el cas [ [] ] o tot buid
    values = ws.get_all_values()
    is_truly_empty = (
        not values or
        all((not r) or all((c or "").strip() == "" for c in r) for r in values)
    )

    if is_truly_empty:
        ws.clear()  # deixa el full net del tot
        ws.append_row(SHEETS_COLUMNS, value_input_option="RAW")
        _log("🧾 Capçalera afegida")

    # 4) Escriure files
    if rows:
        ws.append_rows(rows, value_input_option="RAW")
        _log(f"✅ Rows appended: {len(rows)}")
    else:
        _log("ℹ️ No hi ha files per escriure (0 rows).")

    # 5) Verificació ràpida (per saber si realment hi ha dades al sheet)
    try:
        after = ws.get_all_values()
        _log(f"🔎 Files totals al full (inclosa capçalera): {len(after)}")
    except Exception:
        pass

    ws.update_acell("K1", f"LAST_WRITE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# ---------- OUTPUT: Genweb JSON ----------
def export_genweb_json(blocks: List[Dict[str, Any]], output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(blocks, f, ensure_ascii=False, indent=2)


# ---------- PIPELINE ----------
def run_pipeline(
    input_mode: str,                    # "csv"
    output_mode: str,                   # "csv" | "sheets_oauth" | "genweb_json"

    sources_csv_path: Optional[str] = None,

    output_file_path: Optional[str] = None,  # per csv o genweb_json

    output_sheet_title: Optional[str] = None,
    output_sheet_tab: Optional[str] = None,

    oauth_client_json: str = "oauth_client.json",
    token_file: str = "token.json",

    log=None,
    debug: bool = False,
):
    def _log(m: str):
        if log:
            log(m)

    # --- Load sources ---
    if input_mode != "csv":
        raise RuntimeError("Aquesta versió de l’app només accepta ENTRADA per CSV.")

    if not sources_csv_path:
        raise RuntimeError("Falta el fitxer CSV d’entrada.")

    sources = read_sources_csv(sources_csv_path)
    _log(f"📥 Sources loaded: {len(sources)}")

    if not sources:
        raise RuntimeError("No s’han trobat URLs al CSV. Revisa el format (URL a la 1a columna).")

    # --- Scrape + build ---
    rows, blocks, stats, errors = build_outputs(sources, log=log, debug=debug)

    # --- Export ---
    if output_mode == "csv":
        if not output_file_path:
            raise RuntimeError("Falta el fitxer CSV de sortida.")
        export_like_sheets_csv(rows, output_file_path)
        _log(f"📄 CSV written: {output_file_path}")

    elif output_mode == "genweb_json":
        if not output_file_path:
            raise RuntimeError("Falta el fitxer JSON de sortida.")
        export_genweb_json(blocks, output_file_path)
        _log(f"🧩 Genweb JSON written: {output_file_path}")


    elif output_mode == "sheets_oauth":

        if not (output_sheet_title and output_sheet_tab):
            raise RuntimeError("Falta el títol o la pestanya del Google Sheet de sortida.")

        try:

            export_rows_to_google_sheets_oauth(

                rows=rows,

                spreadsheet_title=output_sheet_title,

                worksheet_name=output_sheet_tab,

                oauth_client_json=oauth_client_json,

                token_file=token_file,

                log=log

            )

            _log(f"📤 Exported to Google Sheets: {output_sheet_title} / {output_sheet_tab}")


        except Exception as e:

            _log(f"❌ Error exportant a Google Sheets: {type(e).__name__}: {e}")

            # Intentar treure detalls si és un APIError de gspread

            try:

                import gspread

                if isinstance(e, gspread.exceptions.APIError):

                    _log(f"❌ APIError raw response: {getattr(e, 'response', None)}")

                    try:

                        _log(f"❌ APIError response text: {e.response.text[:1200]}")

                    except Exception:

                        pass

            except Exception:

                pass

            raise

    else:
        raise RuntimeError("output_mode ha de ser 'csv', 'sheets_oauth' o 'genweb_json'.")



    return stats
