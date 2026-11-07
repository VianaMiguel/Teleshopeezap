@echo off
cd /d "%~dp0"
title Bot de Ofertas Telegram
echo ============================================
echo  Bot de Ofertas - Iniciando tudo...
echo ============================================

REM Matar instancias anteriores
taskkill /F /IM python.exe 2>nul
taskkill /F /IM uv.exe 2>nul
taskkill /F /IM node.exe 2>nul
timeout /t 3 >nul

REM Instalar dependencias do WhatsApp Server se necessario
if not exist "whatsapp-server\node_modules" (
  echo Instalando dependencias do WhatsApp Server...
  pushd whatsapp-server && npm install && popd
)

echo.
echo Iniciando Servidor WhatsApp...
start "WhatsApp Server" cmd /k "cd whatsapp-server && npm start"
timeout /t 5 >nul

echo Iniciando Bot de Ofertas...
echo (feche esta janela para parar o bot inteiro)
echo.
:loop
uv run python -m ofertas run
echo.
echo O bot parou (codigo %errorlevel%). Reiniciando em 15 segundos...
timeout /t 15 >nul
goto loop
