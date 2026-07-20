#!/usr/bin/env node
/**
 * Local dev server for project-air HTML with fieldnote comments.
 *
 * fieldnote-svc only allows github.intuit.com/pages origins — not localhost.
 * This server proxies API calls through the same origin so comments work locally.
 *
 * Usage: npm run dev
 * Open:  http://localhost:7432/ita2.0-product-binder.html
 */

import { createServer } from 'node:http';
import { readFileSync, statSync, existsSync } from 'node:fs';
import { extname, join, normalize, basename } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const PORT = Number(process.env.PORT) || 7432;
const UPSTREAM = 'https://fieldnote-svc-e2e.api.intuit.com';
const PROXY_PREFIX = '/fieldnote-api';
const LOCAL_SERVICE = `http://localhost:${PORT}${PROXY_PREFIX}`;
const GITHUB_HOST = 'github.intuit.com';
const REPO = 'project-air';

function ghUsername() {
  if (process.env.GITHUB_USER) return process.env.GITHUB_USER;
  try {
    return execFileSync(
      'gh',
      ['api', 'user', '--hostname', GITHUB_HOST, '--jq', '.login'],
      { encoding: 'utf-8' },
    ).trim();
  } catch {
    return 'rraman2';
  }
}

const OWNER = ghUsername();

/** fieldnote-svc only accepts github.intuit.com/pages return URLs — not localhost. */
function pagesUrl(filename) {
  return `https://${GITHUB_HOST}/pages/${OWNER}/${REPO}/${filename}`;
}

function rewriteAuthReturn(queryString) {
  const params = new URLSearchParams(queryString.startsWith('?') ? queryString.slice(1) : queryString);
  const ret = params.get('return');
  if (!ret) return queryString;
  try {
    const file = basename(new URL(ret).pathname);
    if (file.endsWith('.html')) params.set('return', pagesUrl(file));
  } catch {
    /* leave unchanged */
  }
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
}

const DEV_READONLY_PATCH = `<!-- project-air:dev-readonly:begin -->
<script>
(function () {
  var file = location.pathname.split('/').pop() || 'ita2.0-product-binder.html';
  var pages = 'https://${GITHUB_HOST}/pages/${OWNER}/${REPO}/' + file;
  var notice = 'Comment actions (sign in, post, reply, resolve) only work on GitHub Pages, not localhost.\\n\\nOpen the live page in a new tab?';

  function openPages() {
    if (confirm(notice)) window.open(pages, '_blank');
  }

  function isAuthNav(url) {
    return /\\/v1\\/auth\\/login/.test(String(url));
  }

  // signIn() sets window.location.href — block before the browser navigates to auth/login
  try {
    var hrefDesc = Object.getOwnPropertyDescriptor(window.Location.prototype, 'href');
    if (hrefDesc && hrefDesc.set) {
      Object.defineProperty(window.location, 'href', {
        configurable: true,
        enumerable: true,
        get: hrefDesc.get.bind(window.location),
        set: function (url) {
          if (isAuthNav(url)) { openPages(); return; }
          hrefDesc.set.call(window.location, url);
        },
      });
    }
    var assign = window.location.assign.bind(window.location);
    window.location.assign = function (url) {
      if (isAuthNav(url)) { openPages(); return; }
      return assign(url);
    };
    var replace = window.location.replace.bind(window.location);
    window.location.replace = function (url) {
      if (isAuthNav(url)) { openPages(); return; }
      return replace(url);
    };
  } catch (e) { /* ignore */ }

  var origFetch = window.fetch;
  window.fetch = function (url, opts) {
    var u = String(url);
    var method = ((opts && opts.method) || 'GET').toUpperCase();
    if (u.indexOf('/fieldnote-api/') !== -1 && method !== 'GET' && method !== 'HEAD') {
      openPages();
      return Promise.reject(new Error('Use GitHub Pages for comment actions'));
    }
    return origFetch.apply(this, arguments);
  };

  document.addEventListener('click', function (e) {
    var path = typeof e.composedPath === 'function' ? e.composedPath() : [e.target];
    for (var i = 0; i < path.length; i++) {
      var el = path[i];
      if (!el || !el.classList) continue;
      if (
        el.classList.contains('fc-signin') ||
        el.classList.contains('fc-stamp') ||
        el.classList.contains('fc-reply-link') ||
        el.classList.contains('fc-post') ||
        el.classList.contains('fc-pagepost') ||
        el.classList.contains('fc-reply-post') ||
        el.classList.contains('fc-reopen') ||
        el.classList.contains('fc-rx')
      ) {
        e.preventDefault();
        e.stopImmediatePropagation();
        openPages();
        return;
      }
    }
  }, true);
})();
</script>
<!-- project-air:dev-readonly:end -->`;

const DEV_BANNER = `<!-- project-air:dev-server:begin -->
<div id="project-air-dev-banner" style="position:fixed;bottom:0;left:0;right:0;z-index:2147483647;background:#0C2340;color:#fff;font:600 13px/1.4 -apple-system,BlinkMacSystemFont,sans-serif;padding:10px 16px;text-align:center;box-shadow:0 -2px 12px rgba(0,0,0,.2)">
  <strong>Read-only preview.</strong> Comments load here; to sign in, post, reply, or resolve, use
  <a id="project-air-dev-pages-link" href="#" style="color:#00A3AD">GitHub Pages</a>.
</div>
<script>
(function(){
  var file=location.pathname.split('/').pop();
  var pages='https://${GITHUB_HOST}/pages/${OWNER}/${REPO}/'+file;
  var a=document.getElementById('project-air-dev-pages-link');
  if(a){a.href=pages;a.textContent=pages;}
})();
</script>
<!-- project-air:dev-server:end -->`;

