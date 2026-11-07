#!/usr/bin/env bash
# Painel de controle do Bot de Ofertas (Linux e macOS).
# Rode com:  bash painel.sh   (ou dê permissão: chmod +x painel.sh  e execute ./painel.sh)
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
    echo "       (o resto do painel roda normalmente)"
  fi
fi

echo
echo "  ============================================"
echo "    BOT DE OFERTAS - PAINEL DE CONTROLE"
echo "  ============================================"
echo

# 1) Garante o uv instalado
if ! command -v uv >/dev/null 2>&1; then
  echo "  O 'uv' nao esta instalado. Instalando agora..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  echo
  echo "  ------------------------------------------------------------"
  echo "  uv instalado! FECHE este terminal e rode o painel de novo."
  echo "  (ou rode:  source \$HOME/.local/bin/env  e tente de novo)"
  echo "  ------------------------------------------------------------"
  exit 0
fi

# 2) Prepara o ambiente Python (rapido depois da primeira vez)
echo "  Preparando o ambiente (pode demorar na primeira vez)..."
uv sync

# 2.5) Dependencias do servidor WhatsApp (se necessario)
if [ -f whatsapp-server/package.json ] && [ ! -d whatsapp-server/node_modules ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "  Instalando dependencias do WhatsApp Server..."
    (cd whatsapp-server && npm install)
  else
    echo "  AVISO: npm nao encontrado - servidor WhatsApp nao sera instalado."
    echo "         (instale o Node.js: https://nodejs.org/)"
  fi
fi

# 3) Abre o painel no navegador
echo
echo "  Abrindo o painel no navegador..."
echo "  (deixe este terminal aberto enquanto usar o painel)"
echo "  O painel vai:"
echo "    - garantir que o servidor WhatsApp esteja conectado;"
echo "    - ligar o bot sozinho e comecar a publicar."
echo "  (para nao ligar sozinho: PAINEL_AUTO_START=0 no .env)"
echo
uv run python -m ofertas painel
