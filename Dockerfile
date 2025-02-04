# Basis-Image mit Python 3.9
FROM python:3.9-slim

# Arbeitsverzeichnis im Container setzen
WORKDIR /app

# Abhängigkeiten kopieren und installieren
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Alle Gym-Skripte kopieren
COPY gym_scripts/ /app/gym_scripts/

# Standardmäßig läuft das Image ohne ein spezifisches Gym-Skript
CMD ["python", "--version"]
