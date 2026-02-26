from scraper.scraping import scrape_faqs


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
