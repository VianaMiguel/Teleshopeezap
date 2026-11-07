import logging

from .formatter import montar_caption
from .models import Oferta

log = logging.getLogger("ofertas.poster.facebook")


def montar_mensagem_facebook(o: Oferta) -> tuple[str, bool]:
    """Monta a mensagem para Facebook. Retorna (texto, tem_imagem)."""
    caption = montar_caption(o)
    
    # Facebook limita captions a 63k caracteres
    if len(caption) > 63000:
        log.warning("Caption muito longa para Facebook (%d chars), truncando", len(caption))
        caption = caption[:63000] + "\n...\n(Mensagem truncada)"
    
    return caption, bool(o.imagem)


async def postar_oferta_facebook(oferta: Oferta, page_id: str, 
                                 access_token: str, api_version: str = "v18.0") -> dict:
    """Posta uma oferta em uma página do Facebook.
    
    Retorna dict com {sucesso: bool, mensagem: str, post_id: str | None}
    """
    try:
        import requests
        
        texto, tem_imagem = montar_mensagem_facebook(oferta)
        
        # API endpoint do Facebook Graph
        url = f"https://graph.facebook.com/{api_version}/{page_id}/feed"
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        # Preparar corpo da publicação
        dados = {
            "message": texto,
            "link": oferta.url_afiliado,
            "access_token": access_token
        }
        
        if tem_imagem and oferta.imagem:
            # Para posts com imagem, precisamos fazer upload primeiro
            upload_url = f"https://graph.facebook.com/{api_version}/upload"
            
            # Fazer upload da imagem
            params = {
                "access_token": access_token,
                "source": "url"
            }
            
            upload_response = requests.post(
                upload_url,
                params=params,
                json={"url": oferta.imagem},
                timeout=30
            )
            
            if upload_response.status_code == 200:
                imagem_id = upload_response.json().get("id")
                if imagem_id:
                    dados["attached_media"] = f'{{"media":{{"id":"{imagem_id}"}}}}'
        
        response = requests.post(url, headers=headers, json=dados, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "sucesso": True,
                "mensagem": "Postada com sucesso",
                "post_id": data.get("id")
            }
        else:
            erro = response.text
            if response.status_code == 400:
                erro = "Dados inválidos"
            elif response.status_code == 401:
                erro = "Token de acesso inválido"
            elif response.status_code == 403:
                erro = "Sem permissão para publicar nesta página"
            elif response.status_code == 500:
                erro = "Erro interno do Facebook"
            
            return {
                "sucesso": False,
                "mensagem": f"Erro {response.status_code}: {erro}",
                "post_id": None
            }
            
    except Exception as e:
        return {
            "sucesso": False,
            "mensagem": f"Exceção: {str(e)}",
            "post_id": None
        }


async def testar_conexao_facebook(page_id: str, access_token: str, api_version: str = "v18.0") -> dict:
    """Testa a conexão com o Facebook Graph API."""
    try:
        import requests
        
        url = f"https://graph.facebook.com/{api_version}/{page_id}"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return {
                "sucesso": True,
                "mensagem": "Conexão OK",
                "pagina_info": response.json()
            }
        else:
            return {
                "sucesso": False,
                "mensagem": f"Erro {response.status_code}: {response.text}",
                "pagina_info": None
            }
            
    except Exception as e:
        return {
            "sucesso": False,
            "mensagem": f"Exceção: {str(e)}",
            "pagina_info": None
        }