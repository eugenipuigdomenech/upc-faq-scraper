from scraper.html_export import approved_rows_to_html, filter_approved, render_upc_faqaccordion
from scraper.pipeline import _filter_approved_rows_for_render, _filter_approved_rows_by_context_topic


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
        {"Tema": "Preguntes frequents per estudiants", "Pregunta": "Q <b>x</b>?", "Resposta": "A <script>x</script>\nLinia 2"},
        {"Tema": "Preguntes frequents per estudiants", "Pregunta": "Q2", "Resposta": "A2"},
    ]

    html = render_upc_faqaccordion(items)

    assert "faqTopicAccordion" in html
    assert "window.__upcFaqStandaloneInit" in html


def test_approved_rows_to_html_maps_ui_rows():
    approved_rows = [
        ["Tema A", "Subtopic A", "Pregunta A", "Resposta A", "https://a.test"],
        ["Tema B", "Subtopic B", "Pregunta B", "Resposta B", "https://b.test"],
    ]

    html = approved_rows_to_html(approved_rows)

    assert "Pregunta A" in html
    assert "Resposta B" in html
    assert "Subtopic A" in html
    assert "Subtopic B" in html
    assert "Tema A" not in html
    assert "Tema B" not in html


def test_render_upc_faqaccordion_uses_subtopic_as_visible_group_title():
    items = [
        {"Tema": "Tema principal", "Subtopic": "Bloc 1", "Pregunta": "Pregunta A", "Resposta": "Resposta A"},
        {"Tema": "Tema principal", "Subtopic": "Bloc 1", "Pregunta": "Pregunta B", "Resposta": "Resposta B"},
    ]

    html = render_upc_faqaccordion(items)

    assert "Bloc 1" in html
    assert "Pregunta A" in html
    assert "Tema principal" not in html
    assert "background: #F2F8FB" not in html
    assert "border-left: 5px solid #00769D" not in html


def test_render_upc_faqaccordion_uses_bootstrap_accordion_button():
    html = render_upc_faqaccordion(
        [{"Tema": "Tema principal", "Pregunta": "Pregunta A", "Resposta": "Resposta A"}]
    )

    assert 'class="accordion-button collapsed"' in html
    assert 'data-chevron="1"' not in html
    assert '[data-upc-faq-toggle="1"]::after' in html
    assert "height: 0px; overflow: hidden; transition: height 350ms ease;" in html
    assert "window.__upcFaqStandaloneInit" in html


def test_filter_approved_rows_for_render_ignores_empty_subtopic_when_subtopics_exist():
    approved_rows = [
        {"Tema": "Altres", "Subtopic": "", "Pregunta": "Q antiga", "Resposta": "A antiga"},
        {"Tema": "Practiques empresa", "Subtopic": "Empresa", "Pregunta": "Q empresa", "Resposta": "A empresa"},
        {"Tema": "Practiques empresa", "Subtopic": "Estudiant", "Pregunta": "Q estudiant", "Resposta": "A estudiant"},
    ]

    filtered = _filter_approved_rows_for_render(approved_rows)

    assert len(filtered) == 2
    assert [row["Subtopic"] for row in filtered] == ["Empresa", "Estudiant"]


def test_render_upc_faqaccordion_uses_topic_when_subtopic_is_placeholder():
    items = [
        {"Tema": "Preguntes frequents", "Subtopic": "-", "Pregunta": "Pregunta A", "Resposta": "Resposta A"},
        {"Tema": "Mobilitat", "Subtopic": "–", "Pregunta": "Pregunta B", "Resposta": "Resposta B"},
    ]

    html = render_upc_faqaccordion(items)

    assert "Preguntes frequents" in html
    assert "Mobilitat" in html
    assert ">-<" not in html
    assert ">–<" not in html


def test_filter_approved_rows_for_render_keeps_rows_when_all_subtopics_are_placeholders():
    approved_rows = [
        {"Tema": "Preguntes frequents", "Subtopic": "-", "Pregunta": "Q1", "Resposta": "A1"},
        {"Tema": "Mobilitat", "Subtopic": "--", "Pregunta": "Q2", "Resposta": "A2"},
        {"Tema": "Beques", "Subtopic": "—", "Pregunta": "Q3", "Resposta": "A3"},
    ]

    filtered = _filter_approved_rows_for_render(approved_rows)

    assert filtered == approved_rows


def test_filter_approved_rows_by_context_topic_keeps_only_matching_topic_when_no_subtopics():
    approved_rows = [
        {"Tema": "Altres", "Subtopic": "-", "Pregunta": "Q1", "Resposta": "A1"},
        {"Tema": "Mobilitat", "Subtopic": "-", "Pregunta": "Q2", "Resposta": "A2"},
        {"Tema": "MIRAFI", "Subtopic": "-", "Pregunta": "Q3", "Resposta": "A3"},
    ]

    filtered = _filter_approved_rows_by_context_topic(
        approved_rows,
        context_labels=["FAQs Mobilitat", "FAQs"],
    )

    assert len(filtered) == 1
    assert filtered[0]["Tema"] == "Mobilitat"


def test_render_upc_faqaccordion_flattens_single_topic_without_subtopics():
    items = [
        {"Tema": "Mobilitat", "Subtopic": "-", "Pregunta": "Pregunta A", "Resposta": "Resposta A"},
        {"Tema": "Mobilitat", "Subtopic": "-", "Pregunta": "Pregunta B", "Resposta": "Resposta B"},
    ]

    html = render_upc_faqaccordion(items)

    assert 'id="faqTopicAccordion"' in html
    assert 'id="faqAccordion-1"' in html
    assert "<!-- TOPIC 1: Mobilitat -->" not in html
    assert "Pregunta A" in html
    assert "Pregunta B" in html
