# Basis-Image mit Python
FROM python:3.9-slim

# Arbeitsverzeichnis im Container setzen
WORKDIR /app

# Kopiere alle Dateien ins Arbeitsverzeichnis
COPY gym_scripts/ /app/gym_scripts/
COPY requirements.txt /app/

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Stelle sicher, dass die credentials.json nicht vergessen wird
# COPY credentials.json /app/credentials.json

# Setze den Befehl, der beim Start des Containers ausgeführt wird
CMD ["python", "-m", "gym_scripts"]
