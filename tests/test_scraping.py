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


def test_build_outputs_uses_accordion_subtitle_as_topic(monkeypatch):
    html = """
    <div class="accordion-item">
      <h2 class="accordion-header"><button class="accordion-button">Preguntes freqüents per estudiants</button></h2>
      <div class="accordion-body">
        <p><b>1)</b><b>Q alumnes?</b></p>
        <p>A alumnes</p>
      </div>
    </div>
    <div class="accordion-item">
      <h2 class="accordion-header"><button class="accordion-button">Preguntes freqüents per als directors de TFE</button></h2>
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
    assert rows[0][0] == "Preguntes freqüents per estudiants"
    assert rows[1][0] == "Preguntes freqüents per als directors de TFE"
    assert blocks[0]["items"][0]["topic"] == "Preguntes freqüents per estudiants"


def test_build_outputs_uses_gw4_headings_as_topic(monkeypatch):
    html = """
    <section id="section-text">
      <h2>Preguntes i respostes freqüents per a l'empresa</h2>
      <div class="accordion accordion-gw4 mb-3">
        <div>
          <a id="open-accordion1">Q empresa?</a>
          <div class="accordion-content"><p>R empresa</p></div>
        </div>
      </div>
      <h2>Preguntes i respostes freqüents per l'estudiant</h2>
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
    assert rows[0][0] == "Preguntes i respostes freqüents per a l'empresa"
    assert rows[1][0] == "Preguntes i respostes freqüents per l'estudiant"
    assert blocks[0]["items"][0]["topic"] == "Preguntes i respostes freqüents per a l'empresa"


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
    assert rows[0][0] == "About the procedure"
    assert rows[1][0] == "About the subjects"
    assert blocks[0]["items"][0]["topic"] == "About the procedure"
