# UPC FAQ Scraper

Eina d'escriptori en Python per:
- capturar FAQs des de multiples URLs,
- revisar i aprovar FAQs des de la UI,
- exportar a CSV o Google Sheets,
- generar HTML final per enganxar a Genweb.

## Estat actual

Aquest projecte usa:
- UI amb `customtkinter`,
- scraping amb `requests` + `beautifulsoup4`,
- integracio Google Sheets via OAuth amb `gspread`.

## Estructura del projecte

```text
Scraper/
  assets/                    # Logo i icona de l'app
  src/
    scraper/
      app.py                 # UI principal
      core.py                # Logica de scraping/exportacio/render HTML
  tests/                     # Fitxers de prova / recursos
  requirements.txt
  .gitignore
  README.md
```

## Requisits

- Python 3.11+ (recomanat)
- Windows 10/11 (testejat principalment en Windows)

## Instal·lacio

```powershell
py -m venv .venv
.\.venv\Scripts\activate
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

## Executar l'aplicacio

Des de l'arrel del projecte:

```powershell
py src\scraper\app.py
```

## Flux funcional

1. Afegeixes topics.
2. Afegeixes URLs dins de cada topic.
3. Fas scraping.
4. Revisions i aprovacions a la pestanya UI.
5. Exportes:
   - CSV,
   - Google Sheets,
   - HTML final per Genweb.

## Google Sheets (OAuth)

Si vols exportar a Google Sheets:

1. Crea un OAuth Client ID de tipus Desktop a Google Cloud.
2. Descarrega el JSON i selecciona'l des de la UI (`oauth_client.json`).
3. A la primera execucio es demanara login al navegador i es generara `token.json`.

No pugis mai aquests fitxers al repositori.

## Build EXE (opcional)

```powershell
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --clean --onefile --windowed --name "UPC_FAQ_Scraper" --icon=assets\upc_logo.ico --add-data "assets;assets" src\scraper\app.py
```

Sortida esperada:
- `dist\UPC_FAQ_Scraper.exe`

## Bones practiques aplicades

- Codi dins de `src/`
- Secrets ignorats a `.gitignore`
- Entorn virtual local
- `README` amb setup i flux clar

