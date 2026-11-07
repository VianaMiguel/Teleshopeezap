const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode');
const path = require('path');
const fs = require('fs');
const config = require('../config');
const logger = require('../utils/logger');

// WhatsApp Web recarrega a página logo após o load (atualização de bundle),
// o que mata a injeção com "Execution context was destroyed".
// Retry na injeção resolve a corrida de timing.
const _injectOriginal = Client.prototype.inject;
Client.prototype.inject = async function (...args) {
  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      return await _injectOriginal.apply(this, args);
    } catch (e) {
      const msg = String(e && e.message || e);
      if (msg.includes('Execution context was destroyed') || msg.includes('Cannot find context')) {
        logger.warn(`[Inject] Página navegou durante injeção (tentativa ${attempt}/5) — tentando de novo...`);
        await new Promise(r => setTimeout(r, 3000));
        continue;
      }
      throw e;
    }
  }
  return _injectOriginal.apply(this, args);
};

// Retry também em TODOS os page.evaluate — a navegação mata o encadeamento
// pós-authenticated (ClientInfo, listeners) e o 'ready' nunca dispara.
try {
  const { Page } = require('puppeteer-core');
  const _evaluate = Page.prototype.evaluate;
  Page.prototype.evaluate = async function (...args) {
    for (let attempt = 1; attempt <= 4; attempt++) {
      try {
        return await _evaluate.apply(this, args);
      } catch (e) {
        const msg = String(e && e.message || e);
        if ((msg.includes('Execution context was destroyed') || msg.includes('Cannot find context')) && attempt < 4) {
          await new Promise(r => setTimeout(r, 2000));
          continue;
        }
        throw e;
      }
    }
  };
} catch (_) {}

// attachEventListeners depende de módulos lazy do WhatsApp Web; se o chunk
// ainda não carregou, evaluate falha. Retry resolve.
const _attachOriginal = Client.prototype.attachEventListeners;
Client.prototype.attachEventListeners = async function (...args) {
  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      return await _attachOriginal.apply(this, args);
    } catch (e) {
      const msg = String(e && e.message || e);
      if (attempt < 5) {
        logger.warn(`[Listeners] Falha ao anexar listeners (tentativa ${attempt}/5): ${msg.slice(0, 80)}`);
        await new Promise(r => setTimeout(r, 4000));
        continue;
      }
      throw e;
    }
  }
};

const BROWSER_PATH = findBrowserPath();

function findBrowserPath() {
  const paths = [];
  if (process.env.LOCALAPPDATA) {
    paths.push(path.join(process.env.LOCALAPPDATA, 'puppeteer'));
  }
  paths.push(
    path.join(__dirname, '../../node_modules/puppeteer/.local-chromium'),
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/snap/bin/chromium',
  );
  for (const p of paths) {
    try {
      // precisa ser um ARQUIVO (executablePath aponta para o binário,
      // não para uma pasta)
      if (fs.existsSync(p) && fs.statSync(p).isFile()) return p;
    } catch (_) {}
  }
  // null = puppeteer usa o navegador que ele mesmo baixou (~/.cache/puppeteer)
  return null;
}

const puppeteerConfig = {
  headless: true,
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-web-security',
    '--disable-features=TranslateUI',
    '--disable-extensions',
  ],
};
if (BROWSER_PATH) {
  puppeteerConfig.executablePath = BROWSER_PATH;
  logger.info(`Caminho do navegador: ${BROWSER_PATH}`);
}

let client = null;
let cachedGroups = [];
let readyResolved = false;
let readyResolveFn = null;
const readyPromise = new Promise((resolve) => {
  readyResolveFn = resolve;
});

// Abre um arquivo com o aplicativo padrão do sistema (Windows/macOS/Linux).
function abrirArquivo(p) {
  try {
    const { exec } = require('child_process');
    const cmd = process.platform === 'win32' ? `start "" "${p}"`
      : process.platform === 'darwin' ? `open "${p}"`
      : `xdg-open "${p}"`;
    exec(cmd, () => {});
  } catch (_) {}
}

