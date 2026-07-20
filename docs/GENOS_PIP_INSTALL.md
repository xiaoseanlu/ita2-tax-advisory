# Installing `genosclient` (Intuit Artifactory)

The package **`nocode-execution-genosclient-genosclient`** is **not** on the public Python Package Index (PyPI). `pip install -r requirements.txt` only works after `pip` is configured to use **Intuit’s Artifactory** (or another internal index your team uses).

That is why **Cursor**, **CI**, or a fresh machine will error until Artifactory access is set up the same way your working machine is.

## What your colleague needs

1. **Intuit network / VPN** (if required for Artifactory).
2. **Credentials or a token** for Artifactory PyPI — usually from internal docs, your team’s wiki, or **Developer / Platform** onboarding (not something we can put in this public repo).
3. **One-time pip configuration** so installs resolve the `genosclient` package.

## Common ways teams do this

### A. Team-provided setup script

Some repos include a script (e.g. `.pip-artifactory-setup.sh`) that writes `pip.conf` or runs `pip config set` with the correct **Artifactory URL** and auth. **This repo may not ship that script** — ask your team or copy it from another internal project that already installs `nocode-execution-genosclient-genosclient`.

After setup:

```bash
pip install -r requirements.txt
```

### B. Manual `pip` / `uv` extra index

If internal documentation gives you an **Artifactory simple index URL** and auth method (token in URL, `pip keyring`, etc.), configure `pip` accordingly, then run `pip install -r requirements.txt` again.

### C. Internal wheel or mirror

Some teams vendor a `.whl` or use an internal mirror; follow your org’s process.

## Verify

```bash
python3 -c "import genosclient; print('ok')"
```

## App runtime (separate from pip)

Installing the package is not enough: the app also needs **GenOS / Intuit IAM** variables in `.env` (see `.env.example`). See `genai_tax_core.py` and your team’s GenOS onboarding for `GENOS_*`, `INTUIT_*`, etc.

## If you cannot use Artifactory

You cannot run the full GenOS-backed flows without `genosclient`. Options are: use a machine that already has Artifactory configured, or ask **your team / IT** for the official Artifactory + pip instructions for Python packages.
