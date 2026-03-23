from scraper.scraping import build_outputs, scrape_faqs


class FakeResponse:
    def __init__(self, text, status_code=200, url="https://example.test"):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_scrape_faqs_upc_antic_format(monkeypatch):
    html = """
    <div id="collapse-base">
      <a data-toggle="collapse" href="#collapse-1">Pregunta 1?</a>
    </div>
    <div id="collapse-1"><div class="panel-body">Resposta 1</div></div>
    """

    def fake_get(*args, **kwargs):
        return FakeResponse(html)

    monkeypatch.setattr("scraper.scraping.requests.get", fake_get)
    faqs = scrape_faqs("https://example.test/faq")

    assert faqs == [("Pregunta 1?", "Resposta 1")]


def test_scrape_faqs_bootstrap_format(monkeypatch):
    html = """
    <div class="accordion-item">
      <button class="accordion-button">Q bootstrap</button>
      <div class="accordion-body">A bootstrap</div>
    </div>
    """

    def fake_get(*args, **kwargs):
        return FakeResponse(html)

    monkeypatch.setattr("scraper.scraping.requests.get", fake_get)
    faqs = scrape_faqs("https://example.test/bootstrap")

    assert faqs == [("Q bootstrap", "A bootstrap")]


def test_scrape_faqs_returns_empty_when_unknown_format(monkeypatch):
    html = "<html><body><h1>Sense FAQs</h1></body></html>"

    def fake_get(*args, **kwargs):
        return FakeResponse(html)

    monkeypatch.setattr("scraper.scraping.requests.get", fake_get)
    faqs = scrape_faqs("https://example.test/none")

    assert faqs == []


def test_build_outputs_uses_accordion_subtitle_as_subtopic(monkeypatch):
    html = """
    <div class="accordion-item">
      <h2 class="accordion-header"><button class="accordion-button">Preguntes frequents per estudiants</button></h2>
      <div class="accordion-body">
        <p><b>1)</b><b>Q alumnes?</b></p>
        <p>A alumnes</p>
      </div>
    </div>
    <div class="accordion-item">
      <h2 class="accordion-header"><button class="accordion-button">Preguntes frequents per als directors de TFE</button></h2>
      <div class="accordion-body">
        <p><b>1)</b><b>Q directors?</b></p>
        <p>A directors</p>
      </div>
    </div>
    """

    def fake_get(*args, **kwargs):
        return FakeResponse(html)

    monkeypatch.setattr("scraper.scraping.requests.get", fake_get)

    rows, blocks, stats, errors = build_outputs([("https://example.test/tfe", "TFE")])

    assert errors == []
    assert stats["total_faqs"] == 2
    assert rows[0][0] == "TFE"
    assert rows[1][0] == "TFE"
    assert rows[0][1] == "Preguntes frequents per estudiants"
    assert rows[1][1] == "Preguntes frequents per als directors de TFE"
    assert rows[0][2] == "Q alumnes?"
    assert rows[1][2] == "Q directors?"
    assert blocks[0]["items"][0]["topic"] == "TFE"
    assert blocks[0]["items"][0]["subtopic"] == "Preguntes frequents per estudiants"


def test_build_outputs_uses_gw4_headings_as_subtopic(monkeypatch):
    html = """
    <section id="section-text">
      <h2>Preguntes i respostes frequents per a l'empresa</h2>
      <div class="accordion accordion-gw4 mb-3">
        <div>
          <a id="open-accordion1">Q empresa?</a>
          <div class="accordion-content"><p>R empresa</p></div>
        </div>
      </div>
      <h2>Preguntes i respostes frequents per l'estudiant</h2>
      <div class="accordion accordion-gw4 mb-3">
        <div>
          <a id="open-accordion2">Q estudiant?</a>
          <div class="accordion-content"><p>R estudiant</p></div>
        </div>
      </div>
    </section>
    """

    def fake_get(*args, **kwargs):
        return FakeResponse(html)

    monkeypatch.setattr("scraper.scraping.requests.get", fake_get)

    rows, blocks, stats, errors = build_outputs([("https://example.test/gw4", "General")])

    assert errors == []
    assert stats["total_faqs"] == 2
    assert rows[0][0] == "General"
    assert rows[1][0] == "General"
    assert rows[0][2] == "Q empresa?"
    assert rows[1][2] == "Q estudiant?"
    assert blocks[0]["items"][0]["topic"] == "General"


