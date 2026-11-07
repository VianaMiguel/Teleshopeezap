# Bot de Ofertas para Telegram 🔥

Bot que roda **no seu PC/servidor (Linux)**, garimpa promoções em **Mercado Livre, Shopee e Amazon** e posta no seu canal do Telegram com **os seus links de afiliado** — foto, preço "de/por", desconto e botão de compra. Tudo local, sem servidor nem mensalidade.

> ⚠️ Você precisa das **suas próprias** contas de afiliado (Mercado Livre, Amazon Associados, Shopee Afiliados). As comissões vão para quem configurar — cada pessoa usa as suas.

## Como funciona

Dois modos, no mesmo programa:

1. **Automático** — de tempos em tempos busca ofertas, filtra por desconto mínimo, evita repetir produto e posta as melhores no canal, já com o seu link de afiliado.
2. **Conversor** — você cola qualquer link de produto no privado do bot; ele monta a prévia do post com o seu link e você decide **✅ Postar** ou **🗑 Descartar**.

| Plataforma | De onde vêm as ofertas | Link de afiliado |
|---|---|---|
| Mercado Livre | Página de ofertas, filtrada por categoria | API do Linkbuilder do painel (login 1x); gera `meli.la/...` |
| Shopee | Open API oficial de afiliados (busca por palavra-chave) | A API já devolve o link com sua comissão |
| Amazon | Creators API; ou, enquanto sua conta não é elegível, ofertas por departamento | Link com a sua tag |

---

## Pré-requisitos

- **Google Chrome** instalado (usado para gerar os links do Mercado Livre). Em Debian/Ubuntu:
  ```bash
  wget -qO- https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
  sudo apt update && sudo apt install -y google-chrome-stable
  ```
  (Chromium também serve como alternativa.)
- **Node.js + npm** (para o servidor WhatsApp): https://nodejs.org/
- Uma conta no Telegram, um bot (@BotFather) e um canal.

---

## 🖥️ Jeito fácil: o painel gráfico (recomendado)

Dentro da pasta do projeto, no terminal:

```bash
bash painel.sh
```

Ele prepara o ambiente sozinho e abre um painel no seu navegador, onde você faz tudo com formulário e botões — sem terminal:

- preenche a configuração (token, IDs, tags) num formulário;
- descobre os IDs do Telegram com o botão **🔎 Detectar IDs**;
- instala o navegador e faz o **login do Mercado Livre** por botões;
- testa as fontes (ML/Shopee/Amazon) e vê as ofertas na hora;
- **liga/desliga o bot** e acompanha o log ao vivo.

Na primeira vez, se o `uv` não estiver instalado, o script instala e pede para você reabrir o terminal (ou rode `source $HOME/.local/bin/env`) — só seguir a tela. Antes, tenha em mãos: o **token** do bot (@BotFather), um **canal** com o bot como **administrador**, e suas **contas de afiliado**.

> Prefere o terminal? O passo a passo manual está logo abaixo (dá no mesmo).

---

## Passo a passo (pelo terminal)