function rewriteHtml(html) {
  let out = html.replace(
    /data-service="https:\/\/fieldnote-svc-e2e\.api\.intuit\.com"/g,
    `data-service="${LOCAL_SERVICE}"`,
  );
  if (!out.includes('project-air:dev-readonly:begin')) {
    out = out.replace(/<head>/i, `<head>\n${DEV_READONLY_PATCH}`);
    out = out.replace(/<\/body\s*>/i, `${DEV_BANNER}\n</body>`);
  } else if (!out.includes('project-air:dev-server:begin')) {
    out = out.replace(/<\/body\s*>/i, `${DEV_BANNER}\n</body>`);
  }
  return out;
}

function authReturnFilename(queryString, referer) {
  const params = new URLSearchParams(queryString.startsWith('?') ? queryString.slice(1) : queryString);
  const ret = params.get('return');
  for (const candidate of [ret, referer]) {
    if (!candidate) continue;
    try {
      const file = basename(new URL(candidate).pathname);
      if (file.endsWith('.html')) return file;
    } catch {
      /* try next */
    }
  }
  return 'ita2.0-product-binder.html';
}

function forwardHeaders(upstream) {
  const out = {};
  for (const [key, value] of upstream.headers) {
    const lower = key.toLowerCase();
    if (lower === 'transfer-encoding' || lower === 'connection') continue;
    out[key] = value;
  }
  return out;
}

async function proxy(req, res, pathname) {
  const upstreamPath = pathname.slice(PROXY_PREFIX.length) || '/';
  const rawQs = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '';
  const isAuthLogin = upstreamPath === '/v1/auth/login' || upstreamPath.endsWith('/v1/auth/login');
  const qs = isAuthLogin ? rewriteAuthReturn(rawQs) : rawQs;
  const url = `${UPSTREAM}${upstreamPath}${qs}`;

  const headers = { ...req.headers, host: new URL(UPSTREAM).host };
  delete headers['host'];

  const init = { method: req.method, headers };
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    init.body = Buffer.concat(chunks);
  }

  try {
    const upstream = await fetch(url, { ...init, redirect: 'manual' });

    // Safety net: never show raw JSON auth errors for localhost return URLs.
    if (isAuthLogin && req.method === 'GET' && upstream.status >= 400) {
      const file = authReturnFilename(rawQs, req.headers.referer);
      cors(res);
      res.writeHead(302, { Location: pagesUrl(file) });
      res.end();
      return;
    }

    cors(res);
    const outHeaders = forwardHeaders(upstream);
    if (!outHeaders['content-type']) outHeaders['Content-Type'] = 'application/json';
    const body = upstream.status === 204 || upstream.status === 304
      ? null
      : Buffer.from(await upstream.arrayBuffer());
    res.writeHead(upstream.status, outHeaders);
    res.end(body);
  } catch (err) {
    cors(res);
    res.writeHead(502, { 'Content-Type': 'text/plain' });
    res.end(`Proxy error: ${err.message}`);
  }
}

function serveStatic(req, res, pathname) {
  let filePath = normalize(join(ROOT, pathname));
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }
  if (pathname.endsWith('/') || !extname(pathname)) {
    const index = join(filePath, 'index.html');
    if (existsSync(index)) filePath = index;
    else if (existsSync(`${filePath}.html`)) filePath = `${filePath}.html`;
  }
  if (!existsSync(filePath) || statSync(filePath).isDirectory()) {
    res.writeHead(404);
    res.end('Not found');
    return;
  }

  let body = readFileSync(filePath);
  const type = MIME[extname(filePath).toLowerCase()] || 'application/octet-stream';
  if (type.startsWith('text/html')) {
    body = Buffer.from(rewriteHtml(body.toString('utf-8')), 'utf-8');
  }
  cors(res);
  res.writeHead(200, { 'Content-Type': type });
  res.end(body);
}

const server = createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  if (req.method === 'OPTIONS') {
    cors(res);
    res.writeHead(204);
    res.end();
    return;
  }
  if (url.pathname.startsWith(PROXY_PREFIX)) {
    proxy(req, res, url.pathname);
    return;
  }
  serveStatic(req, res, url.pathname === '/' ? '/index.html' : decodeURIComponent(url.pathname));
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`Port ${PORT} is already in use.`);
    console.error(`  Stop the other server:  kill $(lsof -t -iTCP:${PORT} -sTCP:LISTEN)`);
    console.error(`  Or use another port:     PORT=7433 npm run dev`);
    process.exit(1);
  }
  throw err;
});

server.listen(PORT, () => {
  console.log(`project-air dev server: http://localhost:${PORT}`);
  console.log(`  comments proxy: ${LOCAL_SERVICE} → ${UPSTREAM}`);
  console.log(`  mode:           read-only (post/reply/resolve → GitHub Pages)`);
  console.log(`  open: http://localhost:${PORT}/ita2.0-product-binder.html`);
});
