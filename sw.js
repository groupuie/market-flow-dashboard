/* 美股資金流向追蹤 — Service Worker
 * 設計原則：只快取「App 外殼」（HTML/JS/圖示），即時資料一律走網路、永不快取，
 * 避免手機上看到舊數據。改版由 Claude 部署後，下次連線開啟即自動取得最新頁面。
 *
 * 規則：
 *   - 跨網域請求（gist raw / Yahoo / CBOE / cdnjs / api.github.com）→ 完全不攔截（瀏覽器直連，永遠即時）
 *   - 同網域 /data/（signals.json 等即時檔）→ 網路優先，不長存快取
 *   - 導覽（HTML 頁面）→ 網路優先，成功即更新外殼快取；離線才回退快取
 *   - 其餘同網域靜態（klinecharts.min.js / icon / manifest）→ 快取優先 + 背景更新
 */
const V = 'mfd-v1';
const SHELL = [
  './', './index.html', './stock.html',
  './klinecharts.min.js', './manifest.json',
  './icon-180.png', './icon-192.png', './icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(V);
    // 逐檔加入，單一檔案失敗不影響其餘
    await Promise.all(SHELL.map(u => c.add(u).catch(() => {})));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== V).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', (e) => {
  if (e.data === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;                       // 只處理 GET
  const url = new URL(req.url);

  // 跨網域：即時資料與 CDN，一律不攔截（瀏覽器直連 → 永遠最新）
  if (url.origin !== self.location.origin) return;

  // 同網域 /data/（signals.json 等即時檔）：網路優先，不覆寫外殼快取
  if (url.pathname.includes('/data/')) {
    e.respondWith(fetch(req).catch(() => caches.match(req)));
    return;
  }

  // 導覽（HTML）：網路優先 → 成功則更新外殼快取；離線回退快取
  if (req.mode === 'navigate' || (req.destination === 'document')) {
    e.respondWith((async () => {
      try {
        const net = await fetch(req);
        const c = await caches.open(V);
        c.put(req, net.clone());
        return net;
      } catch (_) {
        return (await caches.match(req, { ignoreSearch: true }))
            || (await caches.match('./index.html'))
            || Response.error();
      }
    })());
    return;
  }

  // 其餘同網域靜態：快取優先 + 背景更新（stale-while-revalidate）
  e.respondWith((async () => {
    const cached = await caches.match(req);
    const fetching = fetch(req).then(net => {
      if (net && net.status === 200) caches.open(V).then(c => c.put(req, net.clone()));
      return net;
    }).catch(() => null);
    return cached || (await fetching) || Response.error();
  })());
});