function saveQr(qr) {
  if (!config.displayQR) return;
  logger.info('========================================');
  logger.info('QR CODE gerado! Abra o arquivo para escanear:');
  logger.info(`→ qrcode.png`);
  logger.info('========================================');
  console.log('\n>>> QR CODE disponivel em qrcode.png\n');
  try {
    const qrPath = path.resolve(__dirname, '../../qrcode.png');
    qrcode.toFile(qrPath, qr, { type: 'png', width: 400, margin: 3 }).catch(() => {});
    abrirArquivo(qrPath);
  } catch (_) {}
}

function createClient() {
  const c = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: puppeteerConfig,
  });

  c.on('error', (err) => {
    logger.error('[Client Error]', err.message);
  });

  c.on('qr', saveQr);

  c.on('authenticated', () => {
    logger.info('Autenticação bem-sucedida! Sessão salva.');
  });

  c.on('disconnected', (reason) => {
    logger.warn(`Bot desconectado: ${reason}`);
  });

  c.on('auth_failure', (msg) => {
    logger.error('Falha na autenticação:', msg);
  });

  c.on('ready', async () => {
    if (readyResolved) return;
    logger.info('✅ WhatsApp conectado!');
    readyResolved = true;
    readyResolveFn(c);
    try {
      // groupMetadata.update() interno quebra com "IDBObjectStore: No key" na
      // versão atual do WhatsApp Web — versão segura pula chats problemáticos.
      await c.pupPage.evaluate(() => {
        if (window.WWebJS && !window.WWebJS._getChatsPatched) {
          window.WWebJS._getChatsPatched = true;
          window.WWebJS.getChats = async () => {
            const chats = window.require('WAWebCollections').Chat.getModelsArray();
            const out = [];
            for (const chat of chats) {
              try {
                const m = await window.WWebJS.getChatModel(chat);
                if (m) out.push(m);
              } catch (e) {
                try {
                  const model = chat.serialize();
                  model.isGroup = !!chat.groupMetadata;
                  if (chat.formattedTitle) model.formattedTitle = chat.formattedTitle;
                  out.push(model);
                } catch (_) {}
              }
            }
            return out;
          };
          window.WWebJS.getChannels = async () => {
            try {
              const col = window.require('WAWebCollections').WAWebNewsletterCollection;
              const channels = col.getModelsArray();
              const out = [];
              for (const ch of channels || []) {
                try {
                  const m = await window.WWebJS.getChatModel(ch, { isChannel: true });
                  if (m) out.push(m);
                } catch (e) {
                  try {
                    const model = ch.serialize();
                    model.isChannel = true;
                    if (ch.name) model.name = ch.name;
                    out.push(model);
                  } catch (_) {}
                }
              }
              return out;
            } catch (_) { return []; }
          };
          // update() das coleções internas lança "IDBObjectStore: No key" na
          // versão atual do WA Web — engole o erro (mantém metadata em memória).
          try {
            const cols = window.require('WAWebCollections');
            const names = ['GroupMetadata', 'WAWebGroupMetadataCollection',
              'NewsletterMetadataCollection', 'WAWebNewsletterMetadataCollection'];
            for (const n of names) {
              const coll = cols[n];
              if (coll && typeof coll.update === 'function' && !coll.update.__wrapped) {
                const orig = coll.update.bind(coll);
                const wrapped = async (...args) => {
                  try { return await orig(...args); } catch (_) { return undefined; }
                };
                wrapped.__wrapped = true;
                coll.update = wrapped;
              }
            }
          } catch (_) {}
          // Fallback do getChatModel: se ainda falhar, serializa sem metadata
          const origGCM = window.WWebJS.getChatModel;
          if (origGCM && !origGCM.__wrapped) {
            const wrappedGCM = async (chat, opts) => {
              try { return await origGCM(chat, opts); } catch (e) {
                try {
                  const model = chat.serialize();
                  model.isGroup = !!chat.groupMetadata;
                  if (opts && opts.isChannel) model.isChannel = true;
                  if (chat.formattedTitle) model.formattedTitle = chat.formattedTitle;
                  if (chat.name && !model.name) model.name = chat.name;
                  model.lastMessage = null;
                  return model;
                } catch (_) { return null; }
              }
            };
            wrappedGCM.__wrapped = true;
            window.WWebJS.getChatModel = wrappedGCM;
          }
          // Canais: chat.msgs nem sempre expõe .add() nesta versão do WA Web
          const origSend = window.WWebJS.sendMessage;
          if (origSend && !origSend.__wrapped) {
            const wrappedSend = async (chat, content, options) => {
              try {
                if (chat) {
                  if (!chat.msgs) {
                    try { chat.msgs = { add() {}, remove() {} }; } catch (_) {}
                  } else if (typeof chat.msgs.add !== 'function') {
                    try {
                      Object.defineProperty(chat.msgs, 'add', {
                        value() {}, configurable: true, writable: true,
                      });
                    } catch (_) {}
                  }
                }
              } catch (_) {}
              return origSend(chat, content, options);
            };
            wrappedSend.__wrapped = true;
            window.WWebJS.sendMessage = wrappedSend;
          }
        }
      }).catch(() => {});
      // A lista de chats demora alguns segundos após o 'ready' — espera e retenta
      for (let tentativa = 1; tentativa <= 5; tentativa++) {
        await new Promise(r => setTimeout(r, 6000));
        const chats = await c.getChats();
        cachedGroups = chats
          .filter(ch => ch.isGroup || ch.isChannel)
          .map(ch => ({ name: ch.name || ch.formattedTitle, id: ch.id._serialized, isChannel: !!ch.isChannel }));
        if (cachedGroups.length > 0 || tentativa === 5) {
          logger.info(`[Cache] ${cachedGroups.length} grupo(s)/canal(is) carregado(s).`);
          break;
        }
        logger.info(`[Cache] Lista ainda vazia (tentativa ${tentativa}/5) — aguardando...`);
      }
    } catch (e) {
      logger.warn('[Cache] Falha ao carregar grupos:', String(e && e.message || e).split('\n')[0] || '(erro sem mensagem)');
    }
  });

  return c;
}

