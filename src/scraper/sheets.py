import re
import os
from datetime import datetime
from typing import Dict, List
from bs4 import BeautifulSoup, NavigableString

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

try:
    from .constants import OAUTH_SCOPES, SHEETS_COLUMNS
except ImportError:
    from constants import OAUTH_SCOPES, SHEETS_COLUMNS


SHEETS_TOPIC_OPTIONS = [
    "Dobles Graus",
    "Doctoral Studies",
    "Doctorats",
    "Final Thesis",
    "Guidance (MEM/MASE)",
    "Masters",
    "Mobilitat",
    "Orientació",
    "Pràctiques empresa",
    "TFE",
]


def get_oauth_client(oauth_client_json="oauth_client.json", token_file="token.json"):
    def _resolve_token_path(path: str) -> str:
        p = (path or "").strip() or "token.json"
        if os.path.isabs(p):
            return p
        appdata = os.getenv("APPDATA")
        if appdata:
            base_dir = os.path.join(appdata, "UPCFAQScraper")
        else:
            base_dir = os.path.join(os.path.expanduser("~"), ".upc_faq_scraper")
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, p)

    token_file = _resolve_token_path(token_file)
    creds = None
    try:
        if os.path.exists(token_file):
            creds = OAuthCredentials.from_authorized_user_file(token_file, OAUTH_SCOPES)
    except Exception:
        creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(oauth_client_json, OAUTH_SCOPES)
            creds = flow.run_local_server(port=0)
            with open(token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception as e:
            raise RuntimeError(f"OAuth error: {_format_google_error(e)}") from e

    return gspread.authorize(creds)


def _format_google_error(e: Exception) -> str:
    response = getattr(e, "response", None)
    if response is not None:
        code = getattr(response, "status_code", "?")
        txt = ""
        try:
            txt = (response.text or "").strip()
        except Exception:
            txt = ""
        if txt:
            txt = re.sub(r"\s+", " ", txt)
            return f"HTTP {code} - {txt[:300]}"
        return f"HTTP {code}"
    return str(e)


def _open_sheet_lenient(client, spreadsheet_title: str, log=None, spreadsheet_id: str | None = None):
    def _log(m: str):
        if log:
            log(m)

    sheet_id = (spreadsheet_id or "").strip()
    if sheet_id:
        _log(f"Intentant obrir Google Sheet per ID: {sheet_id}")
        try:
            return client.open_by_key(sheet_id)
        except Exception:
            pass

    title = (spreadsheet_title or "").strip()
    if not title:
        raise RuntimeError("El títol del Google Sheet està buit.")

    _log(f"Intentant obrir Google Sheet per títol exacte: {title}")
    try:
        return client.open(title)
    except Exception:
        pass

    # Fallback més lleuger que openall(): consulta de fitxers de spreadsheet.
    try:
        files = client.list_spreadsheet_files()
    except Exception as e:
        raise RuntimeError(f"No s'han pogut llistar els teus Google Sheets: {_format_google_error(e)}") from e

    normalized = title.casefold()
    exact_ci = [f for f in files if (f.get("name", "") or "").strip().casefold() == normalized]
    if exact_ci:
        key = exact_ci[0].get("id")
        if key:
            _log(f"Sheet trobat (coincidència insensitive): {exact_ci[0].get('name', '')}")
            return client.open_by_key(key)

    partial = [f for f in files if normalized in (f.get("name", "") or "").strip().casefold()]
    if len(partial) == 1:
        key = partial[0].get("id")
        if key:
            _log(f"Sheet trobat (coincidència parcial única): {partial[0].get('name', '')}")
            return client.open_by_key(key)

    sample = ", ".join((f.get("name", "") or "") for f in files[:8])
    if partial:
        opts = ", ".join((f.get("name", "") or "") for f in partial[:8])
        raise RuntimeError(
            f"No s'ha trobat una coincidència única per '{title}'. Coincidències: {opts}"
        )

    raise RuntimeError(
        f"No s'ha trobat cap Google Sheet amb títol '{title}'. "
        f"Comprova compte Google autoritzat i títol exacte. Exemples trobats: {sample}"
    )


def get_client(credentials_json: str):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
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


def export_rows_to_google_sheets_oauth(
    rows: List[List[str]],
    spreadsheet_title: str,
    worksheet_name: str,
    spreadsheet_id: str | None = None,
    oauth_client_json: str = "oauth_client.json",
    token_file: str = "token.json",
    log=None,
):
    def _log(m: str):
        if log:
            log(m)

    def _norm(s: str) -> str:
        s = (s or "").replace("\u00a0", " ")
        return re.sub(r"\s+", " ", s).strip()

    def _qkey(row: List[str]) -> tuple[str, str, str, str]:
        topic = _norm(row[0]) if len(row) > 0 else ""
        subtopic = _norm(row[1]) if len(row) > 1 else ""
        pregunta = _norm(row[2]) if len(row) > 2 else ""
        font = _norm(row[9]) if len(row) > 9 else ""
        return (topic, subtopic, pregunta, font)

    def _ans(row: List[str]) -> str:
        return _norm(row[3]) if len(row) > 3 else ""

    def _html_to_sheet_text(value: str) -> str:
        text = (value or "").strip()
        if not text or ("<" not in text or ">" not in text):
            return text

        try:
            soup = BeautifulSoup(text, "html.parser")
        except Exception:
            return text

        def _render(node) -> str:
            if isinstance(node, NavigableString):
                return str(node)

            name = getattr(node, "name", "") or ""
            name = name.lower()

            if name == "br":
                return "\n"

            if name == "a":
                href = (node.get("href") or "").strip()
                label = "".join(_render(c) for c in node.children).strip()
                if href and label and label != href:
                    return f"{label} ({href})"
                return href or label

            inner = "".join(_render(c) for c in node.children)

            if name in {"b", "strong"}:
                return f"**{inner.strip()}**" if inner.strip() else ""
            if name in {"i", "em"}:
                return f"*{inner.strip()}*" if inner.strip() else ""
            if name == "li":
                return f"- {inner.strip()}\n" if inner.strip() else ""
            if name in {"p", "div"}:
                return f"{inner.strip()}\n\n" if inner.strip() else ""
            if name in {"ul", "ol"}:
                return f"{inner.strip()}\n" if inner.strip() else ""

            return inner

        rendered = "".join(_render(n) for n in soup.contents)
        rendered = rendered.replace("\r\n", "\n").replace("\r", "\n")
        rendered = re.sub(r"\n{3,}", "\n\n", rendered)
        rendered = re.sub(r"[ \t]+", " ", rendered)
        rendered = re.sub(r" *\n *", "\n", rendered)
        return rendered.strip()

    def _ensure_status_default(value: str) -> str:
        v = (value or "").strip()
        return v if v in {"Aprovat", "Pendent", "Rebutjat"} else "Pendent"

    def _collect_subtopic_options(existing_rows: List[List[str]], pending_rows: List[List[str]]) -> List[str]:
        options: List[str] = []
        seen: set[str] = set()
        for row in list(existing_rows) + list(pending_rows):
            value = _norm(row[1]) if len(row) > 1 else ""
            if not value or value in seen:
                continue
            seen.add(value)
            options.append(value)
        return options

    def _build_review_table_columns(subtopic_options: List[str] | None = None) -> List[Dict[str, object]]:
        topic_dropdown_values = [
            {"userEnteredValue": topic}
            for topic in SHEETS_TOPIC_OPTIONS
        ]
        subtopic_dropdown_values = [
            {"userEnteredValue": subtopic}
            for subtopic in (subtopic_options or [])
        ]
        columns: List[Dict[str, object]] = []
        for idx, name in enumerate(SHEETS_COLUMNS):
            column: Dict[str, object] = {
                "columnIndex": idx,
                "columnName": name,
                "columnType": "TEXT",
            }
            if idx == 0:
                column["columnType"] = "DROPDOWN"
                column["dataValidationRule"] = {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": topic_dropdown_values,
                    }
                }
            if idx == 1 and subtopic_dropdown_values:
                column["columnType"] = "DROPDOWN"
                column["dataValidationRule"] = {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": subtopic_dropdown_values,
                    }
                }
            columns.append(column)
        return columns

    def _sync_review_table_with_status_chips(
        worksheet,
        used_row_count: int,
        subtopic_options: List[str] | None = None,
    ):
        sheet_id = worksheet.id
        table_name = f"UPCFAQTable_{sheet_id}"
        table_range = {
            "sheetId": sheet_id,
            "startRowIndex": 0,
            "endRowIndex": max(2, used_row_count),
            "startColumnIndex": 0,
            "endColumnIndex": len(SHEETS_COLUMNS),
        }

        meta = worksheet.spreadsheet.fetch_sheet_metadata()
        sheet_meta = next(
            (
                sh_meta
                for sh_meta in meta.get("sheets", [])
                if sh_meta.get("properties", {}).get("sheetId") == sheet_id
            ),
            {},
        )
        existing_tables = sheet_meta.get("tables", []) or []
        target_table = next((table for table in existing_tables if table.get("name") == table_name), None)
        if target_table is None:
            target_table = next(
                (
                    table
                    for table in existing_tables
                    if table.get("range", {}).get("startColumnIndex") == 0
                    and table.get("range", {}).get("endColumnIndex") == len(SHEETS_COLUMNS)
                ),
                None,
            )

        table_payload: Dict[str, object] = {
            "name": table_name,
            "range": table_range,
            "rowsProperties": {
                "headerColorStyle": {"rgbColor": {"red": 0.95, "green": 0.95, "blue": 0.95}},
                "firstBandColorStyle": {"rgbColor": {"red": 1, "green": 1, "blue": 1}},
                "secondBandColorStyle": {"rgbColor": {"red": 1, "green": 1, "blue": 1}},
            },
            "columnProperties": _build_review_table_columns(subtopic_options=subtopic_options),
        }

        if target_table and target_table.get("tableId"):
            table_payload["tableId"] = target_table["tableId"]
            worksheet.spreadsheet.batch_update(
                {
                    "requests": [
                        {
                            "updateTable": {
                                "table": table_payload,
                                "fields": "name,range,rowsProperties,columnProperties",
                            }
                        }
                    ]
                }
            )
            return

        worksheet.spreadsheet.batch_update(
            {
                "requests": [
                    {
                        "addTable": {
                            "table": table_payload,
                        }
                    }
                ]
            }
        )

    def _enforce_header_row_format(worksheet, col_count: int):
        sheet_id = worksheet.id
        worksheet.spreadsheet.batch_update(
            {
                "requests": [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": col_count,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": {
                                        "red": 0.95,
                                        "green": 0.95,
                                        "blue": 0.95,
                                    },
                                    "textFormat": {
                                        "bold": True,
                                        "foregroundColor": {
                                            "red": 0.0,
                                            "green": 0.0,
                                            "blue": 0.0,
                                        },
                                    },
                                }
                            },
                            "fields": (
                                "userEnteredFormat.backgroundColor,"
                                "userEnteredFormat.textFormat.bold,"
                                "userEnteredFormat.textFormat.foregroundColor"
                            ),
                        }
                    }
                ]
            }
        )

    def _apply_review_sheet_formatting(
        worksheet,
        used_row_count: int,
        subtopic_options: List[str] | None = None,
    ):
        sheet_id = worksheet.id
        row_count = max(2, int(getattr(worksheet, "row_count", 1000) or 1000))
        col_count = max(len(SHEETS_COLUMNS), int(getattr(worksheet, "col_count", len(SHEETS_COLUMNS)) or len(SHEETS_COLUMNS)))

        # Neteja regles de format condicional existents d'aquesta pestanya per evitar duplicats.
        try:
            meta = worksheet.spreadsheet.fetch_sheet_metadata()
            for sh_meta in meta.get("sheets", []):
                props = sh_meta.get("properties", {})
                if props.get("sheetId") != sheet_id:
                    continue
                rules = sh_meta.get("conditionalFormats", []) or []
                if rules:
                    delete_reqs = [
                        {
                            "deleteConditionalFormatRule": {
                                "sheetId": sheet_id,
                                "index": idx,
                            }
                        }
                        for idx in range(len(rules) - 1, -1, -1)
                    ]
                    worksheet.spreadsheet.batch_update({"requests": delete_reqs})
                break
        except Exception:
            pass

        requests = [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": col_count,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0},
                            },
                        }
                    },
                    "fields": (
                        "userEnteredFormat.backgroundColor,"
                        "userEnteredFormat.textFormat.bold,"
                        "userEnteredFormat.textFormat.foregroundColor"
                    ),
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": row_count,
                        "startColumnIndex": 0,
                        "endColumnIndex": col_count,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "LEFT",
                            "verticalAlignment": "TOP",
                            "wrapStrategy": "WRAP",
                        }
                    },
                    "fields": (
                        "userEnteredFormat.horizontalAlignment,"
                        "userEnteredFormat.verticalAlignment,"
                        "userEnteredFormat.wrapStrategy"
                    ),
                }
            },
            {
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": max(1, used_row_count),
                        "startColumnIndex": 0,
                        "endColumnIndex": col_count,
                    },
                    "top": {
                        "style": "SOLID",
                        "width": 1,
                        "color": {"red": 0.84, "green": 0.86, "blue": 0.88},
                    },
                    "bottom": {
                        "style": "SOLID",
                        "width": 1,
                        "color": {"red": 0.84, "green": 0.86, "blue": 0.88},
                    },
                    "left": {
                        "style": "SOLID",
                        "width": 1,
                        "color": {"red": 0.84, "green": 0.86, "blue": 0.88},
                    },
                    "right": {
                        "style": "SOLID",
                        "width": 1,
                        "color": {"red": 0.84, "green": 0.86, "blue": 0.88},
                    },
                    "innerHorizontal": {
                        "style": "SOLID",
                        "width": 1,
                        "color": {"red": 0.84, "green": 0.86, "blue": 0.88},
                    },
                    "innerVertical": {
                        "style": "SOLID",
                        "width": 1,
                        "color": {"red": 0.84, "green": 0.86, "blue": 0.88},
                    },
                }
            },
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": col_count,
                    }
                }
            },
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": 0,
                        "endIndex": row_count,
                    }
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": 1,
                    },
                    "properties": {
                        "pixelSize": 140,
                    },
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 5,
                        "endIndex": 6,
                    },
                    "properties": {
                        "pixelSize": 150,
                    },
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 6,
                        "endIndex": 7,
                    },
                    "properties": {
                        "pixelSize": 170,
                    },
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 7,
                        "endIndex": 8,
                    },
                    "properties": {
                        "pixelSize": 180,
                    },
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 9,
                        "endIndex": 10,
                    },
                    "properties": {
                        "pixelSize": 220,
                    },
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 10,
                        "endIndex": 11,
                    },
                    "properties": {
                        "pixelSize": 170,
                    },
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 2,
                        "endIndex": 3,
                    },
                    "properties": {
                        "pixelSize": 320,
                    },
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 4,
                        "endIndex": 5,
                    },
                    "properties": {
                        "pixelSize": 110,
                    },
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 3,
                        "endIndex": 4,
                    },
                    "properties": {
                        "pixelSize": 800,
                    },
                    "fields": "pixelSize",
                }
            },
        ]
        worksheet.spreadsheet.batch_update({"requests": requests})
        _sync_review_table_with_status_chips(
            worksheet,
            used_row_count,
            subtopic_options=subtopic_options,
        )
        _enforce_header_row_format(worksheet, col_count)

    client = get_oauth_client(oauth_client_json=oauth_client_json, token_file=token_file)

    try:
        sh = _open_sheet_lenient(client, spreadsheet_title, log=log, spreadsheet_id=spreadsheet_id)
        _log(f"Spreadsheet obert: {sh.title}")
    except Exception as e:
        raise RuntimeError(
            f"No s'ha pogut obrir el Google Sheet '{spreadsheet_title}': {_format_google_error(e)}"
        ) from e

    try:
        ws = sh.worksheet(worksheet_name)
        _log(f"Pestanya oberta: {worksheet_name}")
    except Exception as e:
        raise RuntimeError(
            f"No s'ha trobat la pestanya '{worksheet_name}' al sheet '{spreadsheet_title}': "
            f"{_format_google_error(e)}"
        ) from e

    prepared_rows: List[List[str]] = []
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for r in rows:
        rr = list(r[:len(SHEETS_COLUMNS)])
        if len(rr) < len(SHEETS_COLUMNS):
            rr.extend([""] * (len(SHEETS_COLUMNS) - len(rr)))
        if len(rr) > 3:
            rr[3] = _html_to_sheet_text(rr[3])
        if len(rr) > 4:
            rr[4] = _ensure_status_default(rr[4])
        if len(rr) > 5 and not (rr[5] or "").strip():
            rr[5] = now_ts
        if len(rr) > 6:
            rr[6] = now_ts
        prepared_rows.append(rr)

    last_column = gspread.utils.rowcol_to_a1(1, len(SHEETS_COLUMNS)).rstrip("1")
    clear_until_row = max(int(getattr(ws, "row_count", 2) or 2), len(prepared_rows) + 1, 2)
    ws.batch_clear([f"A2:{last_column}{clear_until_row}"])

    if prepared_rows:
        end_row = len(prepared_rows) + 1
        ws.update(
            f"A2:{last_column}{end_row}",
            prepared_rows,
            value_input_option="RAW",
        )
        _log(f"Contingut bolcat a la plantilla: {len(prepared_rows)} files.")
    else:
        _log("No hi ha files noves per bolcar a la plantilla.")


