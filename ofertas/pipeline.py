import asyncio
import logging
import re

from telegram import Bot

from . import db
from .config import config, dentro_do_horario
from .models import Oferta
from .sources import amazon, mercadolivre, shopee
from .telegram_poster import postar_oferta
from .whatsapp_poster import esperar_whatsapp_pronto, postar_oferta_whatsapp
from .facebook_poster import postar_oferta_facebook

log = logging.getLogger("ofertas.pipeline")


def coletar() -> list[Oferta]:
    """Busca ofertas nas fontes automáticas ativas (sem link de afiliado ainda, no caso do ML)."""
    todas: list[Oferta] = []

    if config.fonte_shopee.get("ativa"):
        if config.shopee_app_id and config.shopee_app_secret:
            try:
                todas += shopee.buscar_ofertas(int(config.fonte_shopee.get("limite", 30)))
            except Exception as e:
                log.error("Shopee: %s", e)
        else:
            log.warning("Shopee ativa no config.yaml mas sem credenciais no .env — pulando")

    if config.fonte_amazon.get("ativa"):
        if config.amazon_tag:
            try:
                todas += amazon.buscar_ofertas()
            except Exception as e:
                log.error("Amazon: %s", e)
        else:
            log.warning("Amazon ativa no config.yaml mas sem AMAZON_TAG no .env — pulando")

    if config.fonte_ml.get("ativa"):
        if mercadolivre.tem_sessao():
            try:
                todas += mercadolivre.buscar_ofertas()
            except Exception as e:
                log.error("Mercado Livre: %s", e)
        else:
            log.warning("Mercado Livre ativo mas sem sessão de afiliado — rode: uv run python -m ofertas ml-login")

    return todas


def filtrar(ofertas: list[Oferta]) -> list[Oferta]:
    aprovadas = []
    for o in ofertas:
        if not o.titulo:
            continue
        if db.ja_postada(o.uid, config.nao_repetir_dias):
            continue
        if config.desconto_minimo and (o.desconto or 0) < config.desconto_minimo:
            continue
        if o.preco is not None:
            if config.preco_minimo and o.preco < config.preco_minimo:
                continue
            if config.preco_maximo and o.preco > config.preco_maximo:
                continue
        titulo = o.titulo.lower()
        if any(p in titulo for p in config.palavras_bloqueadas):
            continue
        aprovadas.append(o)
    return aprovadas


def _chave_similar(titulo: str) -> str:
    """Variações do mesmo produto (cor, tamanho) costumam repetir as primeiras palavras."""
    return " ".join(re.findall(r"\w+", titulo.lower())[:5])


def escolher(ofertas: list[Oferta], n: int) -> list[Oferta]:
    """Top N por desconto, alternando plataformas e pulando variações do mesmo produto."""
    filas: dict[str, list[Oferta]] = {}
    for o in sorted(ofertas, key=lambda o: o.desconto or 0, reverse=True):
        filas.setdefault(o.plataforma, []).append(o)
    ordem = sorted(filas.values(), key=lambda f: f[0].desconto or 0, reverse=True)
    escolhidas: list[Oferta] = []
    vistas: set[str] = set()
    while len(escolhidas) < n and any(ordem):
        for fila in ordem:
            while fila:
                o = fila.pop(0)
                chave = _chave_similar(o.titulo)
                if chave not in vistas:
                    vistas.add(chave)
                    escolhidas.append(o)
                    break
            if len(escolhidas) >= n:
                break
    return escolhidas


async def avisar_dono(bot: Bot, texto: str) -> None:
    """Manda um aviso no privado do dono (se configurado) — para operação sem supervisão."""
    if not config.owner_id:
        return
    try:
        await bot.send_message(config.owner_id, texto)
    except Exception as e:
        log.warning("Não consegui avisar o dono: %s", e)


async def executar_ciclo(bot: Bot) -> int:
    """Um ciclo completo: coletar -> filtrar -> escolher -> gerar links -> postar. Retorna nº de posts."""
    if not dentro_do_horario():
        log.info("Fora do horário ativo (%s) — ciclo pulado", config.horario_ativo)
        return 0

    # O servidor WhatsApp costuma subir junto com o painel; se ainda não estiver
    # conectado, espera um pouco antes de postar — senão a oferta vai só pro
    # Telegram e o grupo do WhatsApp perde (fica marcada como postada por 7 dias).
    if config.fonte_whatsapp.get("ativa") and config.whatsapp_chat_id:
        if not await esperar_whatsapp_pronto(timeout=25):
            log.warning("WhatsApp não conectado — este ciclo posta só no Telegram/Facebook")

    brutas = await asyncio.to_thread(coletar)
    boas = filtrar(brutas)
    escolhidas = escolher(boas, config.max_posts_por_ciclo)

    # Mercado Livre: gerar link de afiliado só das escolhidas (linkbuilder é caro)
    ml_pendentes = [o for o in escolhidas if o.plataforma == "mercadolivre" and not o.url_afiliado]
    if ml_pendentes:
        try:
            await asyncio.to_thread(mercadolivre.gerar_links_afiliado, ml_pendentes)
        except Exception as e:
            log.error("Linkbuilder ML falhou: %s", e)
            if "Sessão" in str(e):
                await avisar_dono(bot, f"⚠️ Mercado Livre parou de gerar links: {e}")

    postadas = 0
    for o in escolhidas:
        if not o.url_afiliado:
            log.warning("Sem link de afiliado, pulando: %s", o.titulo[:60])
            continue
        
        # Telegram
        try:
            await postar_oferta(bot, o, config.chat_id)
            log.info("Postada no Telegram: %s", o.titulo[:60])
        except Exception as e:
            log.error("Falha ao postar no Telegram '%s': %s", o.titulo[:60], e)
            continue
        
        # WhatsApp (se ativado)
        if config.fonte_whatsapp.get("ativa") and config.whatsapp_chat_id:
            try:
                resultado = await postar_oferta_whatsapp(
                    o,
                    config.whatsapp_chat_id
                )
                if resultado["sucesso"]:
                    log.info("Postada no WhatsApp: %s", o.titulo[:60])
                else:
                    log.warning("Falha no WhatsApp '%s': %s", o.titulo[:60], resultado["mensagem"])
            except Exception as e:
                log.error("Exceção no WhatsApp '%s': %s", o.titulo[:60], e)
        
        # Facebook (se ativado)
        if config.fonte_facebook.get("ativa") and config.facebook_access_token and config.facebook_page_id:
            try:
                resultado = await postar_oferta_facebook(
                    o,
                    config.facebook_page_id,
                    config.facebook_access_token
                )
                if resultado["sucesso"]:
                    log.info("Postada no Facebook: %s", o.titulo[:60])
                else:
                    log.warning("Falha no Facebook '%s': %s", o.titulo[:60], resultado["mensagem"])
            except Exception as e:
                log.error("Exceção no Facebook '%s': %s", o.titulo[:60], e)
        
        db.registrar(o)
        postadas += 1
        if o is not escolhidas[-1]:
            await asyncio.sleep(config.espacamento_segundos)

    log.info("Ciclo: %d coletadas, %d aprovadas, %d postadas", len(brutas), len(boas), postadas)
    return postadas
