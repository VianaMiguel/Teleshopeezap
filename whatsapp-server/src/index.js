require('dotenv').config();
const app = require('./server');
const { getClient, getReadyPromise, initialize } = require('./services/whatsapp');
const { processQueue } = require('./services/queue');
const { registerListener } = require('./services/listener');
const config = require('./config');
const logger = require('./utils/logger');

initialize().catch(e => logger.error('Erro ao inicializar:', e.message));

getReadyPromise().then(async (client) => {
  logger.info('✅ WhatsApp conectado!');
  if (config.sourceGroups.length > 0) {
    registerListener();
  }
  await processQueue(client);
}).catch(e => logger.error('Erro ao iniciar:', e.message));

process.on('SIGINT', () => {
  require('./services/queue').stopProcessing();
  require('./services/queue').saveBeforeExit();
  getClient().destroy();
  process.exit(0);
});
process.on('SIGTERM', () => {
  require('./services/queue').stopProcessing();
  require('./services/queue').saveBeforeExit();
  getClient().destroy();
  process.exit(0);
});