function getClient() {
  if (!client) client = createClient();
  return client;
}

function getReadyPromise() {
  return readyPromise;
}

const READY_TIMEOUT_MS = 90000;
const MAX_ATTEMPTS = 3;

async function initialize() {
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    client = createClient();
    logger.info(`[Init] Iniciando WhatsApp (tentativa ${attempt}/${MAX_ATTEMPTS})...`);

    const initPromise = client.initialize().then(() => null).catch(err => {
      logger.error('[INIT ERROR]', String(err && (err.stack || err.message) || err).split('\n').slice(0, 3).join(' | '));
      return 'init-error';
    });

    const result = await Promise.race([
      readyPromise.then(() => 'ready'),
      initPromise.then(v => v === 'init-error' ? 'init-error' : null),
      new Promise(r => setTimeout(() => r('timeout'), READY_TIMEOUT_MS)),
    ]);

    if (result === 'ready') return;
    if (result === null) {
      // initialize() terminou, mas ready ainda não veio — espera o restante do timeout
      const late = await Promise.race([
        readyPromise.then(() => 'ready'),
        new Promise(r => setTimeout(() => r('timeout'), READY_TIMEOUT_MS)),
      ]);
      if (late === 'ready') return;
    }

    logger.warn(`[Init] Não ficou pronto (${result}) — destruindo e tentando de novo...`);
    try { await client.destroy(); } catch (_) {}
    readyResolved = false;

    if (attempt === MAX_ATTEMPTS) {
      throw new Error(`WhatsApp não conectou após ${MAX_ATTEMPTS} tentativas`);
    }
    await new Promise(r => setTimeout(r, 5000));
  }
}

function getCachedGroups() {
  return cachedGroups;
}

function getIsReady() {
  return readyResolved;
}

module.exports = { getClient, getReadyPromise, initialize, getCachedGroups, getIsReady };
