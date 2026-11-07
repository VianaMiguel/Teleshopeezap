const config = require('../config');

const logger = {
  info: (msg) => console.log(`[${new Date().toLocaleTimeString('pt-BR')}] [INFO] ${msg}`),
  warn: (msg) => console.log(`[${new Date().toLocaleTimeString('pt-BR')}] [WARN] ${msg}`),
  error: (msg) => console.log(`[${new Date().toLocaleTimeString('pt-BR')}] [ERROR] ${msg}`),
  debug: (msg) => {
    if (process.env.LOG_LEVEL === 'DEBUG') {
      console.log(`[${new Date().toLocaleTimeString('pt-BR')}] [DEBUG] ${msg}`);
    }
  }
};

module.exports = logger;
