require('dotenv').config({ path: require('path').join(__dirname, '../../../.env') });
require('dotenv').config();
const { getClient, getIsReady, getReadyPromise, initialize } = require('../services/whatsapp');
const config = require('../config');
const logger = require('../utils/logger');

async function listGroups() {
  console.log('Conectando ao WhatsApp (use a sessão existente ou escaneie o QR)...');
  initialize().catch(e => {
    console.error('Erro ao inicializar:', e.message);
    process.exit(1);
  });

  const timeoutMs = 240000;
  const pronto = await Promise.race([
    getReadyPromise().then(() => true),
    new Promise(r => setTimeout(() => r(false), timeoutMs)),
  ]);

  if (!pronto || !getIsReady()) {
    console.log('Não foi possível conectar em', timeoutMs / 1000, 's.');
    console.log('Se apareceu QR em qrcode.png, escaneie e rode de novo.');
    process.exit(1);
  }

  let chats = [];
  let channels = [];
  try {
    const client = getClient();
    // A lista de chats demora a carregar após o 'ready' — espera e retenta
    for (let tentativa = 1; tentativa <= 6; tentativa++) {
      await new Promise(r => setTimeout(r, 5000));
      chats = await client.getChats();
      try {
        channels = await client.getChannels();
      } catch (_) { channels = []; }
      const parciais = chats.filter(ch => ch.isGroup).length + (channels ? channels.length : 0);
      if (parciais > 0 && tentativa >= 2) break;
      console.log(`Carregando chats e canais (tentativa ${tentativa}/6)...`);
    }
  } catch (e) {
    logger.error('getChats falhou:', e.message);
  }

  const groups = chats.filter(ch => ch.isGroup);
  const canais = (channels || []).filter(Boolean);

  if (groups.length === 0 && canais.length === 0) {
    console.log('\nNenhum grupo ou canal encontrado.');
    console.log('Use GET http://localhost:4000/groups ou descubra manualmente.\n');
  } else {
    console.log('\n═══════════════════════════════════════');
    console.log(`  GRUPOS (${groups.length}) E CANAIS (${canais.length})`);
    console.log('═══════════════════════════════════════\n');

    let i = 0;
    groups.forEach((g) => {
      i++;
      const isSource = config.sourceGroups.includes(g.id._serialized);
      const isDest = config.destGroups.includes(g.id._serialized);
      console.log(`${i}. 👥 Grupo: ${g.name || 'Sem nome'}`);
      console.log(`   ID: ${g.id._serialized}`);
      if (isDest) console.log(`   ✅ Destino configurado`);
      if (isSource) console.log(`   📡 Fonte configurada`);
      console.log('');
    });

    canais.forEach((ch) => {
      i++;
      const id = (ch.id && (ch.id._serialized || ch.id)) || '';
      const isSource = config.sourceGroups.includes(id);
      const isDest = config.destGroups.includes(id);
      console.log(`${i}. 📢 Canal: ${ch.name || ch.formattedTitle || 'Sem nome'}`);
      console.log(`   ID: ${id}`);
      if (isDest) console.log(`   ✅ Destino configurado`);
      if (isSource) console.log(`   📡 Fonte configurada`);
      console.log('');
    });

    console.log('═══════════════════════════════════════');
    console.log('Copie o ID para o .env como WHATSAPP_CHAT_ID');
    console.log('═══════════════════════════════════════\n');
  }
}

listGroups().then(() => process.exit(0)).catch(e => {
  console.error('Erro:', e.message);
  process.exit(1);
});
