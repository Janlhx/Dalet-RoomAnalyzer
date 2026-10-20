FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir flask requests

# Copiar código del servicio de alertas
COPY alerts/ ./alerts/

EXPOSE 5000

ENV ALERT_TEMP_THRESHOLD=26.0
ENV PORT=5000

CMD ["python3", "alerts/app.py"]
