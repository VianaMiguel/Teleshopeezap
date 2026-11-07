#!/usr/bin/env bash
# Inicia bot + servidor WhatsApp juntos (Linux e macOS).
# Reinicia o bot se cair. Prefira o painel grafico:  bash painel.sh
set -e
# Caminho absoluto deste script (preciso para re-executar sob Xvfb depois do cd)
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
cd "$(dirname "$0")"

# uv instalado pelo instalador oficial fica em ~/.local/bin — cobre systemd/cron
if [ -d "$HOME/.local/bin" ]; then
  PATH="$HOME/.local/bin:$PATH"
  export PATH
fi

# VPS sem tela: o ML exige Chrome com janela visível (headless é bloqueado).
# Sem DISPLAY, re-executa sob Xvfb para o bot inteiro ter uma tela virtual.
if [ "$(uname -s)" = "Linux" ] && [ -z "${DISPLAY:-}" ]; then
  if command -v xvfb-run >/dev/null 2>&1; then
    echo "Sem tela (DISPLAY) — reexecutando sob Xvfb (tela virtual) para o Mercado Livre."
    echo "Login manual do ML exige tela de verdade:  ssh -X usuario@servidor"
    echo "(README, secao 'VPS sem tela (Oracle etc.)')"
    export OFERTAS_DISPLAY_VIRTUAL=1
    exec xvfb-run -a -s "-screen 0 1280x800x24" bash "$SELF" "$@"
  else
    echo "AVISO: sem DISPLAY e sem xvfb-run — a fonte Mercado Livre vai falhar."
    echo "       Instale com:  sudo apt install -y xvfb xauth"
    echo "       (o resto do bot roda normalmente)"
  fi
fi

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
