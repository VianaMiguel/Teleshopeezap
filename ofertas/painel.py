"""Painel de controle gráfico (interface web local) para o bot de ofertas.

Roda um servidor só em 127.0.0.1 e abre no navegador. Dali dá para:
- preencher a configuração (.env) em formulário, sem editar arquivo à mão;
- instalar o navegador, fazer login no Mercado Livre e testar as fontes por botões;
- descobrir os IDs do Telegram automaticamente;
- ligar/desligar o bot e acompanhar o log ao vivo — tudo sem terminal.

Sobe com:  uv run python -m ofertas painel   (ou rode:  bash painel.sh)
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests

from .config import BASE_DIR, DATA_DIR, config
from .painel_html import PAGINA

HOST, PORT = "127.0.0.1", 8481
ENV_PATH = BASE_DIR / ".env"
WA_URL = "http://localhost:4000"
WA_DIR = BASE_DIR / "whatsapp-server"
WA_ENTRY = WA_DIR / "src" / "index.js"

# (chave, rótulo, grupo, é_segredo, ajuda)
CAMPOS = [
    ("TELEGRAM_BOT_TOKEN", "Token do bot", "Telegram", True,
     "Crie no @BotFather com /newbot e cole o token aqui."),
    ("TELEGRAM_OWNER_ID", "Seu user ID", "Telegram", False,
     "Use o botão 'Detectar IDs' depois de colocar o token."),
    ("TELEGRAM_CHAT_ID", "ID do canal", "Telegram", False,
     "O canal onde o bot posta. Use 'Detectar IDs'."),
    ("ML_ETIQUETA", "Etiqueta do afiliado", "Mercado Livre", False,
     "A 'Etiqueta em uso' que aparece no Linkbuilder do painel de afiliados."),
    ("AMAZON_TAG", "Tag de associado", "Amazon", False,
     "Sua tag do Amazon Associados (ex: seunome-20)."),
    ("AMAZON_CREDENTIAL_ID", "Creators API — ID", "Amazon", False,
     "Opcional. Associates Central > Creators API > Aplicativos."),
    ("AMAZON_CREDENTIAL_SECRET", "Creators API — Secret", "Amazon", True,
     "Opcional. Aparece só uma vez, na criação da credencial."),
    ("SHOPEE_APP_ID", "App ID", "Shopee", False,
     "Painel de afiliados Shopee > menu 'Abrir API'."),
    ("SHOPEE_APP_SECRET", "App Secret", "Shopee", True,
     "Painel de afiliados Shopee > menu 'Abrir API'."),
    # WhatsApp
    ("WHATSAPP_ACCESS_TOKEN", "Token de Acesso do WhatsApp", "WhatsApp", True,
     "Só para a API oficial do WhatsApp Business. Com o servidor local deste projeto, deixe em branco."),
    ("WHATSAPP_CHAT_ID", "ID do grupo/canal", "WhatsApp", False,
     "Para onde vão as ofertas (ex.: 120363432876585377@newsletter ou 120363...@g.us). "
     "Descubra com: uv run python -m ofertas listar-grupos-whatsapp"),
    # Facebook
    ("FACEBOOK_ACCESS_TOKEN", "Token de Acesso do Facebook", "Facebook", True,
     "Gerado em Configurações do Desenvolvedor > Tokens de Acesso."),
    ("FACEBOOK_PAGE_ID", "ID da Página", "Facebook", False,
     "ID numérico da página que recebe os posts (ex: 123456789012345)."),
]
CHAVES = [c[0] for c in CAMPOS]

# ── Servidor WhatsApp (whatsapp-server, porta 4000) ────────────────────

_wa_cache: dict = {"t": 0.0, "valor": {"rodando": False, "conectado": False}}
_wa_lock = threading.Lock()


def status_whatsapp(force: bool = False) -> dict:
    """{rodando, conectado} do servidor local. Cache de 2s para não travar o polling."""
    agora = time.monotonic()
    if not force and agora - _wa_cache["t"] < 2.0:
        return _wa_cache["valor"]
    rodando = conectado = False
    try:
        r = requests.get(f"{WA_URL}/status", timeout=2)
        if r.status_code == 200:
            rodando = True
            conectado = bool(r.json().get("connected"))
    except Exception:
        pass
    _wa_cache.update(t=agora, valor={"rodando": rodando, "conectado": conectado})
    return _wa_cache["valor"]


def auto_start_ativo() -> bool:
    """PAINEL_AUTO_START=0 (no .env ou no ambiente) desliga o ligar-sozinho."""
    valor = os.getenv("PAINEL_AUTO_START", "")
    if not valor and ENV_PATH.exists():
        for linha in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if linha.strip().upper().startswith("PAINEL_AUTO_START="):
                valor = linha.split("=", 1)[1].strip()
    return valor.strip().lower() not in {"0", "false", "no", "off", "nao", "não"}


def _subir_servidor_whatsapp() -> bool:
    """Sobe o node do whatsapp-server em janela oculta (saída no log do painel)."""
    if wa.rodando():
        return True
    node = shutil.which("node")
    if not node or not WA_ENTRY.exists():
        return False
    return wa.iniciar(None, "Servidor WhatsApp",
                      cmd=[node, str(WA_ENTRY)], cwd=WA_DIR)


def garantir_whatsapp_conectado(timeout: int = 90) -> bool:
    """Garante o servidor WhatsApp no ar e conectado até `timeout` segundos.

    - se a porta estiver morta, sobe o servidor (com pausa para não duplicar
      o que o painel.sh/run.sh já abriu);
    - devolve True se em algum momento ele responder connected:true.
    """
    if not (config.fonte_whatsapp.get("ativa") and ler_env().get("WHATSAPP_CHAT_ID")):
        return False
    with _wa_lock:
        if status_whatsapp(force=True)["conectado"]:
            return True
        bot.linhas.append("• Aguardando o servidor WhatsApp conectar "
                          "(na 1ª vez ele pode gerar um QR Code)...")

        subiu = False
        parado_desde: float | None = None
        fim = time.monotonic() + timeout
        while time.monotonic() < fim:
            st = status_whatsapp(force=True)
            if st["conectado"]:
                bot.linhas.append("✅ WhatsApp conectado — servidor pronto.")
                return True
            if st["rodando"]:
                parado_desde = None
            else:
                if parado_desde is None:
                    parado_desde = time.monotonic()
                elif not subiu and time.monotonic() - parado_desde >= 4:
                    subiu = True
                    if _subir_servidor_whatsapp():
                        bot.linhas.append("• Servidor WhatsApp subiu pelo painel.")
                    else:
                        bot.linhas.append("⚠️ Não consegui subir o servidor WhatsApp "
                                          "(Node.js instalado? whatsapp-server/src/index.js existe?).")
            time.sleep(2)
        bot.linhas.append("⚠️ WhatsApp não conectou a tempo — o Telegram/Facebook "
                          "continuam normais.")
        return False


def ler_env() -> dict[str, str]:
    valores = {k: "" for k in CHAVES}
    if ENV_PATH.exists():
        for linha in ENV_PATH.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, _, v = linha.partition("=")
                if k.strip() in valores:
                    valores[k.strip()] = v.strip()
    return valores


def _extras_env() -> dict[str, str]:
    """Chaves do .env que não estão no formulário (ex.: TELEGRAM_SOURCE_CHAT_ID,
    PAINEL_AUTO_START) — precisam sobreviver a um salvamento do painel."""
    extras: dict[str, str] = {}
    if ENV_PATH.exists():
        for linha in ENV_PATH.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, _, v = linha.partition("=")
                if k.strip() not in CHAVES:
                    extras[k.strip()] = v.strip()
    return extras


def salvar_env(novos: dict[str, str]) -> None:
    atuais = ler_env()
    for k, v in novos.items():
        if k in atuais:
            atuais[k] = str(v).strip()
    extras = _extras_env()
    linhas = ["# Configuração do bot de ofertas (gerado pelo painel).",
              "# Não compartilhe este arquivo — ele guarda seus segredos.", ""]
    grupo_atual = None
    for chave, rotulo, grupo, *_ in CAMPOS:
        if grupo != grupo_atual:
            linhas.append(f"# ── {grupo} ──")
            grupo_atual = grupo
        linhas.append(f"{chave}={atuais.get(chave, '')}")
    if extras:
        linhas += ["", "# ── Outras (fora do formulário) ──"]
        linhas += [f"{k}={v}" for k, v in extras.items()]
    ENV_PATH.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def aplicar_config(dados: dict) -> None:
    """Grava só o que veio do formulário.

    Sem essa checagem, um campo que a página não renderiza chega como "" e apaga
    o que estava salvo (foi o que zerava WHATSAPP_CHAT_ID a cada "Salvar").
    """
    atuais = ler_env()
    filtrados = {}
    for chave, _, _, segredo, _ in CAMPOS:
        if chave not in dados:
            continue
        v = dados.get(chave, "")
        if segredo and not v and atuais.get(chave):
            continue
        filtrados[chave] = v
    salvar_env(filtrados)


# ── Processo do bot ───────────────────────────────────────────────────

class Processo:
    """Encapsula um subprocesso (o bot, ou uma ação) e guarda o log recente."""

    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.linhas: deque[str] = deque(maxlen=500)
        self.rotulo = ""

    def rodando(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def iniciar(self, args: list[str] | None, rotulo: str,
                cmd: list[str] | None = None, cwd=None) -> bool:
        if self.rodando():
            return False
        self.rotulo = rotulo
        self.linhas.append(f"▶ {rotulo}...")
        comando = list(cmd) if cmd else [sys.executable, "-m", "ofertas", *(args or [])]
        self.proc = subprocess.Popen(
            comando,
            cwd=str(cwd or BASE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._ler, daemon=True).start()
        return True

    def _ler(self):
        for linha in self.proc.stdout:
            self.linhas.append(linha.rstrip())
        cod = self.proc.wait()
        fim = "concluído ✓" if cod == 0 else f"terminou (código {cod})"
        self.linhas.append(f"■ {self.rotulo}: {fim}")

    def parar(self):
        if self.rodando():
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.linhas.append(f"■ {self.rotulo} parado.")


bot = Processo()
acao = Processo()
wa = Processo()
# a saída do servidor WhatsApp aparece no log "Bot ao vivo" do painel
wa.linhas = bot.linhas


def detectar_ids() -> dict:
    """Consulta o Telegram (getUpdates) e sugere owner id e chat id do canal."""
    token = ler_env().get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {"erro": "Preencha e salve o token do bot primeiro."}
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20)
        dados = r.json()
    except Exception as e:
        return {"erro": f"Não consegui falar com o Telegram: {e}"}
    if not dados.get("ok"):
        return {"erro": f"Telegram recusou o token: {dados.get('description', '?')}"}

    pessoas, canais = {}, {}
    for upd in dados.get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") == "private" and chat.get("id"):
            nome = " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
            pessoas[chat["id"]] = nome or chat.get("username") or str(chat["id"])
        elif chat.get("type") in ("channel", "supergroup", "group") and chat.get("id"):
            canais[chat["id"]] = chat.get("title") or str(chat["id"])
        fwd = (msg.get("forward_from_chat") or {})
        if fwd.get("type") == "channel" and fwd.get("id"):
            canais[fwd["id"]] = fwd.get("title") or str(fwd["id"])
    return {
        "pessoas": [{"id": i, "nome": n} for i, n in pessoas.items()],
        "canais": [{"id": i, "nome": n} for i, n in canais.items()],
        "vazio": not pessoas and not canais,
    }


def status() -> dict:
    env = ler_env()
    tem_navegador = bool(list((DATA_DIR / "pw-browsers").glob("chromium-*")))
    perfil = DATA_DIR / "ml_profile"
    tem_sessao_ml = perfil.exists() and any(perfil.iterdir())
    return {
        "bot_rodando": bot.rodando(),
        "acao_rodando": acao.rotulo if acao.rodando() else "",
        "preenchidos": {k: bool(env.get(k)) for k in CHAVES},
        "navegador": tem_navegador,
        "sessao_ml": tem_sessao_ml,
        "whatsapp": status_whatsapp(),
        "whatsapp_ativo": bool(config.fonte_whatsapp.get("ativa")
                               and env.get("WHATSAPP_CHAT_ID")),
        "pronto": bool(env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")
                       and env.get("TELEGRAM_OWNER_ID")),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _json(self, obj, code=200):
        corpo = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo_json(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            return {}

    def do_GET(self):
        rota = urlparse(self.path).path
        if rota == "/":
            corpo = PAGINA.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        elif rota == "/api/status":
            self._json(status())
        elif rota == "/api/config":
            env = ler_env()
            saida = {}
            for chave, _, _, segredo, _ in CAMPOS:
                saida[chave] = "" if (segredo and env.get(chave)) else env.get(chave, "")
                saida[chave + "__set"] = bool(env.get(chave))
            self._json(saida)
        elif rota == "/api/logs":
            fonte = urlparse(self.path).query
            alvo = acao if "acao" in fonte else bot
            self._json({"linhas": list(alvo.linhas)})
        elif rota == "/api/nichos":
            from .nichos import catalogo, ler_selecao
            self._json({"catalogo": catalogo(), "selecionados": ler_selecao()})
        else:
            self._json({"erro": "rota desconhecida"}, 404)

    def do_POST(self):
        rota = urlparse(self.path).path
        dados = self._corpo_json()
        if rota == "/api/config":
            aplicar_config(dados)
            self._json({"ok": True})
        elif rota == "/api/start":
            ok = bot.iniciar(["run"], "Bot")
            if ok:
                # em paralelo: garante o servidor WhatsApp para o 1º ciclo (+30s)
                threading.Thread(target=garantir_whatsapp_conectado,
                                 kwargs={"timeout": 90}, daemon=True).start()
            self._json({"ok": ok, "rodando": bot.rodando()})
        elif rota == "/api/stop":
            bot.parar()
            self._json({"ok": True, "rodando": bot.rodando()})
        elif rota == "/api/acao":
            nome = dados.get("nome", "")
            mapa = {
                "instalar-navegador": (["instalar-navegador"], "Instalando navegador"),
                "ml-login": (["ml-login"], "Login no Mercado Livre"),
                "testar-ml": (["testar", "ml"], "Testando Mercado Livre"),
                "testar-shopee": (["testar", "shopee"], "Testando Shopee"),
                "testar-amazon": (["testar", "amazon"], "Testando Amazon"),
            }
            if nome not in mapa:
                return self._json({"erro": "ação desconhecida"}, 400)
            if acao.rodando():
                return self._json({"erro": f"Já rodando: {acao.rotulo}"}, 409)
            args, rotulo = mapa[nome]
            acao.linhas.clear()
            acao.iniciar(args, rotulo)
            self._json({"ok": True})
        elif rota == "/api/detectar-ids":
            self._json(detectar_ids())
        elif rota == "/api/nichos":
            from .nichos import salvar_selecao
            salvar_selecao(dados.get("selecionados") or [])
            self._json({"ok": True})
        else:
            self._json({"erro": "rota desconhecida"}, 404)


def _auto_ligar() -> None:
    """Abre o painel e já deixa o bot postando (Telegram + WhatsApp + Facebook).

    Desligável com PAINEL_AUTO_START=0 no .env. Só liga se o Telegram estiver
    configurado; antes de subir o bot, espera o servidor WhatsApp conectar.
    """
    if not auto_start_ativo():
        bot.linhas.append("• Auto-start desligado (PAINEL_AUTO_START=0) — "
                          "clique em “Ligar bot” para começar.")
        return
    env = ler_env()
    if not (env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")):
        bot.linhas.append("• Auto-start: falta o token do bot ou o ID do canal — "
                          "preencha no formulário e clique em “Ligar bot”.")
        return
    print("  Auto-start: preparando o servidor WhatsApp e ligando o bot...",
          flush=True)
    garantir_whatsapp_conectado(timeout=90)
    if bot.rodando():
        return
    bot.linhas.append("▶ Auto-start: ligando o bot (o 1º ciclo sai em ~30s)...")
    bot.iniciar(["run"], "Bot")
    print("  Auto-start: bot no ar. Acompanhe o log na página.\n", flush=True)


def painel():
    url = f"http://{HOST}:{PORT}/"
    servidor = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"\n  Painel de controle aberto em {url}")
    print("  (deixe esta janela aberta; feche-a para desligar o painel)\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    threading.Thread(target=_auto_ligar, daemon=True).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        bot.parar()
        wa.parar()
        servidor.shutdown()