ARG BUILD_FROM
FROM $BUILD_FROM

# Setze Working Directory
WORKDIR /data

# Kopiere ALLES aus addon Verzeichnis (einfachster Ansatz)
COPY . /data

# Installiere Python Dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Starte Application
CMD ["python3", "main.py"]
