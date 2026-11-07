@echo off
cd /d "%~dp0whatsapp-server"
echo ============================================
echo  Servidor WhatsApp rodando...
echo  Escaneie o QR Code com o WhatsApp
echo ============================================
cmd /k "npm start"
