FROM python:3.11-slim

# CUPS para impressão em Linux (lp, lpstat, lpadmin)
RUN apt-get update && apt-get install -y --no-install-recommends \
        cups \
        cups-client \
        cups-bsd \
        printer-driver-all-enforce \
    && rm -rf /var/lib/apt/lists/*

# Permite que o processo Python acesse o CUPS local sem ser root
RUN usermod -aG lpadmin www-data 2>/dev/null || true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Garante que o banco SQLite persiste em volume externo
VOLUME ["/app/data"]

EXPOSE 8000

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
