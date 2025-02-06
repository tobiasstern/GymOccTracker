import time
import requests
import gspread
import os
import json
import sys
import pytz
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# Konfiguriere unbuffered Output für konsistente Logs
sys.stdout.reconfigure(line_buffering=True)

# Gym-spezifische Konstanten
GYM_NAME = "Fitnesspark-Bern"
URL = "https://www.fitnesspark.ch/wp/wp-admin/admin-ajax.php?action=single_park_update_visitors&park_id=856&location_id=105&location_name=FP_Bern_City"
GSHEET_NAME = "Fitnesspark Auslastung"

# Standardintervall in Sekunden (derzeit 60 Sekunden, kann per Umgebungsvariable überschrieben werden)
DEFAULT_INTERVAL = 60

def get_check_interval():
    """
    Liest das Prüfintervall aus der Umgebungsvariable CHECK_INTERVAL_FP_BE oder nutzt den Standardwert.
    """
    try:
        interval = int(os.getenv("CHECK_INTERVAL_FP_BE", DEFAULT_INTERVAL))
        if interval < 10:
            print("WARNUNG: CHECK_INTERVAL_FP_BE ist zu klein, setze auf 10 Sekunden", flush=True)
            return 10
        print(f"Nächste Prüfung in {interval} Sekunden", flush=True)
        return interval
    except ValueError:
        print(f"Ungültiger CHECK_INTERVAL_FP_BE-Wert, nutze Standard ({DEFAULT_INTERVAL} Sekunden)", flush=True)
        return DEFAULT_INTERVAL

def get_google_credentials():
    """
    Nutzt entweder die lokale Datei credentials.json oder das Secret aus der Umgebungsvariable GOOGLE_CREDENTIALS_JSON.
    Gibt ein ServiceAccountCredentials-Objekt zurück.
    """
    credentials_path = "credentials.json"

    # Lokale Datei bevorzugt
    if os.path.exists(credentials_path):
        print("Lade lokale credentials.json Datei...", flush=True)
        return ServiceAccountCredentials.from_json_keyfile_name(credentials_path)

    # Falls die Datei nicht existiert, wird die Umgebungsvariable verwendet
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
    Das Worksheet wird anhand des Gym-Namens (GYM_NAME) ausgewählt.
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = get_google_credentials()
    client = gspread.authorize(credentials)

    try:
        # Versucht, das Worksheet mit dem Namen GYM_NAME zu öffnen
        sheet = client.open(GSHEET_NAME).worksheet(GYM_NAME)
    except gspread.SpreadsheetNotFound:
        print("Google Sheet wurde nicht gefunden. Ein neues wird erstellt...", flush=True)
        # Falls das Worksheet nicht existiert, wird es erstellt und mit Überschriften versehen
        sheet = client.create(GSHEET_NAME).worksheet(GYM_NAME)
        sheet.append_row(["Timestamp", "Auslastung (%)"], value_input_option='USER_ENTERED')
    except Exception as e:
        print(f"Fehler beim Zugriff auf Google Sheets: {e}", flush=True)
        return None

    return sheet

def fetch_capacity():
    """
    Ruft die aktuelle Auslastung des Fitnessstudios von der URL ab.
    Erwartet, dass die API-Antwort einen reinen Zahlenwert liefert.
    """
    try:
        response = requests.get(URL)
        response.raise_for_status()
        capacity = response.text.strip()  # Entfernt überflüssige Leerzeichen und Zeilenumbrüche

        print(f"API-Antwort erhalten: {capacity}", flush=True)

        # Falls der Wert "—" zurückgegeben wird, wird er auf 0 gesetzt
        if capacity == "—":
            capacity = 0

        # Versuch, den Wert in eine Zahl zu konvertieren
        try:
            capacity = int(capacity)
        except ValueError:
            print(f"Ungültige Kapazität (keine Zahl): '{capacity}'", flush=True)
            return None

        return capacity

    except requests.RequestException as e:
        print(f"Fehler beim Abrufen für {GYM_NAME}: {e}", flush=True)
        return None

def log_to_sheet(sheet, capacity):
    """
    Schreibt den aktuellen Timestamp und die ermittelte Auslastung in das Google Sheet.
    """
    if capacity is not None:
        local_tz = pytz.timezone("Europe/Zurich")
        timestamp = datetime.now(pytz.utc).astimezone(local_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, capacity], value_input_option='USER_ENTERED')
        print(f"{GYM_NAME}: Daten gespeichert: {timestamp}, {capacity}", flush=True)
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
