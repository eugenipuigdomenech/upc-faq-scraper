import requests
from bs4 import BeautifulSoup
import csv
import gspread
from google.oauth2.service_account import Credentials

# ------------------------------------------------------------
# Funció que extreu les FAQs (Pregunta + Resposta)
# ------------------------------------------------------------
def scrape_faqs(url: str):

    r = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    q_tags = soup.select(
        '#collapse-base a[data-toggle="collapse"][href^="#collapse-"]'
    )

    faqs = []

    for q in q_tags:

        question = q.get_text(" ", strip=True)

        target_id = q.get("href", "").lstrip("#")

        collapse_div = soup.find(id=target_id)
        if not collapse_div:
            continue

        body = collapse_div.select_one(".panel-body") or collapse_div
        answer = body.get_text(" ", strip=True)

        faqs.append((question, answer))

    return faqs

def upload_to_google_sheets(faqs, spreadsheet_name: str, worksheet_name: str = "Sheet1"):

    scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    client = gspread.authorize(creds)

    sh = client.open("upc-faqs")
    ws = sh.worksheet("faqs1")

    # Esborra contingut antic
    ws.clear()

    # Preparem dades amb capçalera
    rows = [["Pregunta", "Resposta"]] + [[q, a] for q, a in faqs]

    ws.update(values=rows, range_name="A1")

    print("FAQs pujades correctament al Google Sheets (upc-faqs)")


if __name__ == "__main__":

     url = "https://www.upc.edu/ca/graus/faqs/preinscripcio-i-assignacio" # UPC faqs
    # url = "https://eseiaat.upc.edu/ca/curs-actual/treballs-fi-estudis/preguntes-frequents" # ESEIAAT tfe
    # url = "https://eseiaat.upc.edu/ca/empresa/preguntes-frequents" # ESEIAAT empresa
    # url = "https://eseiaat.upc.edu/ca/international-office/incomings/faqs" # ESEIAAT mobilitat
    # url = "https://eseiaat.upc.edu/ca/acte-graduacio/preguntes-mes-frequents" # ESEIAAT acte graduació

    faqs = scrape_faqs(url)


    # Pujar a upc-faqs (google sheets)
    upload_to_google_sheets(
        faqs,
        spreadsheet_name="upc-faqs",  # titol del sheets
        worksheet_name="faqs1"  # nom de la pestanya
    )

    print("TOTAL FAQS:", len(faqs))
    # Mostrem per consola també
    for i, (q, a) in enumerate(faqs, 1):
        print(f"\n[{i}] Q: {q}")
        print(f"A: {a}")
        print("-" * 60)