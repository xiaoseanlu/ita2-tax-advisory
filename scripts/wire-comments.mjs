#!/usr/bin/env node
/**
 * Embed the fieldnote comment widget in local HTML files for GitHub Pages.
 *
 * Usage:
 *   node scripts/wire-comments.mjs <file.html> [more.html ...]
 *   node scripts/wire-comments.mjs <file.html> --slug custom-slug
 *
 * Requires: gh auth login --hostname github.intuit.com
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { basename, extname, resolve } from 'node:path';
import {
  ensureDiscussion,
  injectCommentWidget,
  stripCommentWidget,
} from '@dev-devsuccess/fieldnote/dist/comments.js';

const GITHUB_HOST = 'github.intuit.com';
const REPO = 'project-air';
const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;

function usage() {
  console.log(`Usage: wire-comments <file.html> [...] [--slug <name>]

Embeds the fieldnote comment widget (Google Docs-style inline comments).
Discussion is keyed by <github-user>/<slug> — independent of fieldnote publish.

Examples:
  npm run wire-comments -- ita2.0-product-binder.html
  npm run wire-comments -- ita2.0-prd.html --slug ita2-prd-v2`);
}

function deriveSlug(filename, explicit) {
  if (explicit) {
    const cleaned = explicit.trim().toLowerCase();
    if (!SLUG_RE.test(cleaned)) {
      throw new Error(`Invalid slug "${explicit}". Use lowercase letters, digits, and dashes.`);
    }
    return cleaned;
  }
  const base = basename(filename, extname(filename));
  const slug = base
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 64);
  if (!slug || !SLUG_RE.test(slug)) {
    throw new Error(`Could not derive slug from "${filename}". Pass --slug explicitly.`);
  }
  return slug;
}

function ghUsername() {
  try {
    return execFileSync(
      'gh',
      ['api', 'user', '--hostname', GITHUB_HOST, '--jq', '.login'],
      { encoding: 'utf-8' },
    ).trim();
  } catch {
    throw new Error(`Not authenticated to ${GITHUB_HOST}. Run: gh auth login --hostname ${GITHUB_HOST}`);
  }
}

function parseArgs(argv) {
  const files = [];
  let slug = null;
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--slug') {
      slug = argv[++i];
      if (!slug) throw new Error('--slug requires a value');
    } else if (arg === '--help' || arg === '-h') {
      usage();
      process.exit(0);
    } else if (arg.startsWith('-')) {
      throw new Error(`Unknown option: ${arg}`);
    } else {
      files.push(arg);
    }
  }
  if (files.length === 0) {
    usage();
    process.exit(1);
  }
  return { files, slug };
}

function stripLegacyComments(html) {
  return html.replace(/\s*<script\s+src=["']inline-comments\.js["']\s*><\/script>\s*/gi, '\n');
}

const RESOLVE_VISIBLE_BEGIN = '<!-- fieldnote:resolve-visible:begin -->';
const RESOLVE_VISIBLE_END = '<!-- fieldnote:resolve-visible:end -->';

/** Default widget hides Resolve until card hover (opacity:0). Keep it visible for PM review. */
const RESOLVE_VISIBLE_PATCH = `${RESOLVE_VISIBLE_BEGIN}
<script>
(function () {
  function patch() {
    var host = document.getElementById('fieldnote-widget-host');
    if (!host || !host.shadowRoot) return setTimeout(patch, 250);
    if (host.shadowRoot.querySelector('[data-project-air-resolve-visible]')) return;
    var style = document.createElement('style');
    style.setAttribute('data-project-air-resolve-visible', '');
    style.textContent = '.fc-stamp{opacity:1!important}';
    host.shadowRoot.appendChild(style);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', patch);
  else patch();
})();
</script>
${RESOLVE_VISIBLE_END}`;

function stripResolveVisiblePatch(html) {
  const begin = html.indexOf(RESOLVE_VISIBLE_BEGIN);
  if (begin === -1) return html;
  const endIdx = html.indexOf(RESOLVE_VISIBLE_END, begin);
  if (endIdx === -1) return html;
  let after = endIdx + RESOLVE_VISIBLE_END.length;
  if (html[after] === '\n') after += 1;
  return html.slice(0, begin) + html.slice(after);
}

function addResolveVisiblePatch(html) {
  const end = '<!-- fieldnote:comments:end -->';
  const idx = html.indexOf(end);
  if (idx === -1) return html;
  return html.slice(0, idx) + RESOLVE_VISIBLE_PATCH + '\n' + html.slice(idx);
}

async function wireFile(absPath, slugOverride) {
  const slug = deriveSlug(absPath, slugOverride);
  const owner = ghUsername();
  let html = readFileSync(absPath, 'utf-8');
  html = stripLegacyComments(html);

  const discussion = await ensureDiscussion(owner, slug);
  if (discussion == null) {
    throw new Error(
      `Could not register discussion for ${owner}/${slug}. Check VPN and fieldnote-svc availability.`,
    );
  }

  let wired = injectCommentWidget(html, discussion);
  wired = stripResolveVisiblePatch(wired);
  wired = addResolveVisiblePatch(wired);
  writeFileSync(absPath, wired, 'utf-8');

  const filename = basename(absPath);
  const pagesUrl = `https://${GITHUB_HOST}/pages/${owner}/${REPO}/${filename}`;

  console.log(`✓ ${filename}`);
  console.log(`  discussion: ${owner}/${slug} (#${discussion})`);
  console.log(`  share:      ${pagesUrl}`);
}

const { files, slug } = parseArgs(process.argv.slice(2));

for (const file of files) {
  await wireFile(resolve(file), files.length === 1 ? slug : null);
}

console.log('\nNext: git add, commit, push — comments appear on your Pages URL after deploy.');
