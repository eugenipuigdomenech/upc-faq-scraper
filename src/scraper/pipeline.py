import csv
import json
import os
import re
import unicodedata
from collections import Counter
from typing import Any

try:
    from .constants import SHEETS_COLUMNS
    from .html_export import filter_approved, render_upc_faqaccordion
    from .scraping import build_outputs
    from .sheets import export_rows_to_google_sheets_oauth, read_rows_from_sheets_oauth
except ImportError:
    from constants import SHEETS_COLUMNS
    from html_export import filter_approved, render_upc_faqaccordion
    from scraping import build_outputs
    from sheets import export_rows_to_google_sheets_oauth, read_rows_from_sheets_oauth


def read_sources_csv(path: str) -> list[tuple[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
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

        def parse_with_header() -> list[tuple[str, str]]:
            reader = csv.DictReader(f, dialect=dialect)
            out_local: list[tuple[str, str]] = []
            for r in reader:
                url = (r.get("URL") or r.get("url") or r.get("Url") or r.get("link") or "").strip()
                topic = (r.get("topic") or r.get("Topic") or r.get("tema") or r.get("Tema") or "").strip()
                if url:
                    out_local.append((url, topic))
            return out_local

        def parse_without_header() -> list[tuple[str, str]]:
            reader = csv.reader(f, dialect=dialect)
            out_local: list[tuple[str, str]] = []
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


def read_rows_from_csv_like_sheets(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except Exception:
            dialect = csv.excel
            dialect.delimiter = ";"

        reader = csv.DictReader(f, dialect=dialect)
        rows: list[dict[str, str]] = []
        for r in reader:
            rows.append({(k or "").strip(): (v or "").strip() for k, v in r.items() if k})
        return rows


def export_like_sheets_csv(rows: list[list[str]], output_path: str):
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(SHEETS_COLUMNS)
        w.writerows(rows)


def export_genweb_json(blocks: list[dict[str, Any]], output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(blocks, f, ensure_ascii=False, indent=2)


def _normalize_for_compare(value: str) -> str:
    txt = (value or "").strip().lower()
    if not txt:
        return ""
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r"[^a-z0-9]+", "", txt)
    return txt


def _get_row_value_case_insensitive(row: dict[str, str], wanted_key: str) -> str:
    wanted = _normalize_for_compare(wanted_key)
    aliases = {wanted}
    if wanted == _normalize_for_compare("Subtopic"):
        aliases.update(
            {
                _normalize_for_compare("Sub topic"),
                _normalize_for_compare("Subtema"),
                _normalize_for_compare("Sub tema"),
                _normalize_for_compare("Subtòpic"),
                _normalize_for_compare("Sub tòpic"),
            }
        )
    for k, v in row.items():
        if _normalize_for_compare(k) in aliases:
            return (v or "").strip()
    return ""


def _normalize_subtopic_value(value: str) -> str:
    text = (value or "").strip()
    if text in {"-", "--", "–", "—"}:
        return ""
    return text


def _log_grouping_diagnostics(rows: list[dict[str, str]], approved_rows: list[dict[str, str]], log=None):
    def _log(m: str):
        if log:
            log(m)

    if not rows:
        _log("Diagnòstic HTML: no s'han llegit files.")
        return

    header_keys = [k for k in rows[0].keys() if (k or "").strip()]
    _log("Diagnòstic HTML: columnes detectades -> " + ", ".join(header_keys))

    if not approved_rows:
        _log("Diagnòstic HTML: no hi ha files aprovades.")
        return

    subtopics = [
        _normalize_subtopic_value(_get_row_value_case_insensitive(r, "Subtopic"))
        for r in approved_rows
    ]
    topics = [
        _get_row_value_case_insensitive(r, "Tema").strip()
        for r in approved_rows
    ]

    non_empty_subtopics = [s for s in subtopics if s]
    empty_subtopics = len(subtopics) - len(non_empty_subtopics)
    subtopic_counter = Counter(non_empty_subtopics)
    topic_counter = Counter([t for t in topics if t])

    if subtopic_counter:
        preview = ", ".join(f"{name} ({count})" for name, count in subtopic_counter.most_common(10))
        _log(f"Diagnòstic HTML: subtopics aprovats detectats -> {preview}")
    else:
        _log("Diagnòstic HTML: no s'ha detectat cap subtopic informat a les files aprovades.")

    if empty_subtopics:
        _log(f"Diagnòstic HTML: files aprovades amb Subtopic buit -> {empty_subtopics}")

    if topic_counter:
        preview = ", ".join(f"{name} ({count})" for name, count in topic_counter.most_common(10))
        _log(f"Diagnòstic HTML: temes aprovats detectats -> {preview}")


def _build_grouping_diagnostics(rows: list[dict[str, str]], approved_rows: list[dict[str, str]]) -> dict[str, object]:
    header_keys = [k for k in (rows[0].keys() if rows else []) if (k or "").strip()]
    subtopics = [
        _normalize_subtopic_value(_get_row_value_case_insensitive(r, "Subtopic"))
        for r in approved_rows
    ]
    topics = [
        _get_row_value_case_insensitive(r, "Tema").strip()
        for r in approved_rows
    ]
    non_empty_subtopics = [s for s in subtopics if s]
    empty_subtopics = len(subtopics) - len(non_empty_subtopics)
    subtopic_counter = Counter(non_empty_subtopics)
    topic_counter = Counter([t for t in topics if t])
    return {
        "headers": header_keys,
        "subtopics_preview": [name for name, _count in subtopic_counter.most_common(10)],
        "topics_preview": [name for name, _count in topic_counter.most_common(10)],
        "empty_subtopics": empty_subtopics,
    }


def _validate_approved_subtopics(approved_rows: list[dict[str, str]], row_numbers: dict[int, int]) -> list[str]:
    errors: list[str] = []
    for row in approved_rows:
        row_num = row_numbers.get(id(row), 0)
        label = f"Fila {row_num}" if row_num else "Fila desconeguda"
        topic = _get_row_value_case_insensitive(row, "Tema")
        subtopic = _normalize_subtopic_value(_get_row_value_case_insensitive(row, "Subtopic"))
        if topic and _normalize_for_compare(subtopic) == _normalize_for_compare(topic):
            errors.append(f"{label}: Subtopic no pot ser igual a Tema ('{topic}').")
    return errors


def _filter_approved_rows_for_render(approved_rows: list[dict[str, str]], log=None) -> list[dict[str, str]]:
    def _log(m: str):
        if log:
            log(m)

    has_any_subtopic = any(
        _normalize_subtopic_value(_get_row_value_case_insensitive(r, "Subtopic"))
        for r in approved_rows
    )
    if not has_any_subtopic:
        return approved_rows

    filtered = [
        r
        for r in approved_rows
        if _normalize_subtopic_value(_get_row_value_case_insensitive(r, "Subtopic"))
    ]
    ignored = len(approved_rows) - len(filtered)
    if ignored:
        _log(
            "Control subtopics: s'ignoren "
            f"{ignored} fila(es) aprovades amb Subtopic buit per evitar barrejar FAQs antigues."
        )
    return filtered


def _filter_approved_rows_by_context_topic(
    approved_rows: list[dict[str, str]],
    context_labels: list[str] | None = None,
    log=None,
) -> list[dict[str, str]]:
    def _log(m: str):
        if log:
            log(m)

    rows = approved_rows or []
    if not rows:
        return rows

    has_any_subtopic = any(
        _normalize_subtopic_value(_get_row_value_case_insensitive(r, "Subtopic"))
        for r in rows
    )
    if has_any_subtopic:
        return rows

    topics: list[str] = []
    for row in rows:
        topic = (_get_row_value_case_insensitive(row, "Tema") or "").strip()
        if topic and topic not in topics:
            topics.append(topic)

    if len(topics) <= 1:
        return rows

    normalized_contexts = []
    for label in context_labels or []:
        norm = _normalize_for_compare(label)
        if norm:
            normalized_contexts.append(norm)

    if not normalized_contexts:
        return rows

    matching_topics = []
    for topic in topics:
        norm_topic = _normalize_for_compare(topic)
        if len(norm_topic) < 4:
            continue
        if any(norm_topic in ctx for ctx in normalized_contexts):
            matching_topics.append(topic)

    if len(matching_topics) != 1:
        return rows

    chosen_topic = matching_topics[0]
    filtered = [
        row
        for row in rows
        if (_get_row_value_case_insensitive(row, "Tema") or "").strip() == chosen_topic
    ]
    if filtered and len(filtered) != len(rows):
        _log(
            "Control temes: s'exporten només les FAQs del tema "
            f"'{chosen_topic}' perquè coincideix amb el context seleccionat."
        )
        return filtered
    return rows


def run_pipeline(
    input_mode: str,
    output_mode: str,
    sources_csv_path: str | None = None,
    sources: list[tuple[str, str]] | None = None,
    output_file_path: str | None = None,
    output_sheet_title: str | None = None,
    output_sheet_tab: str | None = None,
    output_sheet_id: str | None = None,
    create_output_sheet_if_missing: bool = False,
    oauth_client_json: str = "oauth_client.json",
    token_file: str = "token.json",
    log=None,
    debug: bool = False,
    progress_cb=None,
):
    def _log(m: str):
        if log:
            log(m)

    if input_mode == "ui":
        if not sources:
            raise RuntimeError("No s'han afegit URLs a la UI.")
    elif input_mode == "csv":
        if not sources_csv_path:
            raise RuntimeError("Falta el fitxer CSV d'entrada.")
        sources = read_sources_csv(sources_csv_path)
    else:
        raise RuntimeError("input_mode ha de ser 'csv' o 'ui'.")

    _log(f"Sources loaded: {len(sources)}")
    if not sources:
        raise RuntimeError("No s'han trobat URLs. Afegeix almenys una URL.")

    rows, blocks, stats, errors = build_outputs(
        sources, log=log, debug=debug, progress_cb=progress_cb
    )

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
            raise RuntimeError("Falta el tÃ­tol o la pestanya del Google Sheet de sortida.")
        export_rows_to_google_sheets_oauth(
            rows=rows,
            spreadsheet_title=output_sheet_title,
            worksheet_name=output_sheet_tab,
            spreadsheet_id=output_sheet_id,
            oauth_client_json=oauth_client_json,
            token_file=token_file,
            log=log,
            create_if_missing=create_output_sheet_if_missing,
        )
        subtopic_errors = 0
        for row in rows:
            subtopic = (row[1] if len(row) > 1 else "").strip()
            if subtopic == "--":
                subtopic_errors += 1
        if subtopic_errors:
            _log(f"Control subtopics: {subtopic_errors} FAQ(s) sense subtopic vÃ lid.")
        _log(f"Exported to Google Sheets: {output_sheet_title} / {output_sheet_tab}")
        stats["subtopic_errors"] = subtopic_errors
    else:
        raise RuntimeError("output_mode ha de ser 'csv', 'sheets_oauth' o 'genweb_json'.")

    stats["blocks"] = blocks
    stats["errors"] = errors
    return stats


def run_approved_to_html_pipeline(
    input_mode: str,
    input_csv_path: str | None = None,
    sheet_title: str | None = None,
    sheet_tab: str | None = None,
    sheet_id: str | None = None,
    oauth_client_json: str = "oauth_client.json",
    token_file: str = "token.json",
    output_path: str = "faqs_aprovades.txt",
    log=None,
) -> dict[str, Any]:
    def _log(m: str):
        if log:
            log(m)

    if input_mode == "csv":
        if not input_csv_path:
            raise RuntimeError("Falta el CSV d'entrada.")
        rows = read_rows_from_csv_like_sheets(input_csv_path)
        context_labels = [os.path.basename(input_csv_path or ""), input_csv_path or ""]
    elif input_mode == "sheets_oauth":
        if not (sheet_title and sheet_tab):
            raise RuntimeError("Falta tÃ­tol o pestanya del Google Sheet.")
        rows = read_rows_from_sheets_oauth(
            spreadsheet_title=sheet_title,
            worksheet_name=sheet_tab,
            spreadsheet_id=sheet_id,
            oauth_client_json=oauth_client_json,
            token_file=token_file,
            log=log,
            create_if_missing=False,
        )
        context_labels = [sheet_title or "", sheet_tab or ""]
    else:
        raise RuntimeError("input_mode ha de ser 'csv' o 'sheets_oauth'.")

    _log(f"Files llegides: {len(rows)}")
    row_numbers = {id(row): idx for idx, row in enumerate(rows, start=2)}
    approved = filter_approved(rows)
    _log(f"Files aprovades: {len(approved)}")
    _log_grouping_diagnostics(rows, approved, log=log)

    subtopic_errors = _validate_approved_subtopics(approved, row_numbers)
    if subtopic_errors:
        preview = "\n".join(f"- {e}" for e in subtopic_errors[:15])
        more = ""
        if len(subtopic_errors) > 15:
            more = f"\n- ... i {len(subtopic_errors) - 15} incidencia(es) mes."
        raise RuntimeError(
            "Control subtopics: s'han detectat incidencies en files aprovades.\n"
            "Corregeix el CSV/Google Sheet abans de generar el codi font.\n"
            f"{preview}{more}"
        )

    approved = _filter_approved_rows_for_render(approved, log=log)
    approved = _filter_approved_rows_by_context_topic(approved, context_labels=context_labels, log=log)

    approved.sort(
        key=lambda r: (
            (
                _normalize_subtopic_value(_get_row_value_case_insensitive(r, "Subtopic"))
                or _get_row_value_case_insensitive(r, "Tema")
            ).lower(),
            _get_row_value_case_insensitive(r, "Pregunta").lower(),
        )
    )
    html_text = render_upc_faqaccordion(approved)

    topics = len(
        {
            (_normalize_subtopic_value(_get_row_value_case_insensitive(r, "Subtopic")) or _get_row_value_case_insensitive(r, "Tema")).strip()
            for r in approved
            if (_normalize_subtopic_value(_get_row_value_case_insensitive(r, "Subtopic")) or _get_row_value_case_insensitive(r, "Tema")).strip()
        }
    )
    _log(f"Fitxer generat: {output_path}")

    return {
        "total_rows": len(rows),
        "approved_rows": len(approved),
        "topics": topics,
        "html_text": html_text,
        "diagnostics": _build_grouping_diagnostics(rows, approved),
    }
