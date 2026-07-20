/**
 * Inline comment system backed by GitHub Enterprise Issues (github.intuit.com).
 *
 * Setup: set GITHUB_HOST and GITHUB_REPO below.
 * Team members need a github.intuit.com account to comment. No server required.
 *
 * How it works:
 *  - Select any text → "Add Comment" button appears
 *  - Clicking opens a GitHub Issue pre-filled with selected text + context
 *  - A floating panel shows all open issues (comments) for the current page
 */

(function () {
  const GITHUB_HOST = 'github.intuit.com';
  const GITHUB_REPO = 'rraman2/project-air';
  const GITHUB_API  = `https://${GITHUB_HOST}/api/v3`; // GitHub Enterprise REST API base
  const PAGE_LABEL = 'inline-comment';

  // Derive a stable page tag from the filename so issues are scoped per page
  const PAGE_TAG = location.pathname.split('/').pop().replace('.html', '') || 'index';

  // ── Styles ────────────────────────────────────────────────────────────────

  const css = `
    #ic-tooltip {
      position: absolute;
      display: none;
      z-index: 9999;
      background: #0C2340;
      color: #fff;
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 13px;
      font-family: system-ui, sans-serif;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(0,0,0,0.25);
      user-select: none;
      white-space: nowrap;
    }
    #ic-tooltip:hover { background: #00A3AD; }

    #ic-panel {
      position: fixed;
      top: 0; right: 0;
      width: min(280px, 85vw);
      height: 100vh;
      background: #fff;
      border-left: 1px solid #D4D5D9;
      box-shadow: -4px 0 16px rgba(0,0,0,0.1);
      display: flex;
      flex-direction: column;
      z-index: 9998;
      font-family: system-ui, sans-serif;
      transform: translateX(100%);
      transition: transform 0.25s ease;
    }
    #ic-panel.open { transform: translateX(0); }

    #ic-panel-header {
      padding: 16px;
      background: #0C2340;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }
    #ic-panel-header h3 { margin: 0; font-size: 15px; font-weight: 600; }

    #ic-panel-close {
      background: none; border: none; color: #fff;
      font-size: 18px; cursor: pointer; padding: 0 4px;
      line-height: 1;
    }

    #ic-panel-body {
      flex: 1;
      overflow-y: auto;
      padding: 12px;
    }

    .ic-issue {
      border: 1px solid #D4D5D9;
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 10px;
      font-size: 13px;
      line-height: 1.5;
    }
    .ic-issue-title {
      font-weight: 600;
      color: #0C2340;
      margin-bottom: 4px;
      text-decoration: none;
      display: block;
    }
    .ic-issue-title:hover { color: #00A3AD; }
    .ic-issue-meta { color: #6B6C72; font-size: 11px; margin-bottom: 6px; }
    .ic-issue-quote {
      background: #F4F4F5;
      border-left: 3px solid #00A3AD;
      padding: 4px 8px;
      font-style: italic;
      color: #393A3D;
      border-radius: 0 4px 4px 0;
      margin: 4px 0 6px;
      font-size: 12px;
    }
    .ic-issue-body { color: #393A3D; }

    #ic-panel-empty {
      text-align: center;
      color: #6B6C72;
      padding: 40px 16px;
      font-size: 13px;
    }

    #ic-panel-footer {
      padding: 12px 16px;
      border-top: 1px solid #D4D5D9;
      flex-shrink: 0;
    }
    #ic-panel-footer a {
      display: block;
      text-align: center;
      background: #00A3AD;
      color: #fff;
      padding: 8px;
      border-radius: 6px;
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
    }
    #ic-panel-footer a:hover { background: #008891; }

    #ic-toggle {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 9997;
      background: #0C2340;
      color: #fff;
      border: none;
      border-radius: 50px;
      padding: 10px 18px;
      font-size: 13px;
      font-weight: 600;
      font-family: system-ui, sans-serif;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      display: flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s;
    }
    #ic-toggle:hover { background: #00A3AD; }
    #ic-badge {
      background: #00A3AD;
      border-radius: 10px;
      padding: 1px 6px;
      font-size: 11px;
      min-width: 16px;
      text-align: center;
    }
    #ic-toggle.panel-open { background: #393A3D; }
  `;

  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  // ── Tooltip (appears on text selection) ──────────────────────────────────

  const tooltip = document.createElement('div');
  tooltip.id = 'ic-tooltip';
  tooltip.textContent = '💬 Add Comment';
  document.body.appendChild(tooltip);

  let lastSelection = '';

  document.addEventListener('mouseup', (e) => {
    // small delay so selection is finalized
    setTimeout(() => {
      const sel = window.getSelection();
      const text = sel ? sel.toString().trim() : '';

      if (text.length < 3) {
        tooltip.style.display = 'none';
        return;
      }

      lastSelection = text;
      const range = sel.getRangeAt(0).getBoundingClientRect();
      tooltip.style.display = 'block';
      tooltip.style.top = `${range.bottom + window.scrollY + 8}px`;
      tooltip.style.left = `${range.left + window.scrollX}px`;
    }, 10);
  });

  document.addEventListener('mousedown', (e) => {
    if (e.target !== tooltip) {
      tooltip.style.display = 'none';
    }
  });

  tooltip.addEventListener('click', () => {
    tooltip.style.display = 'none';
    openNewIssue(lastSelection);
  });

  function openNewIssue(selectedText) {
    const pageTitle = document.title;
    const truncated = selectedText.length > 200
      ? selectedText.slice(0, 200) + '…'
      : selectedText;

    const title = encodeURIComponent(`[${PAGE_TAG}] Comment`);
    const body = encodeURIComponent(
      `**Page:** ${pageTitle}\n**URL:** ${location.href}\n\n` +
      `> ${truncated}\n\n` +
      `---\n*(Add your comment below this line)*\n\n`
    );
    const labels = encodeURIComponent(`${PAGE_LABEL},${PAGE_TAG}`);
    const url = `https://${GITHUB_HOST}/${GITHUB_REPO}/issues/new?title=${title}&body=${body}&labels=${labels}`;
    window.open(url, '_blank');
  }

  // ── Panel (shows existing issues / comments) ──────────────────────────────

  const issuesUrl = `https://${GITHUB_HOST}/${GITHUB_REPO}/issues?q=is:issue+is:open+label:${PAGE_TAG}`;
  const newIssueHint = `Select any text on this page, then click the "Add Comment" tooltip that appears.`;

  const panel = document.createElement('div');
  panel.id = 'ic-panel';
  panel.innerHTML = `
    <div id="ic-panel-header" style="cursor:pointer;" onclick="document.getElementById('ic-panel').classList.remove('open');document.getElementById('ic-toggle').classList.remove('panel-open');">
      <span style="font-size:22px;font-weight:300;line-height:1;margin-right:10px;">✕</span>
      <h3 style="margin:0;pointer-events:none;">💬 Comments</h3>
    </div>
    <div id="ic-panel-body">
      <div id="ic-panel-empty">
        <p style="margin:0 0 12px">Comments are tracked as GitHub Issues for this page.</p>
        <p style="margin:0 0 16px;font-size:12px;color:#6B6C72">${newIssueHint}</p>
        <a href="${issuesUrl}" target="_blank" style="display:inline-block;background:#0C2340;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:600">
          View comments on GitHub →
        </a>
      </div>
    </div>
  `;
  document.body.appendChild(panel);

  const toggle = document.createElement('button');
  toggle.id = 'ic-toggle';
  toggle.innerHTML = `💬 Add / View Comments`;
  document.body.appendChild(toggle);

  toggle.addEventListener('click', () => {
    const isOpen = panel.classList.toggle('open');
    toggle.classList.toggle('panel-open', isOpen);
  });

  document.getElementById('ic-panel-close').addEventListener('click', () => {
    panel.classList.remove('open');
    toggle.classList.remove('panel-open');
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && panel.classList.contains('open')) {
      panel.classList.remove('open');
      toggle.classList.remove('panel-open');
    }
  });

  // Close on click outside panel
  document.addEventListener('click', (e) => {
    if (panel.classList.contains('open') && !panel.contains(e.target) && e.target !== toggle) {
      panel.classList.remove('open');
      toggle.classList.remove('panel-open');
    }
  });

  // ── Helpers ───────────────────────────────────────────────────────────────

  function escHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

})();
