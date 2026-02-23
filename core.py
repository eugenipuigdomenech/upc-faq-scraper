import csv,json,os,html,requests,gspread
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from bs4 import BeautifulSoup
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


# ---------- INPUT (pas 1: llista d’URLs) ----------
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

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except Exception:
            dialect = csv.excel
            dialect.delimiter = ","

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
    Suporta:
    1) UPC antic (collapse-base / data-toggle="collapse")
    2) Bootstrap 5 accordion clàssic (accordion-item / accordion-body)
    3) Nou format UPC/Plone amb #faqAccordion (button[data-bs-target="#cX"] + div.collapse#cX)
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

    # Format 1: UPC antic
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

    # Format 3: #faqAccordion (més específic)
    root = soup.select_one("#faqAccordion")
    if root:
        btns = root.select('button[data-bs-toggle="collapse"][data-bs-target^="#"]')
        if debug:
            _log(f"DEBUG #faqAccordion buttons: {len(btns)}")

        for btn in btns:
            btn_copy = BeautifulSoup(str(btn), "html.parser").select_one("button")
            if btn_copy:
                for s in btn_copy.select("span"):
                    s.decompose()
                question = btn_copy.get_text(" ", strip=True)
            else:
                question = btn.get_text(" ", strip=True)

            target = (btn.get("data-bs-target") or "").strip()
            if not target.startswith("#"):
                continue

            panel = root.select_one(target) or soup.select_one(target)
            if not panel:
                continue

            ps = panel.select("p")
            if ps:
                answer = " ".join(p.get_text(" ", strip=True) for p in ps if p.get_text(strip=True))
            else:
                answer = panel.get_text(" ", strip=True)

            if question and answer:
                faqs.append((question, answer))

        if faqs:
            return faqs

    # Format 2: Bootstrap 5 accordion
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

    # Mètode extra: buttons data-bs-target
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
            genweb_blocks.append({"topic": topic, "source_url": url, "items": []})

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
    log=None,
):
    import re

    def _log(m: str):
        if log:
            log(m)

    def _norm(s: str) -> str:
        s = (s or "").replace("\u00a0", " ")
        return re.sub(r"\s+", " ", s).strip()

    def _qkey(row: List[str]) -> tuple[str, str, str]:
        topic = _norm(row[0]) if len(row) > 0 else ""
        pregunta = _norm(row[1]) if len(row) > 1 else ""
        font = _norm(row[8]) if len(row) > 8 else ""
        return (topic, pregunta, font)

    def _ans(row: List[str]) -> str:
        return _norm(row[2]) if len(row) > 2 else ""

    client = get_oauth_client(oauth_client_json=oauth_client_json, token_file=token_file)

    try:
        sh = client.open(spreadsheet_title)
        _log(f"Spreadsheet obert: {spreadsheet_title}")
    except Exception:
        sh = client.create(spreadsheet_title)
        _log(f"Spreadsheet creat: {spreadsheet_title}")

    try:
        ws = sh.worksheet(worksheet_name)
        _log(f"Pestanya oberta: {worksheet_name}")
    except Exception:
        ws = sh.add_worksheet(
            title=worksheet_name,
            rows=max(1000, len(rows) + 10),
            cols=len(SHEETS_COLUMNS),
        )
        _log(f"Pestanya creada: {worksheet_name}")

    values = ws.get_all_values()
    is_truly_empty = (
        not values
        or all((not r) or all((c or "").strip() == "" for c in r) for r in values)
    )
    if is_truly_empty:
        ws.clear()
        ws.append_row(SHEETS_COLUMNS, value_input_option="RAW")
        _log("Capçalera afegida")
        values = [SHEETS_COLUMNS]

    first_created: dict[tuple[str, str, str], str] = {}
    existing_answers: dict[tuple[str, str, str], set[str]] = {}

    for r in values[1:]:
        k = _qkey(r)
        created = (r[4] if len(r) > 4 else "").strip()
        if created and k not in first_created:
            first_created[k] = created

        a = _ans(r)
        if a:
            existing_answers.setdefault(k, set()).add(a)

    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    to_append: List[List[str]] = []
    skipped = 0

    for r in rows:
        rr = r.copy()
        k = _qkey(rr)
        a = _ans(rr)

        rr[4] = first_created.get(k, rr[4] or now_ts)
        rr[5] = now_ts

        seen = existing_answers.setdefault(k, set())
        if a in seen:
            skipped += 1
            continue

        seen.add(a)
        first_created.setdefault(k, rr[4])
        to_append.append(rr)

    _log(f"Saltades (mateixa resposta): {skipped} | Noves (resposta diferent): {len(to_append)}")

    if to_append:
        ws.append_rows(to_append, value_input_option="RAW")
        _log(f"Rows appended: {len(to_append)}")
    else:
        _log("No s’ha afegit res (tot eren duplicats de resposta).")

    ws.update_acell("K1", f"LAST_WRITE: {now_ts}")


