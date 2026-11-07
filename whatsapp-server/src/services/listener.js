const { getClient, getReadyPromise } = require('./whatsapp');
const { enqueue } = require('./queue');
const { extractUrls } = require('../utils/regex');
const { randomDelay } = require('../utils/delay');
const config = require('../config');
const logger = require('../utils/logger');

function registerListener() {
  getReadyPromise().then(async (client) => {
    const { Client } = require('whatsapp-web.js');

    client.on('message', async (message) => {
      try {
        const fromId = message.from || '';
        const isGroup = fromId.endsWith('@g.us');
        const isChannel = fromId.endsWith('@newsletter');
        if (!isGroup && !isChannel) return;
        if (config.sourceGroups.length > 0 && !config.sourceGroups.includes(fromId)) return;
        if (!message.body || message.body.trim() === '') return;

        let sourceName = fromId;
        try { sourceName = (await message.getChat()).name || fromId; } catch (_) {}

        logger.info(`[Listener] Mensagem de: ${sourceName} (${isChannel ? 'canal' : 'grupo'})`);

        const { urls } = extractUrls(message.body);
        if (!urls || urls.length === 0) return;

        let imageUrl = null;
        if (message.hasMedia) {
          try { imageUrl = await message.downloadMedia(); } catch (_) {}
        }

        const promo = {
          text: message.body,
          image: imageUrl,
          fromId,
          sourceGroup: sourceName,
          urls,
          timestamp: new Date().toISOString(),
        };

        enqueue(promo);
      } catch (e) {
        logger.error('[Listener] Erro:', e.message);
      }
    });

    logger.info('[Listener] Registrado com sucesso.');
  }).catch(e => logger.error('[Listener] Erro ao registrar:', e.message));
}

module.exports = { registerListener };
