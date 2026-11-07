#!/usr/bin/env bash
# Inicia bot + servidor WhatsApp juntos (Linux e macOS).
# Reinicia o bot se cair. Prefira o painel grafico:  bash painel.sh
set -e
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "Instale o uv primeiro:  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

uv sync

# Dependencias do servidor WhatsApp (se necessario)
if [ ! -d whatsapp-server/node_modules ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "Instalando dependencias do WhatsApp Server..."
    (cd whatsapp-server && npm install)
  else
    echo "AVISO: npm nao encontrado - apenas o bot (Telegram) vai rodar."
  fi
fi

# Sobe o servidor WhatsApp em background (se Node disponivel)
WA_PID=""
if command -v node >/dev/null 2>&1 && [ -d whatsapp-server/node_modules ]; then
  echo "Iniciando Servidor WhatsApp..."
  (cd whatsapp-server && exec node src/index.js) &
  WA_PID=$!
  # EXIT limpa o node; INT/TERM encerram o script (e disparam o EXIT)
  trap '[ -n "$WA_PID" ] && kill "$WA_PID" 2>/dev/null || true' EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  sleep 3
else
  echo "Aviso: Node.js nao encontrado - apenas o bot (Telegram) vai rodar."
fi

echo "Iniciando Bot de Ofertas..."
echo "(Ctrl+C para parar o bot inteiro)"
echo
while true; do
  uv run python -m ofertas run || true
  echo
  echo "O bot parou. Reiniciando em 15s (Ctrl+C para sair)..."
  sleep 15
done
