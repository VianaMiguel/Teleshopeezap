const express = require('express');
const cors = require('cors');
const { getClient, getReadyPromise, initialize, getIsReady } = require('./services/whatsapp');
const { enqueue } = require('./services/queue');
const config = require('./config');
const { extractUrls } = require('./utils/regex');
const { randomDelay } = require('./utils/delay');
const logger = require('./utils/logger');

const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb' }));

app.post('/send', async (req, res) => {
  try {
    const { text, image, targetGroups } = req.body;
    if (!text) return res.status(400).json({ error: 'Texto obrigatório' });

    const client = getClient();
    if (!getIsReady()) return res.status(503).json({ error: 'WhatsApp não conectado' });

    const groupIds = targetGroups || config.destGroups;
    const results = [];

    for (const groupId of groupIds) {
      try {
        const chat = await client.getChatById(groupId);
        // Canais (newsletter) não têm sendStateTyping/clearState
        if (config.typingDelayMin > 0 && typeof chat.sendStateTyping === 'function') {
          await chat.sendStateTyping();
          await randomDelay(config.typingDelayMin, config.typingDelayMax);
          if (typeof chat.clearState === 'function') await chat.clearState();
        }
        if (image) {
          try {
            const { MessageMedia } = require('whatsapp-web.js');
            const media = await MessageMedia.fromUrl(image, { unsafeMime: true });
            await chat.sendMessage(media, { caption: text });
          } catch (e) {
            logger.warn('Falha ao enviar imagem, enviando texto:', e.message);
            await chat.sendMessage(text);
          }
        } else {
          await chat.sendMessage(text);
        }
        results.push({ groupId, status: 'success' });
        logger.info(`[API] Mensagem enviada para ${groupId}`);
      } catch (e) {
        results.push({ groupId, status: 'error', error: e.message });
        logger.error(`[API] Falha em ${groupId}: ${e.message}`);
      }
      await randomDelay(500, 1500);
    }
    res.json({ success: true, results });
  } catch (e) {
    logger.error('[API] Erro:', e.message);
    res.status(500).json({ error: e.message });
  }
});

app.post('/send-quick', async (req, res) => {
  try {
    const { text, image, targetGroups } = req.body;
    const promo = { text, image, targetGroups, fromId: 'api', timestamp: new Date().toISOString() };
    const added = enqueue(promo);
    res.json({ success: true, queued: added });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/status', async (req, res) => {
  const connected = getIsReady();
  let groups = [];
  let chatCount = 0;
  let error = null;
  try {
    if (connected) {
      const client = getClient();
      const chats = await client.getChats();
      chatCount = chats.length;
      groups = chats.filter(c => c.isGroup).map(c => ({ name: c.name, id: c.id._serialized }));
    }
  } catch (e) {
    error = e.message;
    logger.error(`[API] /status getChats falhou: ${e.message}`);
  }
  res.json({ connected, chatCount, groups, error, queueSize: require('./services/queue').getQueueSize() });
});

app.get('/groups', async (req, res) => {
  if (!getIsReady()) return res.status(503).json({ error: 'Não conectado' });
  let groups = [];
  let chatCount = 0;
  let error = null;
  try {
    const client = getClient();
    const chats = await client.getChats();
    chatCount = chats.length;
    groups = chats.filter(c => c.isGroup).map(c => ({ name: c.name, id: c.id._serialized }));
  } catch (e) {
    error = e.message;
    logger.error(`[API] /groups getChats falhou: ${e.message}`);
    return res.status(500).json({ error: e.message });
  }
  res.json({ chatCount, groups, error, note: 'Se vazio, use GET /status ou list-groups.js' });
});

const PORT = (config.port || 4000);

// Sobe o servidor imediatamente (mesmo sem WhatsApp conectado),
// para que /status responda e o painel consiga monitorar.
const server = app.listen(PORT, () => {
  logger.info(`WhatsApp Server rodando na porta ${PORT}`);
  logger.info(`Endpoints:`);
  logger.info(`   POST /send      - Enviar mensagem imediata`);
  logger.info(`   POST /send-quick - Enviar pela fila`);
  logger.info(`   GET  /status    - Status`);
  logger.info(`   GET  /groups    - Listar grupos`);
});
server.unref();

getReadyPromise().then(() => {
  logger.info('Servidor pronto para receber envios (WhatsApp conectado).');
});

module.exports = app;
