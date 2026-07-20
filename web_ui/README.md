# Tax Advisory Web UI

## Run with API (recommended)

From the **project-air** project root, run the Flask server so the UI can call the tax calculation API (same as `tax_cli.py`):

```bash
python3 web_ui_server.py
```

Then open **http://localhost:5000/** (or set `PORT` in the environment).

- Add scenarios in the modal; each card has a **Calculate** button.
- Click **Calculate** to send the scenario to the core (`genai_tax_core.get_tax_calculation_response`) and show the result on the screen.

## Static-only (no API)

To serve the UI without the API (Calculate will fail unless you point at another backend):

```bash
python3 -m http.server 8080
```

Then open **http://localhost:8080/web_ui/**

---

Do **not** run `python3 index.html` — that tries to execute the HTML file as Python.

## Share externally (tunnel)

```bash
./run_with_tunnel.sh
```

Uses **Cloudflare quick tunnel** (`cloudflared`). If you see **Error 1101**, **Worker threw exception**, or **`invalid character '<'`** — that’s **Cloudflare’s** `api.trycloudflare.com` failing (temporary). Retry later or use **ngrok**:

```bash
brew install ngrok/ngrok/ngrok
ngrok config add-authtoken <your token>   # from https://dashboard.ngrok.com
TUNNEL=ngrok ./run_with_tunnel.sh
```

Other: `PORT=5001 ./run_with_tunnel.sh`, or `TUNNEL=localtunnel` if you use `npm install -g localtunnel`.