### 0. Instalar o uv (uma vez)
O projeto usa o [uv](https://docs.astral.sh/uv/) (gerenciador de Python — ele baixa o Python sozinho, você não precisa instalar Python separado):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Depois **abra um terminal novo** (ou `source $HOME/.local/bin/env`) para o `uv` ficar no PATH.

### 1. Entrar na pasta do bot
```bash
cd caminho/do/bot-ofertas-telegram
```

### 2. Instalar as dependências
```bash
uv sync
uv run python -m ofertas instalar-navegador
```
(O segundo comando baixa o navegador que gera os links do Mercado Livre, ~120 MB.)

### 3. Criar o bot no Telegram
Fale com o [@BotFather](https://t.me/BotFather) → `/newbot` → escolha um nome e um @username → **copie o token** que ele te dá.

### 4. Criar o canal e colocar o bot como admin
Crie um canal no Telegram. Abra os detalhes do canal → **Administradores** → adicione o seu bot com permissão de **Publicar mensagens**.

### 5. Preencher o `.env`
```bash
cp .env.example .env
nano .env
```
Preencha (o que você não tiver ainda, deixe em branco e preencha depois):
- `TELEGRAM_BOT_TOKEN` — o token do passo 3.
- `TELEGRAM_OWNER_ID` e `TELEGRAM_CHAT_ID` — o jeito fácil: salve o token, rode o bot (passo 7), mande `/id` para ele no privado (dá o seu **owner id**) e encaminhe um post do canal para ele (dá o **chat id**). Depois cole os dois no `.env`. Ou use o botão **Detectar IDs** do painel.
- `ML_ETIQUETA` — a "Etiqueta em uso" que aparece no [Linkbuilder](https://www.mercadolivre.com.br/afiliados/linkbuilder) do painel de afiliados do Mercado Livre.
- `AMAZON_TAG` — sua tag do [Amazon Associados](https://associados.amazon.com.br) (algo como `seunome-20`).
- `AMAZON_CREDENTIAL_ID` / `SECRET` — opcional (Creators API). Sem isso o bot funciona mesmo assim.
- `SHOPEE_APP_ID` / `SHOPEE_APP_SECRET` — no [painel de afiliados Shopee](https://affiliate.shopee.com.br), menu **Abrir API** (a aprovação pode demorar alguns dias).

### 6. Login no Mercado Livre (uma vez só)
```bash
uv run python -m ofertas ml-login
```
Abre um Chrome normal. Faça login na sua conta de afiliado, confira que o Linkbuilder aparece logado e **feche o navegador**. A sessão fica salva e o bot passa a gerar os links sozinho.

> **Num servidor sem tela (VPS)?** O Chrome precisa de uma tela que **você veja** — veja a seção *VPS sem tela* abaixo (com `ssh -X` resolve em 1 minuto).

### 7. Conferir e rodar
```bash
uv run python -m ofertas check     # mostra o que ainda falta configurar
bash run.sh                        # liga bot + servidor WhatsApp (reinicia sozinho se cair)
```
Ou só o bot, sem WhatsApp: `uv run python -m ofertas run`.

Cole um link de produto no privado do bot para testar, ou espere o primeiro ciclo automático.

---

## Ajustes — `config.yaml`
Intervalo entre ciclos, quantos posts por vez, desconto mínimo, horário ativo e o **escopo do canal**. Por padrão o bot pega **ofertas de todas as categorias**. Para focar num nicho (tecnologia, moda, casa, pet…), preencha as listas de `categorias`/`departamentos`/`buscas` no `config.yaml` — há exemplos comentados dentro do arquivo. Edite e **reinicie o bot** (ele só lê a configuração ao iniciar).

## Deixar rodando sozinho
- `bash run.sh` reinicia o bot sozinho se cair. `horario_ativo` no `config.yaml` evita posts de madrugada (padrão 08:00–23:00).
- Servidor 24/7? Rode dentro de um `tmux`/`screen`, ou crie um serviço `systemd` apontando para `bash run.sh` (exemplo completo na seção *VPS sem tela*).

---

## 🖥️ VPS sem tela (Oracle, Hetzner etc.)

Servidores normalmente não têm monitor — e o Mercado Livre **exige uma janela de Chrome visível** (o reCAPTCHA recusa Chrome headless). O bot resolve isso sozinho, mas o **login manual** precisa de uma tela que você veja:

- **Coleta e links do ML (automáticos)**: `bash run.sh` e `bash painel.sh` detectam a falta de `DISPLAY` e re-executam sob **Xvfb** (tela virtual, invisível — suficiente para o bot). Instale uma vez:
  ```bash
  sudo apt install -y xvfb xauth
  ```
  Sem tela e sem Xvfb o bot **não trava**: só a fonte ML falha (com erro no log) e o ciclo continua com as demais fontes.
- **Login do ML (`ml-login`, uma vez)** — é manual, então escolha:
  1. **Recomendado — X11 forwarding**: conecte com `ssh -X usuario@servidor` e rode `uv run python -m ofertas ml-login` **nessa sessão**. No Windows, use um cliente com suporte a X11 (PuTTY; ou VcXsrv/Xming aberto junto com o OpenSSH).
  2. **VNC por túnel SSH** (sem abrir porta na nuvem):
     ```bash
     # no servidor
     sudo apt install -y xvfb x11vnc
     Xvfb :99 -screen 0 1280x800x24 &
     x11vnc -display :99 -localhost -forever -nopw &
     DISPLAY=:99 ML_LOGIN_VNC=1 uv run python -m ofertas ml-login

     # no seu PC: abra o túnel e conecte um visualizador VNC em localhost:5900
     ssh -L 5900:localhost:5900 usuario@servidor
     ```
- **O login vale só naquela máquina**: `data/ml_profile` guarda cookies criptografados pelo sistema — **não copie** a pasta de um PC para o outro; faça o login no próprio VPS.
- **Painel**: fica em `http://127.0.0.1:8481` (sem senha, por isso nunca é exposto à internet). Para usar de fora:
  ```bash
  ssh -L 8481:localhost:8481 usuario@servidor
  ```
  e abra `http://localhost:8481` no seu navegador.
- **WhatsApp**: o QR aparece no terminal; rodando em segundo plano, baixa com `scp usuario@servidor:whatsapp-server/qrcode.png .` e escaneie com o celular.
- **Serviço `systemd` (24/7)** — os scripts já resolvem o `PATH` do uv (`~/.local/bin`), mas garantam o Xvfb instalado (o `run.sh` o usa sozinho):
  ```ini
  [Unit]
  Description=Bot de ofertas Telegram
  After=network.target

  [Service]
  User=usuario
  WorkingDirectory=/home/usuario/bot-ofertas-telegram
  ExecStart=/bin/bash run.sh
  Restart=always
  RestartSec=15

  [Install]
  WantedBy=multi-user.target
  ```
- **ARM (Oracle Ampere)**: o Google Chrome oficial não tem build para ARM — instale o Chromium (`sudo apt install -y chromium`) e o bot usa ele automaticamente.

---

## Problemas comuns

**`uv: command not found`** logo após instalar
Reabra o terminal ou rode `source $HOME/.local/bin/env`.

**"Google Chrome não encontrado"** (login do Mercado Livre)
Instale o Google Chrome (ou Chromium) — veja *Pré-requisitos*. Em VPS ARM (Oracle Ampere) instale só o Chromium.

**`Missing X server or $DISPLAY` / "cannot open display"**
O servidor não tem tela e o Xvfb não está instalado: `sudo apt install -y xvfb xauth` e rode de novo com `bash run.sh` (ele cria a tela virtual sozinho).

**Login do ML diz "display virtual (Xvfb)"**
Esse display é invisível — o login manual precisa de `ssh -X` ou VNC. Veja a seção *VPS sem tela*.

**`npm: command not found`**
Instale o Node.js (https://nodejs.org/) — ele traz o npm junto.

**`testar ml` não acha ofertas / links param de sair**
Os sites mudam de layout de vez em quando. Refaça o `ml-login` (a sessão pode ter expirado) e, se persistir, os seletores ficam em `ofertas/sources/`.

---

## ⚖️ Uso responsável
- **Divulgação obrigatória**: os programas de afiliado (Amazon principalmente) exigem avisar que os links geram comissão. Coloque na descrição do canal algo como *"Contém links de afiliado; podemos receber comissão pelas compras, sem custo extra para você."*
- Respeite os termos de cada plataforma e não abuse da frequência de busca (os padrões do `config.yaml` já são comedidos).
- Os preços mudam a qualquer momento; o post reflete o preço no instante da coleta.

## Estrutura

```
bot-ofertas-telegram/
├── ofertas/
│   ├── main.py            # comandos (check, run, converter, postar, ml-login, testar, testar-whatsapp, testar-facebook)
│   ├── bot_interativo.py  # bot do Telegram (conversor + agendador) — posta no WhatsApp e Facebook
│   ├── pipeline.py        # coleta → filtros → gera links → posta (telegram + whatsapp + facebook)
│   ├── formatter.py       # visual do post
│   ├── db.py              # banco anti-repetição
│   ├── config.py          # lê .env + config.yaml
│   ├── telegram_poster.py  # módulo de poster para Telegram
│   ├── whatsapp_poster.py  # módulo que chama o servidor Node.js para WhatsApp
│   ├── facebook_poster.py  # módulo de poster para Facebook Graph API
│   └── sources/           # mercadolivre.py, shopee.py, amazon.py
├── whatsapp-server/       # Servidor Node.js com whatsapp-web.js (grupos e canais WhatsApp)
│   ├── src/
│   │   ├── index.js       # Entry point
│   │   ├── server.js      # Express com endpoints REST
│   │   ├── config/
│   │   ├── services/
│   │   │   ├── whatsapp.js  # Cliente WhatsApp Web
│   │   │   ├── queue.js     # Fila com anti-ban
│   │   │   └── listener.js  # Escuta grupos/canais WhatsApp
│   │   └── utils/
│   ├── package.json
│   └── run.sh
├── run.sh                 # Inicia bot + servidor WhatsApp juntos
├── run-whatsapp.sh        # Inicia só o servidor WhatsApp
├── painel.sh              # Painel gráfico
└── config.yaml
```

### Instalação do WhatsApp

1. Certifique-se de ter **Node.js** instalado ([link](https://nodejs.org/))
2. Na pasta `whatsapp-server`, execute:
   ```bash
   cd whatsapp-server
   npm install
   npm start
   ```
   (Ou, na raiz do projeto: `bash run-whatsapp.sh`)
3. Escaneie o **QR Code** que aparece no terminal (ou em `whatsapp-server/qrcode.png`) com o WhatsApp do celular
4. O servidor ficará rodando na porta **4000**
5. Configure o `WHATSAPP_CHAT_ID` no `.env` com o ID do grupo/canal (use `npm run list-groups` no whatsapp-server para descobrir — ou `uv run python -m ofertas listar-grupos-whatsapp`)
6. No `config.yaml`, coloque `whatsapp.ativa: true`
7. Inicie o bot normalmente (`bash run.sh` já inicia o servidor WhatsApp automaticamente)

> **Nota:** O servidor WhatsApp precisa estar rodando antes de iniciar o bot. O `run.sh` (e o `painel.sh`) já faz isso automaticamente.
