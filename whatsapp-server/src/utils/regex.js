function extractUrls(text) {
  const patterns = {
    mercadolivre: /(?:https?:\/\/)?(?:www\.)?(?:mercadolivre\.com\.br?)\/[^\s]+/gi,
    shopee: /(?:https?:\/\/)?(?:www\.)?(?:shopee\.com\.br|s\.shopee\.com\.br)\/[^\s]+/gi,
    amazon: /(?:https?:\/\/)?(?:www\.)?(?:amazon\.com\.br?)\/[^\s]+/gi,
  };
  const urls = [];
  const platform = [];

  for (const [name, pattern] of Object.entries(patterns)) {
    const matches = text.match(pattern);
    if (matches) {
      urls.push(...matches);
      platform.push(name);
    }
  }

  return { urls, platforms: platform.length ? platform : null };
}

module.exports = { extractUrls };
