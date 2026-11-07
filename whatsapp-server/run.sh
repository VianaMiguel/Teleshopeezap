#!/usr/bin/env bash
# Inicia o servidor WhatsApp (Linux e macOS).
set -e
cd "$(dirname "$0")"

if [ ! -d node_modules ]; then
  echo "Instalando dependencias do WhatsApp Server..."
  npm install
fi

echo "============================================"
echo " Servidor WhatsApp rodando..."
echo " Escaneie o QR Code com o WhatsApp"
echo "============================================"
npm start
echo "Servidor encerrado."
