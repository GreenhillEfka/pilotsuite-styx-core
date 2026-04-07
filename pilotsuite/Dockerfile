# PilotSuite Core Add-on (v15.5.0 Gold)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY copilot_core/ ./copilot_core/

EXPOSE 5000

CMD ["python3", "-m", "copilot_core.api.gateway"]