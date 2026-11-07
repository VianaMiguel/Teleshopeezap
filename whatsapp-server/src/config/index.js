const path = require('path');
const fs = require('fs');

const config = {
  port: process.env.PORT || 4000,
  displayQR: process.env.DISPLAY_QR !== 'false',
  destGroups: process.env.DEST_GROUPS ? process.env.DEST_GROUPS.split(',').map(g => g.trim()).filter(Boolean) : [],
  sourceGroups: process.env.SOURCE_GROUPS ? process.env.SOURCE_GROUPS.split(',').map(g => g.trim()).filter(Boolean) : [],
  queueDelayMin: parseInt(process.env.QUEUE_DELAY_MIN) || 120000,
  queueDelayMax: parseInt(process.env.QUEUE_DELAY_MAX) || 300000,
  typingDelayMin: parseInt(process.env.TYPING_DELAY_MIN) || 3000,
  typingDelayMax: parseInt(process.env.TYPING_DELAY_MAX) || 8000,
  queueCheckInterval: parseInt(process.env.QUEUE_CHECK_INTERVAL) || 30000,
};

const QUEUE_FILE = path.join(__dirname, '../../.queue_backup.json');

function loadQueueFromDisk() {
  try {
    if (fs.existsSync(QUEUE_FILE)) {
      const data = JSON.parse(fs.readFileSync(QUEUE_FILE, 'utf-8'));
      fs.unlinkSync(QUEUE_FILE);
      return data;
    }
  } catch (e) {
    console.error('[Config] Erro ao carregar backup da fila:', e.message);
  }
  return [];
}

config.loadedQueue = loadQueueFromDisk();

module.exports = config;
