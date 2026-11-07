#!/usr/bin/env bash
# Inicia SO o servidor WhatsApp (Linux e macOS).
set -e
cd "$(dirname "$0")/whatsapp-server"

if [ ! -d node_modules ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "Instalando dependencias do WhatsApp Server..."
    npm install
  else
    echo "ERRO: npm nao encontrado. Instale o Node.js: https://nodejs.org/"
    exit 1
  fi
fi

echo "============================================"
echo " Servidor WhatsApp rodando..."
echo " Escaneie o QR Code com o WhatsApp"
echo "============================================"
npm start