# ---------- OUTPUT: Genweb JSON (si el vols mantenir) ----------
def export_genweb_json(blocks: List[Dict[str, Any]], output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(blocks, f, ensure_ascii=False, indent=2)


# ---------- PIPELINE (pas 1) ----------
def run_pipeline(
    input_mode: str,                    # "csv" | "ui"
    output_mode: str,                   # "csv" | "sheets_oauth" | "genweb_json"
    sources_csv_path: Optional[str] = None,
    sources: Optional[List[Tuple[str, str]]] = None,
    output_file_path: Optional[str] = None,
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
    if input_mode == "ui":
        if not sources:
            raise RuntimeError("No s’han afegit URLs a la UI.")
    elif input_mode == "csv":
        if not sources_csv_path:
            raise RuntimeError("Falta el fitxer CSV d’entrada.")
        sources = read_sources_csv(sources_csv_path)
    else:
        raise RuntimeError("input_mode ha de ser 'csv' o 'ui'.")

    _log(f"Sources loaded: {len(sources)}")
    if not sources:
        raise RuntimeError("No s’han trobat URLs. Afegeix almenys una URL.")

    rows, blocks, stats, errors = build_outputs(sources, log=log, debug=debug)

    if output_mode == "csv":
        if not output_file_path:
            raise RuntimeError("Falta el fitxer CSV de sortida.")
        export_like_sheets_csv(rows, output_file_path)
        _log(f"CSV written: {output_file_path}")

    elif output_mode == "genweb_json":
        if not output_file_path:
            raise RuntimeError("Falta el fitxer JSON de sortida.")
        export_genweb_json(blocks, output_file_path)
        _log(f"Genweb JSON written: {output_file_path}")

    elif output_mode == "sheets_oauth":
        if not (output_sheet_title and output_sheet_tab):
            raise RuntimeError("Falta el títol o la pestanya del Google Sheet de sortida.")
        export_rows_to_google_sheets_oauth(
            rows=rows,
            spreadsheet_title=output_sheet_title,
            worksheet_name=output_sheet_tab,
            oauth_client_json=oauth_client_json,
            token_file=token_file,
            log=log,
        )
        _log(f"Exported to Google Sheets: {output_sheet_title} / {output_sheet_tab}")

    else:
        raise RuntimeError("output_mode ha de ser 'csv', 'sheets_oauth' o 'genweb_json'.")

    return stats


# =====================================================================================
# ========================  PAS 2: APROVATS -> HTML UPC  ==============================
# =====================================================================================

def read_rows_from_csv_like_sheets(path: str) -> List[Dict[str, str]]:
    """Llegeix CSV amb capçalera tipus SHEETS_COLUMNS i retorna dicts."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except Exception:
            dialect = csv.excel
            dialect.delimiter = ";"

        reader = csv.DictReader(f, dialect=dialect)
        rows: List[Dict[str, str]] = []
        for r in reader:
            rows.append({(k or "").strip(): (v or "").strip() for k, v in r.items() if k})
        return rows


def read_rows_from_sheets_oauth(
    spreadsheet_title: str,
    worksheet_name: str,
    oauth_client_json: str = "oauth_client.json",
    token_file: str = "token.json",
) -> List[Dict[str, str]]:
    """Llegeix totes les files d'una pestanya (capçalera a la primera fila)."""
    client = get_oauth_client(oauth_client_json=oauth_client_json, token_file=token_file)
    sh = client.open(spreadsheet_title)
    ws = sh.worksheet(worksheet_name)

    values = ws.get_all_values()
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


def filter_approved(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    approved_values = {"aprobat", "aprovada", "approved"}
    out = []
    for r in rows:
        estat = (r.get("Estat") or r.get("estat") or "").strip().lower()
        if estat in approved_values:
            out.append(r)
    return out


def _answer_to_html_paragraph(answer: str) -> str:
    a = (answer or "").strip()
    a = html.escape(a)
    a = a.replace("\r\n", "\n").replace("\r", "\n")
    a = a.replace("\n\n", "<br /><br />")
    a = a.replace("\n", "<br />")
    return a


def render_upc_faqaccordion(items: List[Dict[str, str]]) -> str:
    out: List[str] = []
    out.append('<div id="faqAccordion" style="margin-bottom: 40px;">')

    for idx, it in enumerate(items, start=1):
        q = (it.get("Pregunta") or "").strip()
        a = (it.get("Resposta") or "").strip()

        q_html = html.escape(q)
        a_html = _answer_to_html_paragraph(a)

        out.append(f'<!-- ITEM {idx} -->')
        out.append('<div style="border: 0; box-shadow: none; border-bottom: 1px solid #D1D1D1; background: transparent;">')
        out.append(
            '<h2 style="padding: 0; margin: 0;">'
            f'<button type="button" data-bs-toggle="collapse" data-bs-target="#c{idx}" aria-expanded="false" aria-controls="c{idx}" '
            'style="width: 100%; text-align: left; font-size: 18px; background: transparent; padding: 30px 36px 30px 18px; '
            'font-weight: 500; color: #00769d; position: relative; border: 0; border-top: 1px solid #D1D1D1; '
            'box-shadow: none; cursor: pointer;">'
            f'{q_html} '
            '<span aria-hidden="true" style="position: absolute; right: 18px; top: 50%; transform: translateY(-50%); transition: all .25s ease; '
            "font-family: 'upc-icones', Arial, sans-serif;\"></span> "
            '</button></h2>'
        )
        out.append(
            f'<div id="c{idx}" class="collapse" data-bs-parent="#faqAccordion" '
            'style="border-bottom: 1px solid #D1D1D1; margin-bottom: -1px; position: relative; z-index: 1; height: 0px; overflow: hidden; '
            'transition: height 350ms ease;">'
        )
        out.append('<div style="border-top: 0; padding: 0 18px 18px;">')
        out.append(
            '<p style="margin: 0; font-size: 16px; font-weight: 300; line-height: 1.45; color: #636363;">'
            f'{a_html}</p>'
        )
        out.append('</div></div></div>')

    out.append('</div>')
    out.append('<p>')
    out.append('<script>')
    out.append(r"""(function () {
  const acc = document.getElementById('faqAccordion');
  if (!acc) return;

  const collapses = Array.from(acc.querySelectorAll('.collapse'));

  function btnFor(col) {
    return acc.querySelector('[data-bs-target="#' + col.id + '"]');
  }

  function setStyles(col, isOpen) {
    const btn = btnFor(col);
    if (btn) {
      btn.style.borderTopColor = isOpen ? '#00769D' : '#D1D1D1';
      btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      const icon = btn.querySelector('span[aria-hidden="true"]');
      if (icon) {
        icon.style.transform = isOpen
          ? 'rotate(180deg) translateY(50%)'
          : 'translateY(-50%)';
      }
    }
    col.style.borderBottomColor = isOpen ? '#00769D' : '#D1D1D1';
  }

  function open(col) {
    if (col.dataset.anim === '1') return;

    collapses.forEach(other => { if (other !== col) close(other); });

    col.dataset.anim = '1';
    col.classList.add('showing');
    col.style.height = '0px';

    requestAnimationFrame(() => {
      const h = col.scrollHeight;
      col.style.height = h + 'px';
      setStyles(col, true);
    });

    const done = (e) => {
      if (e.propertyName !== 'height') return;
      col.classList.remove('showing');
      col.classList.add('show');
      col.style.height = 'auto';
      col.dataset.anim = '0';
      col.removeEventListener('transitionend', done);
    };
    col.addEventListener('transitionend', done);
  }

  function close(col) {
    if (col.dataset.anim === '1') return;
    if (!col.classList.contains('show') && col.style.height === '0px') return;

    col.dataset.anim = '1';
    col.classList.remove('show');

    const h = col.scrollHeight;
    col.style.height = h + 'px';

    requestAnimationFrame(() => {
      col.style.height = '0px';
      setStyles(col, false);
    });

    const done = (e) => {
      if (e.propertyName !== 'height') return;
      col.dataset.anim = '0';
      col.removeEventListener('transitionend', done);
    };
    col.addEventListener('transitionend', done);
  }

  acc.querySelectorAll('button[data-bs-target]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const sel = btn.getAttribute('data-bs-target');
      const col = sel ? document.querySelector(sel) : null;
      if (!col) return;

      const isOpen = col.classList.contains('show') || col.style.height === 'auto';
      if (isOpen) close(col);
      else open(col);
    });
  });

  collapses.forEach(col => {
    col.style.overflow = 'hidden';
    col.style.transition = 'height 350ms ease';
    col.style.height = '0px';
    col.classList.remove('show');
    setStyles(col, false);
  });
})();""")
    out.append('</script>')
    out.append('</p>')

    return "\n".join(out)


def export_text(output_path: str, text: str):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)


def run_approved_to_html_pipeline(
    input_mode: str,  # "csv" | "sheets_oauth"
    input_csv_path: Optional[str] = None,
    sheet_title: Optional[str] = None,
    sheet_tab: Optional[str] = None,
    oauth_client_json: str = "oauth_client.json",
    token_file: str = "token.json",
    output_path: str = "faqs_aprovades.txt",
    log=None,
) -> Dict[str, int]:
    def _log(m: str):
        if log:
            log(m)

    if input_mode == "csv":
        if not input_csv_path:
            raise RuntimeError("Falta el CSV d’entrada.")
        rows = read_rows_from_csv_like_sheets(input_csv_path)

    elif input_mode == "sheets_oauth":
        if not (sheet_title and sheet_tab):
            raise RuntimeError("Falta títol o pestanya del Google Sheet.")
        rows = read_rows_from_sheets_oauth(
            spreadsheet_title=sheet_title,
            worksheet_name=sheet_tab,
            oauth_client_json=oauth_client_json,
            token_file=token_file,
        )

    else:
        raise RuntimeError("input_mode ha de ser 'csv' o 'sheets_oauth'.")

    _log(f"Files llegides: {len(rows)}")

    approved = filter_approved(rows)
    _log(f"Files aprovades: {len(approved)}")

    approved.sort(key=lambda r: ((r.get("Tema") or "").lower(), (r.get("Pregunta") or "").lower()))

    html_text = render_upc_faqaccordion(approved)
    export_text(output_path, html_text)

    topics = len({(r.get('Tema') or '').strip() for r in approved if (r.get('Tema') or '').strip()})
    _log(f"Fitxer generat: {output_path}")

    return {"total_rows": len(rows), "approved_rows": len(approved), "topics": topics}