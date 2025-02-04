import time
from datetime import datetime
import pytz
import requests
import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import sys

sys.stdout.reconfigure(line_buffering=True) # configures all prin()-statements to have the option flush=True, because without sometimes logging is not consistent
GYM_NAME = "Fitnesspark-Bern"
URL = "https://www.fitnesspark.ch/wp/wp-admin/admin-ajax.php?action=single_park_update_visitors&park_id=856&location_id=105&location_name=FP_Bern_City"
GSHEET_NAME = "Fitnesspark Auslastung"

# Standard-Intervall auf 5 Minuten setzen
DEFAULT_INTERVAL = 60  # 300 Sekunden = 5 Minuten

def get_check_interval():
    """Liest das Prüf-Intervall aus der Umgebungsvariable oder nutzt den Standardwert."""
    try:
        interval = int(os.getenv("CHECK_INTERVAL", DEFAULT_INTERVAL))  # Default 5 Minuten
        if interval < 10:  # Verhindert zu kleine Werte (z. B. 1 Sekunde)
            print("WARNUNG: CHECK_INTERVAL ist zu klein, setze auf 10 Sekunden")
            return 10
        print(f"Nächste Prüfung in {interval} Sekunden")
        return interval
    except ValueError:
        print(f"Ungültiger CHECK_INTERVAL-Wert, nutze Standard ({DEFAULT_INTERVAL} Sekunden)")
        return DEFAULT_INTERVAL


# 0
def get_google_credentials():
    """
    Nutzt entweder die Datei `credentials.json` (lokal) oder das Secret aus einer Umgebungsvariable (OpenShift).
    Fügt Debugging hinzu, um Fehler bei fehlender oder leerer Umgebungsvariable zu erkennen.
    """
    credentials_path = "credentials.json"

    # Lokale Datei zuerst prüfen
    if os.path.exists(credentials_path):
        print("Lade lokale credentials.json Datei...")
        return ServiceAccountCredentials.from_json_keyfile_name(credentials_path)

    # Falls keine Datei, prüfe die Umgebungsvariable
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

    # Debugging: Zeige die ersten 100 Zeichen der Variable (aber nicht das ganze JSON)
    if credentials_json:
        print(f" Lade Google Credentials aus OpenShift Secret... (Erste 100 Zeichen: {credentials_json[:100]}...)")
    else:
        print("FEHLER: Umgebungsvariable GOOGLE_CREDENTIALS_JSON ist nicht gesetzt oder leer!")

    # Falls Variable leer ist, Fehlermeldung ausgeben
    if not credentials_json:
        raise Exception("Keine gültigen Google Credentials gefunden! Bitte prüfen, ob das Secret richtig gesetzt ist.")

    # JSON-Daten umwandeln
    try:
        return ServiceAccountCredentials.from_json_keyfile_dict(json.loads(credentials_json))
    except json.JSONDecodeError as e:
        print(f"JSON-Fehler: {e}")
        print("Inhalt der Umgebungsvariable ist kein gültiges JSON. Bitte prüfen, ob das Secret richtig gespeichert wurde.")
        raise


# 1. Google Sheets einrichten
def setup_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = get_google_credentials()
    client = gspread.authorize(credentials)

    try:
        sheet = client.open(GSHEET_NAME).worksheet(GYM_NAME)
    except gspread.SpreadsheetNotFound:
        print("Google Sheet wurde nicht gefunden. Ein neues wird erstellt...")
        sheet = client.create(GSHEET_NAME).worksheet(GYM_NAME)
        sheet.append_row(["Timestamp", "Auslastung (%)"])
    except Exception as e:
        print(f"Fehler beim Zugriff auf Google Sheets: {e}")
        return None

    return sheet

# 2. Auslastung von URL abrufen
def fetch_capacity():
    try:
        response = requests.get(URL)
        response.raise_for_status()
        capacity = response.text.strip()  # Entfernt unnötige Leerzeichen oder Zeilenumbrüche

        print(f"API-Antwort erhalten: {capacity}")  # Debugging-Ausgabe

        # Wenn die Kapazität "-" ist, ersetze sie durch "0"
        if capacity == "—":
            capacity = 0

        # Konvertiere die Kapazität sicher zu einer Zahl
        try:
            capacity = int(capacity)
        except ValueError:
            print(f"Ungültige Kapazität (keine Zahl): '{capacity}'")  # Jetzt wird der fehlerhafte Wert geloggt
            return None

        return capacity

    except requests.RequestException as e:
        print(f"Fehler beim Abrufen für {GYM_NAME}: {e}")
        return None


# 3. Daten in Google Sheet speichern
def log_to_sheet(sheet, capacity):
    if capacity is not None:
        # Setze deine gewünschte Zeitzone (z. B. "Europe/Berlin")
        local_tz = pytz.timezone("Europe/Zurich")

        # Hole die aktuelle UTC-Zeit und konvertiere sie in die lokale Zeitzone
        timestamp = datetime.now(pytz.utc).astimezone(local_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        # Schreibe den Wert ins Google Sheet (inkl. konvertiertem Datum)
        sheet.append_row([timestamp, capacity], value_input_option='USER_ENTERED')
        print(f"Daten gespeichert: {timestamp}, {capacity}")
    else:
        print("Keine Daten gespeichert, da keine Auslastung verfügbar war.")

# 4. Hauptfunktion: Alle 30 Minuten ausführen
def main():
    sheet = setup_google_sheets()

    while True:
        capacity = fetch_capacity()
        log_to_sheet(sheet, capacity)

        interval = get_check_interval()  # Laufzeit-Check des Intervalls
        time.sleep(interval)  # Warte die konfigurierte Zeit

        #time.sleep(5* 60) # 5 Minuten warten, da die Auslastung scheinbar nicht so oft ändert

if __name__ == "__main__":
    main()