def test_build_outputs_uses_bootstrap_item_title_as_subtopic(monkeypatch):
    html = """
    <div class="accordion" id="uid-abc">
      <div class="accordion-item">
        <h2 class="accordion-header">
          <button class="accordion-button">About the procedure</button>
        </h2>
        <div class="accordion-body">
          <ul>
            <li><strong>How do I apply?</strong><p>Apply online.</p></li>
          </ul>
        </div>
      </div>
      <div class="accordion-item">
        <h2 class="accordion-header">
          <button class="accordion-button">About the subjects</button>
        </h2>
        <div class="accordion-body">
          <ul>
            <li><strong>What subjects can I do?</strong><p>You can choose from guides.</p></li>
          </ul>
        </div>
      </div>
    </div>
    """

    def fake_get(*args, **kwargs):
        return FakeResponse(html)

    monkeypatch.setattr("scraper.scraping.requests.get", fake_get)

    rows, blocks, stats, errors = build_outputs([("https://example.test/incoming", "Incoming")])

    assert errors == []
    assert stats["total_faqs"] == 2
    assert rows[0][0] == "Incoming"
    assert rows[1][0] == "Incoming"
    assert rows[0][1] == "About the procedure"
    assert rows[1][1] == "About the subjects"
    assert rows[0][2] == "How do I apply?"
    assert rows[1][2] == "What subjects can I do?"
    assert blocks[0]["items"][0]["topic"] == "Incoming"
    assert blocks[0]["items"][0]["subtopic"] == "About the procedure"


def test_build_outputs_keeps_subtopic_out_of_question_column_for_strong_paragraph_blocks(monkeypatch):
    html = """
    <div class="accordion-item">
      <h2 class="accordion-header">
        <button class="accordion-button">Before applying</button>
      </h2>
      <div class="accordion-body">
        <p><strong>Who can apply?</strong></p>
        <p>Students with 120 credits passed.</p>
        <p><strong>When do I apply?</strong></p>
        <p>During the enrollment period.</p>
      </div>
    </div>
    """

    def fake_get(*args, **kwargs):
        return FakeResponse(html)

    monkeypatch.setattr("scraper.scraping.requests.get", fake_get)

    rows, _blocks, stats, errors = build_outputs([("https://example.test/apply", "Admissions")])

    assert errors == []
    assert stats["total_faqs"] == 2
    assert rows[0][0] == "Admissions"
    assert rows[0][1] == "Before applying"
    assert rows[0][2] == "Who can apply?"
    assert rows[1][1] == "Before applying"
    assert rows[1][2] == "When do I apply?"


def test_build_outputs_uses_outer_topic_as_subtopic_for_nested_faq_topic_accordion(monkeypatch):
    html = """
    <div id="faqTopicAccordion" class="accordion">
      <div class="accordion-item">
        <h2>
          <button class="accordion-button collapsed" data-bs-target="#topic-1" data-bs-toggle="collapse" type="button">
            Preguntes frequents per als directors de TFE
          </button>
        </h2>
        <div id="topic-1" class="collapse">
          <div>
            <div id="faqAccordion-1" class="accordion">
              <div class="accordion-item">
                <h2>
                  <button class="accordion-button collapsed" data-bs-target="#c1-1" data-bs-toggle="collapse" type="button">
                    Com he d'introduir una proposta de TFE?
                  </button>
                </h2>
                <div id="c1-1" class="collapse">
                  <div>
                    <div>Resposta 1</div>
                  </div>
                </div>
              </div>
              <div class="accordion-item">
                <h2>
                  <button class="accordion-button collapsed" data-bs-target="#c1-2" data-bs-toggle="collapse" type="button">
                    Dirigir un treball implica formar part del tribunal?
                  </button>
                </h2>
                <div id="c1-2" class="collapse">
                  <div>
                    <div>Resposta 2</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    """

    def fake_get(*args, **kwargs):
        return FakeResponse(html)

    monkeypatch.setattr("scraper.scraping.requests.get", fake_get)

    rows, blocks, stats, errors = build_outputs([("https://example.test/nested", "TFE")])

    assert errors == []
    assert stats["total_faqs"] == 2
    assert rows[0][0] == "TFE"
    assert rows[0][1] == "Preguntes frequents per als directors de TFE"
    assert rows[0][2] == "Com he d'introduir una proposta de TFE?"
    assert rows[1][1] == "Preguntes frequents per als directors de TFE"
    assert rows[1][2] == "Dirigir un treball implica formar part del tribunal?"
    assert blocks[0]["items"][0]["subtopic"] == "Preguntes frequents per als directors de TFE"
