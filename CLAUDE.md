# Project AIR — Claude Instructions

## Development Server

**Always use `npm run dev` to serve HTML files — never `python -m http.server`.**

```bash
npm run dev
# → http://localhost:7432
```

The Node dev server (scripts/dev-server.mjs) is required because:
- It proxies API calls to `fieldnote-svc` so inline comments load without CORS errors
- The Python server cannot proxy — comments will appear broken/empty
- Auth for posting comments requires GitHub Pages, but the dev server lets you view existing comments locally

If port 7432 is already in use:
```bash
lsof -ti:7432 | xargs kill -9
npm run dev
```

## Comment System

HTML files are wired with the fieldnote comment widget (GitHub Discussions backend).

To wire a new HTML file with comments:
```bash
npm run wire-comments -- your-file.html
```

This requires `gh auth login --hostname github.intuit.com` to be set up.

After wiring, commit and push — comments are visible on GitHub Pages:
`https://github.intuit.com/pages/rraman2/project-air/<filename>.html`

## Key Files

- `ita2.0-product-binder.html` — main product binder (primary artifact)
- `scripts/dev-server.mjs` — local dev server with fieldnote API proxy
- `scripts/wire-comments.mjs` — injects comment widget into HTML files
- `package.json` — defines `npm run dev` and `npm run wire-comments`

## Setup (first time)

```bash
npm install
npm run dev
```

Requires Node.js and `gh` CLI authenticated to `github.intuit.com`.
