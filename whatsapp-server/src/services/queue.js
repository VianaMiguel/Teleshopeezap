const fs = require('fs');
const path = require('path');
const { Client, MessageMedia } = require('whatsapp-web.js');
const config = require('../config');
const logger = require('../utils/logger');
const { randomDelay, formatMs } = require('../utils/delay');
const { getCachedGroups } = require('./whatsapp');

const queue = config.loadedQueue || [];
let isProcessing = false;
const QUEUE_FILE = path.join(__dirname, '../../.queue_backup.json');
const processedHashes = new Map();
const HASH_RETENTION_MS = 30 * 60 * 1000;

function saveQueueToDisk() {
  try {
    if (queue.length > 0) {
      fs.writeFileSync(QUEUE_FILE, JSON.stringify(queue, null, 2), 'utf-8');
    }
  } catch (e) {
    logger.error('Erro ao salvar backup da fila:', e.message);
  }
}

function hashMessage(text, fromId) {
  return require('crypto').createHash('md5').update(`${text}|${fromId}`).digest('hex');
}

function isDuplicate(messageHash) {
  const now = Date.now();
  for (const [hash, ts] of processedHashes.entries()) {
    if (now - ts > HASH_RETENTION_MS) processedHashes.delete(hash);
  }
  return processedHashes.has(messageHash);
}

function markProcessed(messageHash) {
  processedHashes.set(messageHash, Date.now());
}

async function sendToGroup(client, groupId, text, imageUrl) {
  const MAX_RETRIES = 3;
  let lastError;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const chat = await client.getChatById(groupId);

      // Canais (newsletter) não têm sendStateTyping/clearState
      if (config.typingDelayMin > 0 && typeof chat.sendStateTyping === 'function') {
        await chat.sendStateTyping();
        const typingTime = await randomDelay(config.typingDelayMin, config.typingDelayMax);
        logger.debug(`[Fila] Digitando por ${formatMs(typingTime)}...`);
        if (typeof chat.clearState === 'function') await chat.clearState();
      }

      if (imageUrl) {
        try {
          const media = await MessageMedia.fromUrl(imageUrl, { unsafeMime: true });
          await chat.sendMessage(media, { caption: text });
        } catch (e) {
          logger.warn('Falha ao enviar imagem, enviando apenas texto:', e.message);
          await chat.sendMessage(text);
        }
      } else {
        await chat.sendMessage(text);
      }

      return { success: true };
    } catch (e) {
      lastError = e;
      logger.error(`[Fila] ❌ Erro ao enviar para ${groupId} (tentativa ${attempt}/${MAX_RETRIES}): ${e.message}`);

      if (attempt < MAX_RETRIES) {
        // Backoff exponencial com jitter: ~5s, ~20s
        const backoffMs = Math.pow(attempt, 2) * 5000;
        const waitMs = await randomDelay(backoffMs, backoffMs + 5000);
        logger.info(`[Fila] Aguardando ${formatMs(waitMs)} antes do retry...`);
      }
    }
  }

  throw lastError;
}

async function processQueue(client) {
  if (isProcessing) return;
  isProcessing = true;
  logger.info('[Fila] Processador iniciado.');

  while (isProcessing) {
    if (queue.length > 0) {
      const promo = queue.shift();
      logger.info(`[Fila] Processando: ${promo.title || 'Sem título'}`);

      try {
        const targetGroups = promo.targetGroups || config.destGroups;
        const groupIds = targetGroups.length > 0 ? targetGroups : getCachedGroups().map(g => g.id);

        for (const groupId of groupIds) {
          await sendToGroup(client, groupId, promo.text, promo.image);
          await randomDelay(1000, 2000);
        }

        logger.info(`[Fila] ✅ Promoção enviada: "${promo.title || 'Sem título'}"`);
      } catch (e) {
        logger.error(`[Fila] ❌ Erro ao enviar: ${e.message}`);
      }

      if (queue.length > 0) {
        const waitTime = await randomDelay(config.queueDelayMin, config.queueDelayMax);
        logger.info(`[Fila] Aguardando ${formatMs(waitTime)} antes do próximo...`);
      }
    } else {
      await randomDelay(config.queueCheckInterval, config.queueCheckInterval + 5000);
    }
  }
}

function enqueue(promo) {
  const messageHash = hashMessage(promo.text, promo.fromId || 'system');
  if (isDuplicate(messageHash)) {
    logger.debug('[Fila] Mensagem duplicada — ignorada.');
    return false;
  }
  markProcessed(messageHash);
  queue.push(promo);
  logger.info(`[Fila] Promoção adicionada. Tamanho: ${queue.length}`);
  saveQueueToDisk();
  return true;
}

function stopProcessing() {
  isProcessing = false;
  saveQueueToDisk();
  logger.info('[Fila] Processamento parado.');
}

function saveBeforeExit() {
  saveQueueToDisk();
}

function getQueueSize() {
  return queue.length;
}

module.exports = { enqueue, processQueue, stopProcessing, saveBeforeExit, getQueueSize, isDuplicate, markProcessed };
