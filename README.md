# 📚 UPC FAQ Scraper

Aplicació d’escriptori desenvolupada amb Python + CustomTkinter per:

🔎 Fer scraping de FAQs (Preguntes Més Freqüents) des de múltiples URLs

📄 Exportar resultats a CSV

☁️ Exportar directament a Google Sheets (via OAuth)

🧩 Exportar en format JSON compatible amb Genweb

Pensada per facilitar la recopilació i estructuració de FAQs de manera automatitzada.

## 🚀 Funcionalitats

✅ Lectura de múltiples URLs des d’un CSV
✅ Detecció automàtica de diferents formats d’acordions (UPC antic + Bootstrap 5)
✅ Exportació estructurada amb:
- Tema
- Pregunta
- Resposta
- Esta
- Dates
- Font

✅ Login segur amb Google (OAuth)

✅ Generació d’executable .exe per Windows

## 🖥️ Requisits

Windows 10 / 11

Python 3.11 o superior (recomanat)

Connexió a Internet

## 📦 Instal·lació del projecte

1️⃣ Clonar repositori
git clone <REPO_URL>
cd upc-faq-scraper

2️⃣ Crear entorn virtual (recomanat)
py -m venv .venv
.\.venv\Scripts\activate

3️⃣ Instal·lar dependències
py -m pip install -r requirements.txt

▶️ Executar l’aplicació
py app.py

## 📥 Format del CSV d’entrada

El CSV pot tenir:
- Capçalera
- No capçalera
- Separador , o ;

## ✅ Format recomanat

URL,topic
https://eseiaat.upc.edu/ca/.../preguntes-frequents,tfe
https://www.upc.edu/ca/graus/faqs/preus-reduccions-pagaments,preus

Columna 1 → URL
Columna 2 → Tema

## 📤 Formats de sortida

1️⃣ CSV

- Genera fitxer amb separador ;
- Compatible amb Excel en entorn ES/CA
  
Columnes generades:
| Tema | Pregunta | Resposta | Estat | Data creació | Darrera modificació | Persona darrera modificació | Dades amb actualització anual | Font |

2️⃣ JSON (Genweb)

Estructura:
[
  {
    "topic": "tfe",
    "source_url": "https://...",
    "items": [
      {"q": "Pregunta?", "a": "Resposta"}
    ]
  }
]

3️⃣ Google Sheets (OAuth)

Permet escriure directament en un Spreadsheet.

Si no existeix:
Es crea automàticament.

Si no existeix la pestanya:
També es crea automàticament.

## 🔐 Connexió amb Google Sheets (OAuth) — PAS A PAS

Aquesta aplicació utilitza OAuth Desktop App Login.

### 🥇 PAS 1 — Crear credencials a Google Cloud

Ves a: https://console.cloud.google.com

Crea un projecte nou

Activa:

Google Sheets API

Google Drive API

Ves a:

APIs & Services → Credentials

Clica:

Create Credentials → OAuth Client ID

Tipus:

Desktop application

Descarrega el JSON

Guarda’l com:

oauth_client.json


⚠️ Aquest fitxer NO s’ha de pujar a GitHub.

### 🥈 PAS 2 — Seleccionar el fitxer a l’app

A l’aplicació:

Prem "Explora…"

Selecciona el teu oauth_client.json


### 🥉 PAS 3 — Primera execució

Quan premis "Executa":

S’obrirà el navegador

Iniciaràs sessió amb Google

Acceptaràs permisos

Es crearà automàticament:

token.json

Aquest fitxer guarda la sessió.

## 🔁 Si vols forçar nou login

Esborra:
token.json
i torna a executar.

## 🛠️ Crear executable (.exe)

1️⃣ Instal·lar PyInstaller
py -m pip install pyinstaller

2️⃣ Tancar qualsevol exe obert
Si l’exe està obert, PyInstaller fallarà amb:
PermissionError: [WinError 5] Access Denied
Tanca’l abans de compilar.

3️⃣ Netejar build anterior (recomanat)
rmdir build /s /q
rmdir dist /s /q
del *.spec

4️⃣ Crear EXE

Executar en una sola línia:
py -m PyInstaller --noconfirm --clean --onefile --windowed --name "UPC_FAQ_Scraper" --icon=assets\upc_logo.ico --add-data "assets;assets" app.py

## 📂 Resultat

L’executable es genera a:
dist\UPC_FAQ_Scraper.exe

## 🧠 Errors comuns i solucions

❌ SpreadsheetNotFound: <Response [200]>

Estàs logat amb un altre compte
El sheet no existeix
El token és antic
Solució:
Esborra token.json
Executa de nou
Loga’t amb el compte correcte

❌ L’Spreadsheet es crea però està buit

Revisa:
Estàs mirant la pestanya correcta?
Google pot haver creat FAQs (1)
Mira les pestanyes inferiors

❌ Access Denied al crear exe

L’exe està obert
Defender el bloqueja
No tens permisos
Solució:
Tanca l’exe
Torna a compilar

## 🧩 Arquitectura simplificada

app.py       → Interfície gràfica
core.py      → Lògica de scraping i exportació
assets/      → Icones i imatges

Flux:
CSV → Scraping → Build rows → Export (CSV / Sheets / JSON)

## 📌 Bones pràctiques

No versionar secrets
Fer servir entorn virtual
Netejar build abans de generar exe
Esborrar token.json si hi ha problemes de login
