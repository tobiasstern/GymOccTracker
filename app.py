import time
import requests
import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 0
def get_google_credentials():
    """
    Nutzt entweder die Datei `credentials.json` (lokal) oder das Secret aus einer Umgebungsvariable (OpenShift).
    """
    credentials_path = "credentials.json"
    
    if os.path.exists(credentials_path):  
        # Lokale Datei existiert -> Diese verwenden
        print("Lade lokale credentials.json Datei...")
        return ServiceAccountCredentials.from_json_keyfile_name(credentials_path)
    
    # Falls keine Datei da ist, versuche die Umgebungsvariable zu nutzen
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    
    if credentials_json:
        print("Lade Google Credentials aus OpenShift Secret...")
        return ServiceAccountCredentials.from_json_keyfile_dict(json.loads(credentials_json))
    
    raise Exception("Keine gültigen Google Credentials gefunden!")


# 1. Google Sheets einrichten
def setup_google_sheets(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = get_google_credentials()
    client = gspread.authorize(credentials)

    try:
        sheet = client.open(sheet_name).sheet1
    except gspread.SpreadsheetNotFound:
        print("Google Sheet wurde nicht gefunden. Ein neues wird erstellt...")
        sheet = client.create(sheet_name).sheet1
        sheet.append_row(["Timestamp", "Auslastung (%)"])
    except Exception as e:
        print(f"Fehler beim Zugriff auf Google Sheets: {e}")
        return None

    return sheet

# 2. Auslastung von URL abrufen
def fetch_capacity(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        capacity = response.text

        # Wenn die Kapazität "-" ist, ersetze sie durch "0"
        if capacity == "—":
            capacity = 0

        # Konvertiere die Kapazität sicher zu einer Zahl
        try:
            capacity = int(capacity)
        except ValueError:
            print(f"Ungültige Kapazität: {capacity}")
            return

        return capacity

    except Exception as e:
        print(f"Fehler beim Abrufen der Daten: {e}")
        return None

# 3. Daten in Google Sheet speichern
def log_to_sheet(sheet, capacity):
    if capacity is not None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Schreibe den Wert ins Google Sheet (inkl. konvertiertem Datum)
        sheet.append_row([timestamp, capacity], value_input_option='USER_ENTERED')
        print(f"Daten gespeichert: {timestamp}, {capacity}")
    else:
        print("Keine Daten gespeichert, da keine Auslastung verfügbar war.")

# 4. Hauptfunktion: Alle 30 Minuten ausführen
def main():
    url = "https://www.fitnesspark.ch/wp/wp-admin/admin-ajax.php?action=single_park_update_visitors&park_id=856&location_id=105&location_name=FP_Bern_City"

    sheet_name = "Fitnesspark Auslastung"
    sheet = setup_google_sheets(sheet_name)

    while True:
        capacity = fetch_capacity(url)
        log_to_sheet(sheet, capacity)
        time.sleep(5* 60) # 5 Minuten warten, da die Auslastung scheinbar nicht so oft ändert

if __name__ == "__main__":
    main()
