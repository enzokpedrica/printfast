#!/bin/bash
# Entrypoint do FastPrint — configura CUPS e inicia a aplicação.
set -e

# ---------------------------------------------------------------------------
# 1. Iniciar o daemon CUPS (necessário para lp/lpstat funcionarem)
# ---------------------------------------------------------------------------
if ! pgrep -x cupsd > /dev/null; then
    echo "[entrypoint] Iniciando CUPS..."
    service cups start
    sleep 2
fi

# ---------------------------------------------------------------------------
# 2. Configurar impressoras via variável de ambiente PRINTERS
#
# Formato: PRINTERS="Nome1=ipp://192.168.1.100/ipp/print,Nome2=ipp://192.168.1.101/ipp/print"
#
# Cada entrada cria (ou recria) uma fila CUPS apontando para o IP da impressora.
# O modelo "everywhere" (IPP Everywhere) funciona com a maioria das impressoras modernas.
# Para impressoras mais antigas, troque por "generic" ou o PPD correto.
# ---------------------------------------------------------------------------
if [ -n "$PRINTERS" ]; then
    echo "[entrypoint] Configurando impressoras..."
    IFS=',' read -ra PRINTER_LIST <<< "$PRINTERS"
    for entry in "${PRINTER_LIST[@]}"; do
        name="${entry%%=*}"
        uri="${entry#*=}"
        if [ -z "$name" ] || [ -z "$uri" ]; then
            echo "[entrypoint] Entrada inválida ignorada: '$entry'"
            continue
        fi
        echo "[entrypoint]   $name -> $uri"
        lpadmin -p "$name" -E -v "$uri" -m everywhere 2>/dev/null \
            || lpadmin -p "$name" -E -v "$uri" -m lsb/usr/cupsfilters/generic.ppd 2>/dev/null \
            || echo "[entrypoint]   AVISO: falha ao configurar $name (verifique URI e modelo)"
    done
    echo "[entrypoint] Impressoras configuradas."
fi

# ---------------------------------------------------------------------------
# 3. Criar symlink do banco SQLite para /app/data (volume persistente)
# ---------------------------------------------------------------------------
if [ ! -f /app/fastprint.db ] && [ -f /app/data/fastprint.db ]; then
    ln -s /app/data/fastprint.db /app/fastprint.db
elif [ ! -f /app/fastprint.db ]; then
    touch /app/data/fastprint.db
    ln -s /app/data/fastprint.db /app/fastprint.db
fi

# ---------------------------------------------------------------------------
# 4. Iniciar a aplicação
# ---------------------------------------------------------------------------
exec "$@"
