/* Harināmāmṛta-vyākaraṇam — service worker: tutto in cache al primo avvio, poi funziona senza rete.
   Il numero di VERSION segue quello dell'app (window.VR_N in index.html): lo aggiorna tools/sync-sw-version.py. */
const VERSION = "vyakaranam-v48";
/* Indispensabile: senza questo file l'app non può aprirsi offline. Se non si scarica (anche dopo i nuovi tentativi)
   l'installazione si ferma e riparte alla prossima apertura con la rete. */
const REQUIRED = ["index.html"];
/* Facoltativi: non devono mai bloccare l'installazione. Se ne manca qualcuno, si salva da solo alla prima richiesta. */
const OPTIONAL = ["./", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png", "icons/apple-touch-icon.png", "audio/shikharini-lakshana.m4a"];
/* Deve essere identico al link dei font in index.html */
const FONTS_CSS = "https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700&family=Noto+Serif:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Noto+Serif+Devanagari:wght@400;600&display=swap";
/* Su github.io tutte le app dello stesso account condividono lo stesso archivio: qui si toccano solo le cache "vyakaranam-". */
const PREFIX = "vyakaranam-";

/* Audio: Safari chiede i file audio a pezzi (Range) e vuole una risposta 206; dalla copia salvata si ritaglia l'intervallo richiesto. */
function rangeResponse(full, buf, range) {
  const size = buf.byteLength;
  let type = full.headers.get("Content-Type") || "";
  if (!/^audio\//.test(type)) type = "audio/mp4";
  const m = /^bytes=(\d*)-(\d*)$/.exec(range || "");
  if (!m || (m[1] === "" && m[2] === "")) {
    return new Response(buf, { status: 200, headers: { "Content-Type": type, "Content-Length": String(size), "Accept-Ranges": "bytes" } });
  }
  let start, end;
  if (m[1] === "") { start = Math.max(0, size - Number(m[2])); end = size - 1; }
  else { start = Number(m[1]); end = m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1); }
  if (start >= size || start > end) return new Response(null, { status: 416, headers: { "Content-Range": "bytes */" + size } });
  return new Response(buf.slice(start, end + 1), { status: 206, headers: { "Content-Type": type, "Content-Range": "bytes " + start + "-" + end + "/" + size, "Content-Length": String(end - start + 1), "Accept-Ranges": "bytes" } });
}
/* Se un audio non è ancora in cache lo si scarica intero in background (una volta sola), così la volta dopo funziona anche offline. */
const audioBusy = new Set();
async function cacheAudio(url) {
  if (audioBusy.has(url)) return;
  audioBusy.add(url);
  try {
    const c = await caches.open(VERSION);
    if (await c.match(url)) return;
    const r = await fetch(new Request(url, { cache: "reload" }));
    if (r.ok && r.status === 200) await c.put(url, r);
  } catch (_) {} finally { audioBusy.delete(url); }
}

/* Salva i font in cache; se mancano (o ne mancano dei pezzi) ci riprova a ogni apertura, in background. */
let fontsBusy = false;
async function cacheFonts() {
  if (fontsBusy) return;
  fontsBusy = true;
  try {
    const c = await caches.open(VERSION);
    let css;
    const have = await c.match(FONTS_CSS);
    if (have) css = await have.clone().text();
    else {
      const r = await fetch(FONTS_CSS);
      if (!r.ok) return;
      css = await r.clone().text();
      await c.put(FONTS_CSS, r);
    }
    const urls = [...new Set([...css.matchAll(/url\((https:[^)]+)\)/g)].map((m) => m[1]))];
    await Promise.all(urls.map(async (u) => {
      if (await c.match(u)) return;
      try { const x = await fetch(u); if (x.ok) await c.put(u, x); } catch (_) {}
    }));
  } catch (_) {} finally { fontsBusy = false; }
}

/* Scarica un file dalla rete (mai dalla copia del browser), con qualche nuovo tentativo se la connessione è debole. */
async function getFresh(u, tries) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(new Request(u, { cache: "reload" }));
      if (r.ok) return r;
      last = new Error(u + " " + r.status);
    } catch (err) { last = err; }
    if (i < tries - 1) await new Promise((res) => setTimeout(res, 1000 * (i + 1)));
  }
  throw last;
}

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(VERSION);
    await Promise.all(REQUIRED.map(async (u) => { await c.put(u, await getFresh(u, 3)); }));
    await Promise.all(OPTIONAL.map(async (u) => { try { await c.put(u, await getFresh(u, 2)); } catch (_) {} }));
    /* i font non devono mai bloccare l'installazione: massimo 8 secondi, poi si riprova alle aperture successive */
    await Promise.race([cacheFonts(), new Promise((res) => setTimeout(res, 8000))]);
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith(PREFIX) && k !== VERSION) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith((async () => {
    const uu = new URL(e.request.url);
    const same = uu.origin === location.origin;
    /* il controllo del gesto "trascina per aggiornare" (index.html?u=...) deve sempre chiedere alla rete, mai alla copia salvata */
    if (same && uu.searchParams.has("u")) return fetch(new Request(e.request.url, { cache: "no-store" }));
    if (same && /\/audio\/[^/]+$/.test(uu.pathname)) {
      const ac = await caches.open(VERSION);
      const key = uu.origin + uu.pathname;
      const full = await ac.match(key);
      if (full) return rangeResponse(full, await full.clone().arrayBuffer(), e.request.headers.get("Range"));
      e.waitUntil(cacheAudio(key));
      return fetch(e.request);
    }
    const cache = await caches.open(VERSION);
    const isPage = e.request.mode === "navigate" || (same && (uu.pathname.endsWith("/") || uu.pathname.endsWith("index.html")));
    if (isPage) {
      /* Apertura istantanea: si mostra subito la copia salvata e, in background, si scarica la versione nuova
         (visibile alla prossima apertura). Così il segnale debole non blocca mai l'avvio. */
      const old = await cache.match(e.request, { ignoreSearch: true }) || await cache.match("index.html");
      const refresh = fetch(new Request(e.request.url, { cache: "no-store" }))
        .then(async (r) => { if (r.ok) await cache.put(e.request, r.clone()); return r; })
        .catch(() => null);
      e.waitUntil(refresh);
      e.waitUntil(cacheFonts());
      if (old) return old;
      const fresh = await refresh;
      if (fresh && fresh.ok) return fresh;
    }
    const hit = await cache.match(e.request);
    if (hit) return hit;
    try {
      const res = await fetch(e.request);
      if (res.ok && (same || uu.hostname.endsWith("gstatic.com") || uu.hostname.endsWith("googleapis.com"))) {
        cache.put(e.request, res.clone());
      }
      return res;
    } catch (err) {
      if (e.request.mode === "navigate") { const p = await cache.match("index.html"); if (p) return p; }
      throw err;
    }
  })());
});
