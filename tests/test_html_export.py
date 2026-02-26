from scraper.html_export import approved_rows_to_html, filter_approved, render_upc_faqaccordion


def test_filter_approved_accepts_known_values():
    rows = [
        {"Estat": "aprobat", "Pregunta": "Q1"},
        {"Estat": "aprovada", "Pregunta": "Q2"},
        {"estat": "approved", "Pregunta": "Q3"},
        {"Estat": "pendent", "Pregunta": "Q4"},
    ]

    approved = filter_approved(rows)
    questions = [r.get("Pregunta") for r in approved]
    assert questions == ["Q1", "Q2", "Q3"]


def test_render_upc_faqaccordion_escapes_html_and_builds_ids():
    items = [
        {"Pregunta": "Q <b>x</b>?", "Resposta": "A <script>x</script>\nLinia 2"},
        {"Pregunta": "Q2", "Resposta": "A2"},
    ]

    html = render_upc_faqaccordion(items)

    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "id=\"c1\"" in html
    assert "id=\"c2\"" in html
    assert "<br />" in html


def test_approved_rows_to_html_maps_ui_rows():
    approved_rows = [
        ["Tema A", "Pregunta A", "Resposta A", "https://a.test"],
        ["Tema B", "Pregunta B", "Resposta B", "https://b.test"],
    ]

    html = approved_rows_to_html(approved_rows)

    assert "Pregunta A" in html
    assert "Resposta B" in html
    assert "faqAccordion" in html
