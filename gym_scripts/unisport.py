import time
import requests
import gspread
import json
import os
import sys
import pytz
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup

# Konfiguriere unbuffered Output für konsistente Logs
sys.stdout.reconfigure(line_buffering=True)

# Gym-spezifische Konstanten
GYM_NAME = "Unisport-Zssw"
URL = "https://www.zssw.unibe.ch/usp/zms/templates/crowdmonitoring/_display-spaces-zssw.php"
GSHEET_NAME = "Fitnesspark Auslastung"  # Gemeinsame Google Sheets-Datei
CSS_SELECTOR = ".go-stop-display_footer"  # Selektor, der den Text "33 von 80" enthält

# Standardintervall in Sekunden (hier: 60 Sekunden; kann per CHECK_INTERVAL_UNISPORT_BERN überschrieben werden)
DEFAULT_INTERVAL = 60

def get_check_interval():
    """
    Liest das Prüfintervall aus der Umgebungsvariable CHECK_INTERVAL_UNISPORT_BERN oder nutzt den Standardwert.
    """
    try:
        interval = int(os.getenv("CHECK_INTERVAL_UNISPORT_BERN", DEFAULT_INTERVAL))
        if interval < 10:
            print("WARNUNG: CHECK_INTERVAL_UNISPORT_BERN ist zu klein, setze auf 10 Sekunden", flush=True)
            return 10
        print(f"Nächste Prüfung in {interval} Sekunden", flush=True)
        return interval
    except ValueError:
        print(f"Ungültiger CHECK_INTERVAL_UNISPORT_BERN-Wert, nutze Standard ({DEFAULT_INTERVAL} Sekunden)", flush=True)
        return DEFAULT_INTERVAL

def get_google_credentials():
    """
    Nutzt entweder die lokale Datei credentials.json oder das Secret aus der Umgebungsvariable GOOGLE_CREDENTIALS_JSON.
    Gibt ein ServiceAccountCredentials-Objekt zurück.
    """
    credentials_path = "credentials.json"

    if os.path.exists(credentials_path):
        print("Lade lokale credentials.json Datei...", flush=True)
        return ServiceAccountCredentials.from_json_keyfile_name(credentials_path)
    
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if credentials_json:
        print(f"Lade Google Credentials aus OpenShift Secret... (Erste 100 Zeichen: {credentials_json[:100]}...)", flush=True)
    else:
        print("FEHLER: Umgebungsvariable GOOGLE_CREDENTIALS_JSON ist nicht gesetzt oder leer!", flush=True)
    
    if not credentials_json:
        raise Exception("Keine gültigen Google Credentials gefunden! Bitte prüfen, ob das Secret richtig gesetzt ist.")
    
    try:
        return ServiceAccountCredentials.from_json_keyfile_dict(json.loads(credentials_json))
    except json.JSONDecodeError as e:
        print(f"JSON-Fehler: {e}", flush=True)
        print("Inhalt der Umgebungsvariable ist kein gültiges JSON. Bitte prüfen, ob das Secret richtig gespeichert wurde.", flush=True)
        raise

def setup_google_sheets():
    """
    Initialisiert und gibt das Google Sheets-Worksheet zurück, das für dieses Fitnessstudio verwendet wird.
    Es wird versucht, ein Worksheet mit dem Namen GYM_NAME in der Google Sheets-Datei GSHEET_NAME zu öffnen.
    Falls es nicht existiert, wird es erstellt und mit Überschriften versehen.
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = get_google_credentials()
    client = gspread.authorize(credentials)
    try:
        sheet = client.open(GSHEET_NAME).worksheet(GYM_NAME)
    except gspread.SpreadsheetNotFound:
        print("Google Sheet wurde nicht gefunden. Ein neues wird erstellt...", flush=True)
        sheet = client.create(GSHEET_NAME).worksheet(GYM_NAME)
        sheet.append_row(["Timestamp", "Auslastung (%)"], value_input_option='USER_ENTERED')
    except Exception as e:
        print(f"Fehler beim Zugriff auf Google Sheets: {e}", flush=True)
        return None
    return sheet

def fetch_capacity():
    """
    Ruft die aktuelle Auslastung von Unisport Bern ab, indem die HTML-Seite abgerufen und der Wert mittels BeautifulSoup extrahiert wird.
    Erwartet wird ein Text im Format "33 von 80". Es wird die erste Zahl extrahiert.
    """
    try:
        response = requests.get(URL)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.select_one(CSS_SELECTOR)
        if element:
            text = element.get_text(strip=True)
            print(f"Gefundener Text: {text}", flush=True)
            # Erwarte ein Format wie "33 von 80"
            parts = text.split(" von ")
            if parts and parts[0].isdigit():
                return int(parts[0])
            else:
                print(f"Ungültiges Format: {text}", flush=True)
                return None
        else:
            print("Kein Element mit dem angegebenen CSS-Selektor gefunden.", flush=True)
            return None
    except requests.RequestException as e:
        print(f"Fehler beim Abrufen der Daten für {GYM_NAME}: {e}", flush=True)
        return None

def log_to_sheet(sheet, capacity):
    """
    Schreibt den aktuellen Timestamp und die ermittelte Auslastung in das Google Sheet.
    """
    if capacity is not None:
        local_tz = pytz.timezone("Europe/Zurich")
        timestamp = datetime.now(pytz.utc).astimezone(local_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, capacity], value_input_option='USER_ENTERED')
        print(f"{GYM_NAME}: {capacity} Personen gespeichert: {timestamp}", flush=True)
    else:
        print("Keine Daten gespeichert, da keine Auslastung verfügbar war.", flush=True)

def main():
    sheet = setup_google_sheets()
    while True:
        capacity = fetch_capacity()
        log_to_sheet(sheet, capacity)
        interval = get_check_interval()
        time.sleep(interval)

if __name__ == "__main__":
    main()