def read_rows_from_sheets_oauth(
    spreadsheet_title: str,
    worksheet_name: str,
    spreadsheet_id: str | None = None,
    oauth_client_json: str = "oauth_client.json",
    token_file: str = "token.json",
    log=None,
    create_if_missing: bool = False,
) -> List[Dict[str, str]]:
    def _log(m: str):
        if log:
            log(m)

    _log("Google Sheets: autenticant…")
    try:
        client = get_oauth_client(oauth_client_json=oauth_client_json, token_file=token_file)
    except Exception as e:
        raise RuntimeError(f"No s'ha pogut autenticar amb Google: {_format_google_error(e)}") from e

    _log(f"Google Sheets: obrint sheet '{spreadsheet_title}'…")
    try:
        sh = _open_sheet_lenient(client, spreadsheet_title, log=log, spreadsheet_id=spreadsheet_id)
    except Exception as e:
        if create_if_missing:
            _log(f"Google Sheets: el sheet '{spreadsheet_title}' no existeix, es crearà…")
            try:
                sh = client.create(spreadsheet_title)
                _log(f"Google Sheets: sheet creat: {spreadsheet_title}")
            except Exception as create_e:
                raise RuntimeError(
                    f"No s'ha pogut crear el Google Sheet '{spreadsheet_title}': {_format_google_error(create_e)}"
                ) from create_e
        else:
            raise RuntimeError(
                f"No s'ha pogut obrir el Google Sheet '{spreadsheet_title}': {_format_google_error(e)}"
            ) from e

    _log(f"Google Sheets: obrint pestanya '{worksheet_name}'…")
    try:
        ws = sh.worksheet(worksheet_name)
    except Exception as e:
        if create_if_missing:
            _log(f"Google Sheets: la pestanya '{worksheet_name}' no existeix, es crearà…")
            try:
                ws = sh.add_worksheet(
                    title=worksheet_name,
                    rows=1000,
                    cols=max(11, len(SHEETS_COLUMNS)),
                )
                ws.append_row(SHEETS_COLUMNS, value_input_option="RAW")
                _log(f"Google Sheets: pestanya creada: {worksheet_name}")
            except Exception as create_e:
                raise RuntimeError(
                    f"No s'ha pogut crear la pestanya '{worksheet_name}' al sheet '{spreadsheet_title}': "
                    f"{_format_google_error(create_e)}"
                ) from create_e
        else:
            raise RuntimeError(
                f"No s'ha trobat la pestanya '{worksheet_name}' al sheet '{spreadsheet_title}': {_format_google_error(e)}"
            ) from e

    _log("Google Sheets: llegint files…")
    try:
        values = ws.get_all_values()
    except Exception as e:
        raise RuntimeError(
            f"No s'han pogut llegir files de '{spreadsheet_title}/{worksheet_name}': {_format_google_error(e)}"
        ) from e
    if not values or len(values) < 2:
        return []

    header = [h.strip() for h in values[0]]
    out: List[Dict[str, str]] = []
    for row in values[1:]:
        d: Dict[str, str] = {}
        for i, col in enumerate(header):
            d[col] = (row[i] if i < len(row) else "").strip()
        out.append(d)
    return out
