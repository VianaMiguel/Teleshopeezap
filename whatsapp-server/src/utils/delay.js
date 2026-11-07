function randomDelay(min, max) {
  return new Promise(resolve => {
    const time = Math.floor(Math.random() * (max - min + 1)) + min;
    setTimeout(() => resolve(time), time);
  });
}

function formatMs(ms) {
  if (ms >= 60000) return `${(ms / 60000).toFixed(1)} min`;
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)} s`;
  return `${ms} ms`;
}

module.exports = { randomDelay, formatMs };
