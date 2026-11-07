@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Bot de Ofertas - Painel de Controle (sem taskkill)

echo.
echo   ============================================
echo     BOT DE OFERTAS - PAINEL DE CONTROLE
echo   ============================================
echo.

REM 1) Garante que o uv esta instalado
where uv >nul 2>nul
if errorlevel 1 (
  echo   O 'uv' nao esta instalado. Instalando agora...
  winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements
  echo.
  echo   ------------------------------------------------------------
  echo   uv instalado! FECHE esta janela e abra o PAINEL_safe.bat de novo.
  echo   ------------------------------------------------------------
  pause
  exit /b
)

REM 2) Instala/atualiza as dependencias (rapido depois da primeira vez)
echo   Preparando o ambiente (pode demorar na primeira vez)...
uv sync
if errorlevel 1 goto erro

REM 2.5) Instala dependencias do servidor WhatsApp (se necessario)
if exist "whatsapp-server\package.json" (
  if not exist "whatsapp-server\node_modules" (
    echo   Instalando dependencias do WhatsApp Server...
    pushd whatsapp-server && npm install && popd
  ) else (
    echo   Dependencias do WhatsApp Server ja instaladas.
  )
)

REM 3) Inicia Servidor WhatsApp e abre o painel no navegador
echo.
echo   Iniciando Servidor WhatsApp...
echo   (deixe esta janela aberta enquanto usar o painel)
echo.
start "WhatsApp Server" cmd /k "cd whatsapp-server && npm start"
timeout /t 3 >nul
echo.
echo   Abrindo o painel no navegador...
echo.
echo   O painel vai:
echo     - garantir que o servidor WhatsApp esteja conectado;
echo     - ligar o bot sozinho e comecar a publicar.
echo   (para nao ligar sozinho: PAINEL_AUTO_START=0 no .env)
echo.
uv run python -m ofertas painel
goto fim

:erro
echo.
echo   ============================================================
echo   Algo deu errado ao preparar o ambiente.
echo.
echo   Se apareceu "Failed to spawn: python" ou algo sobre
echo   "Controle de Aplicativo", e o Smart App Control do Windows.
echo   Veja como desligar no arquivo README (secao "Problemas comuns").
echo   ============================================================
echo.

:fim
echo.
echo   Painel encerrado. Pressione uma tecla para sair.
pause >nul
