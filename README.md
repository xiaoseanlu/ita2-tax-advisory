# project-air (Tax Advisory)

## View it live

- **Product binder (start here):** https://xiaoseanlu.github.io/ita2-tax-advisory/
- **PRD:** https://xiaoseanlu.github.io/ita2-tax-advisory/ita2.0-prd.html
- **Product blueprint:** https://xiaoseanlu.github.io/ita2-tax-advisory/ita2.0-product-blueprint.html
- **Use cases:** https://xiaoseanlu.github.io/ita2-tax-advisory/ita2.0-use-cases.html
- **LLM tax engine case:** https://xiaoseanlu.github.io/ita2-tax-advisory/llm-tax-engine-case.html

> The interactive tax-advisory web app (Flask + GenOS) requires Intuit credentials and runs locally only — see below. The links above are the static product artifacts served via GitHub Pages.


Tax advisory web UI and GenOS-backed calculation flow.

## Quick start — run the app

1. **Python 3** and a virtualenv (recommended).

2. **Install dependencies** (from this repo root):

   ```bash
   pip install -r requirements.txt
   ```

   **`genosclient` (GenOS) is not on PyPI** — it comes from **Intuit Artifactory**. If `pip` fails on `nocode-execution-genosclient-genosclient`, configure pip for Artifactory first (your team may provide a `.pip-artifactory-setup.sh` or internal docs with the **Artifactory URL** and auth). See **[docs/GENOS_PIP_INSTALL.md](docs/GENOS_PIP_INSTALL.md)** for what to tell new teammates and CI.

3. **Start the web server**:

   ```bash
   python3 web_ui_server.py
   ```

4. Open **http://127.0.0.1:5000/** (or whatever port is printed). Use another port with:

   ```bash
   PORT=5001 python3 web_ui_server.py
   ```

### Share a public URL (tunnel)

From the repo root:

```bash
./run_with_tunnel.sh
```

Uses Cloudflare quick tunnel by default. If that fails intermittently:

```bash
TUNNEL=ngrok ./run_with_tunnel.sh
```

More detail: [`web_ui/README.md`](web_ui/README.md).

---

## ITA Strategy Insights

After generating a tax calculation, you can get **Intuit Tax Advisor (ITA) strategy recommendations** using the scenario text and tax result:

```bash
python3 tax_cli.py scenario_hoh_2024 --ita-insights
```

Strategy content is in `strategies/` (maintained from ITA). The flow uses `strategy_loader.py` and `ita_insights.py` to recommend applicable strategies (e.g., Section 179, S-Corp election, Solo 401k) based on the situation and the tax return content.

---

## Configuration — Intuit IAM and GenOS

Copy `.env.example` to `.env` and fill in GenOS and Intuit values (see `genai_tax_core.py` and comments in `.env.example` for runtime env vars).

### Intuit IAM ticket (`INTUIT_IAM_TICKET`)

1. Open the **[Intuit API Explorer auth tool](https://devportal.intuit.com/app/dp/api-explorer/rest/landing/auth-tool)**.
2. Create an **authorization header** (sign in and complete the flow as prompted).
3. Copy the resulting **`intuit_token`** value into **`.env`** as **`INTUIT_IAM_TICKET`**.

The GenOS client uses this in metadata so requests authenticate correctly.

### Agentic ITA credentials

**App secrets** for the Agentic ITA experience (for example app id / secret used with GenOS) are managed in the Intuit Developer Portal:

**[Agentic ITA — credentials / secrets](https://devportal.intuit.com/app/dp/resource/2456731190064228324/credentials/secrets)**

Use those values in `.env` alongside `GENOS_EXPERIENCE_ID`, `GENOS_ASSET_ALIAS`, and related variables (see `genai_tax_core.py` and `.env.example`).

### GenOS Security and Safety (AI Workbench)

**Security and Safety** settings for GenOS for this experience can be reviewed and changed in **AI Workbench** (same experience id as the default Agentic ITA flow: `75be454b-adb9-4bb3-af7f-3275e04908c8`):

**[GenOS use case — Security & Safety config](https://ai-workbench.app.intuit.com/wb/projects/7572820366750835670/genos-usecases/75be454b-adb9-4bb3-af7f-3275e04908c8/gensrf-config)**

Background and discussion: [Slack thread](https://intuit-teams.slack.com/archives/C05HKU5DBKJ/p1759158007182299) (Intuit workspace).

For the PDF pipeline only, see `pdf_to_tax_situation/.env.example`.
