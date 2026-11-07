import asyncio
import logging
import re

from .formatter import montar_caption
from .models import Oferta

log = logging.getLogger("ofertas.poster.whatsapp")

WHATSAPP_SERVER_URL = "http://localhost:4000"


def html_para_whatsapp(texto: str) -> str:
    """Converte o HTML do formatter (Telegram) para a formatação do WhatsApp.

    Telegram: <b>negrito</b>, <i>itálico</i>, <s>riscado</s>
    WhatsApp: *negrito*, _itálico_, ~riscado~
    """
    texto = re.sub(r"<b>(.*?)</b>", r"*\1*", texto, flags=re.DOTALL)
    texto = re.sub(r"<i>(.*?)</i>", r"_\1_", texto, flags=re.DOTALL)
    texto = re.sub(r"<s>(.*?)</s>", r"~\1~", texto, flags=re.DOTALL)
    texto = re.sub(r"</?(?:strong|em|u)>", "", texto)
    texto = re.sub(r"<[^>]+>", "", texto)  # remove qualquer outra tag restante
    return texto


def montar_mensagem_whatsapp(o: Oferta) -> str:
    caption = html_para_whatsapp(montar_caption(o))
    if o.url_afiliado:
        caption += f"\n\n🔗 {o.url_afiliado}"
    if len(caption) > 65000:
        log.warning("Caption muito longa para WhatsApp (%d chars), truncando", len(caption))
        caption = caption[:65000] + "\n...\n(Mensagem truncada)"
    return caption


def montar_mensagem_whatsapp_texto(texto: str) -> str:
    texto = html_para_whatsapp(texto)
    if len(texto) > 65000:
        log.warning("Texto muito longo para WhatsApp (%d chars), truncando", len(texto))
        return texto[:65000] + "\n...\n(Mensagem truncada)"
    return texto


def _enviar(payload: dict) -> dict:
    """Bloco síncrono (requests) — roda em thread separada para não travar o bot."""
    import requests

    response = requests.post(
        f"{WHATSAPP_SERVER_URL}/send",
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        return {"sucesso": False, "mensagem": f"Erro {response.status_code}: {response.text}"}

    data = response.json()
    resultados = data.get("results") or []
    falhas = [r for r in resultados if r.get("status") != "success"]
    if falhas:
        return {
            "sucesso": False,
            "mensagem": "; ".join(f"{r.get('groupId')}: {r.get('error')}" for r in falhas),
        }
    if not data.get("success"):
        return {"sucesso": False, "mensagem": str(data)}
    return {"sucesso": True, "mensagem": "Postada com sucesso"}


async def postar_oferta_whatsapp(oferta: Oferta, chat_id: str,
                                  access_token: str = None) -> dict:
    """Posta uma oferta no WhatsApp via servidor Node.js local.

    Retorna dict com {sucesso: bool, mensagem: str, id_mensagem: str | None}
    """
    try:
        payload = {
            "text": montar_mensagem_whatsapp(oferta),
            "targetGroups": [chat_id],
        }

        if oferta.imagem:
            payload["image"] = oferta.imagem

        resultado = await asyncio.to_thread(_enviar, payload)
        resultado["id_mensagem"] = None
        return resultado

    except OSError:
        return {
            "sucesso": False,
            "mensagem": "Servidor WhatsApp não está rodando (npm run start no whatsapp-server)",
            "id_mensagem": None
        }
    except Exception as e:
        return {
            "sucesso": False,
            "mensagem": f"Exceção: {str(e)}",
            "id_mensagem": None
        }


async def postar_oferta_whatsapp_texto(texto: str, chat_id: str,
                                         target_groups: list = None) -> dict:
    """Posta um texto genérico no WhatsApp via servidor Node.js local.

    Retorna dict com {sucesso: bool, mensagem: str}
    """
    try:
        payload = {
            "text": montar_mensagem_whatsapp_texto(texto),
            "targetGroups": target_groups or [chat_id],
        }

        return await asyncio.to_thread(_enviar, payload)

    except OSError:
        return {
            "sucesso": False,
            "mensagem": "Servidor WhatsApp não está rodando"
        }
    except Exception as e:
        return {"sucesso": False, "mensagem": f"Exceção: {str(e)}"}


async def testar_conexao_whatsapp(chat_id: str, _access_token: str = None) -> dict:
    """Testa a conexão com o servidor WhatsApp local."""
    try:
        import requests
        response = requests.get(f"{WHATSAPP_SERVER_URL}/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "sucesso": data.get("connected", False),
                "mensagem": "Conectado" if data.get("connected") else "Não conectado",
                "chat_info": data
            }
        else:
            return {
                "sucesso": False,
                "mensagem": f"Servidor respondeu {response.status_code}",
                "chat_info": None
            }
    except requests.ConnectionError:
        return {
            "sucesso": False,
            "mensagem": "Servidor WhatsApp não está rodando",
            "chat_info": None
        }
    except Exception as e:
        return {
            "sucesso": False,
            "mensagem": f"Exceção: {str(e)}",
            "chat_info": None
        }


async def esperar_whatsapp_pronto(timeout: int = 25) -> bool:
    """Espera até `timeout` segundos o servidor local ficar conectado.

    Usado no início de cada ciclo: se o servidor demorou a subir (ou o painel
    acabou de abrir), a oferta não acaba postada só no Telegram e perdida no
    WhatsApp.
    """
    import time
    fim = time.monotonic() + timeout
    while True:
        st = await testar_conexao_whatsapp("")
        if st["sucesso"]:
            return True
        if time.monotonic() >= fim:
            return False
        await asyncio.sleep(2)