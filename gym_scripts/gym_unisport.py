import requests
from bs4 import BeautifulSoup
import gspread
import json
import os
from datetime import datetime
import pytz
from oauth2client.service_account import ServiceAccountCredentials

GYM_NAME = "Unisport Bern"
URL = "https://www.zssw.unibe.ch/usp/zms/templates/crowdmonitoring/_display-spaces-zssw.php"
CSS_SELECTOR = ".go-stop-display_footer"

def setup_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

    if credentials_json:
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(credentials_json), scope)
    else:
        credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

    client = gspread.authorize(credentials)
    return client

def fetch_capacity():
    try:
        response = requests.get(URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        capacity_div = soup.select_one(CSS_SELECTOR)
        if capacity_div:
            capacity = int(capacity_div.get_text(strip=True).split(" von ")[0])
            return capacity
    except Exception as e:
        print(f"Fehler beim Abrufen für {GYM_NAME}: {e}")
    return None

def log_to_sheet(client, capacity):
    if capacity is not None:
        sheet = client.open("Fitnessstudio-Auslastung").worksheet(GYM_NAME)
        timestamp = datetime.now(pytz.utc).astimezone(pytz.timezone("Europe/Zurich")).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, capacity])
        print(f"{GYM_NAME}: {capacity} Personen gespeichert.")

if __name__ == "__main__":
    client = setup_google_sheets()
    capacity = fetch_capacity()
    log_to_sheet(client, capacity)
