"""
Serves the Tax Advisory web UI and an API that runs the core tax calculation (tax_cli.py / genai_tax_core).
Run from repo root: python web_ui_server.py
Then open http://localhost:5000/
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure repo root is on path so we can import genai_tax_core
_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Load .env from repo root so GENOS_* / INTUIT_* are available when API runs
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
except ImportError:
    pass
except Exception:
    pass

from pdf_pipeline_local import (
    pdf_pipeline_dir,
    pdf_pipeline_local_available,
    pdf_pipeline_missing_message,
    pdf_pipeline_run_script,
)

from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="web_ui", static_url_path="")

# Lazy import so we only load tax/LLM code when the API is actually called
def _get_tax_calculation_response(description: str, *, tax_year: int | None = None) -> str:
    from genai_tax_core import get_tax_calculation_response

    return get_tax_calculation_response(
        description,
        include_reference=True,
        print_prompt=_debug_tax_calc(),
        tax_year=tax_year,
    )


def _get_tax_calculation_with_strategies(description: str, strategies: list, *, tax_year: int | None = None) -> str:
    from genai_tax_core import get_tax_calculation_response_with_strategies

    return get_tax_calculation_response_with_strategies(
        description,
        strategies,
        print_prompt=_debug_tax_calc(),
        tax_year=tax_year,
    )


def _fill_data_model(raw_result: str, scenario: str) -> dict:
    """Run schema filler on raw LLM result; returns dict with tax_situation and form_1040_calculated_lines."""
    from tax_schema_filler import fill_tax_data_model
    return fill_tax_data_model(raw_result, scenario)


def _run_pdf_to_description(pdf_path: Path, output_dir: Path) -> tuple[str | None, str | None]:
    """Run pdf_to_tax_situation pipeline (extract + build description). Returns (description, error)."""
    pipe_dir = pdf_pipeline_dir()
    script = pdf_pipeline_run_script()
    if not script.is_file():
        return None, pdf_pipeline_missing_message()
    desc_file = output_dir / "description.txt"
    cmd = [
        sys.executable,
        str(script),
        str(pdf_path),
        "--output-dir",
        str(output_dir),
        "-o",
        str(desc_file),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(pipe_dir),
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return None, "PDF pipeline timed out (extraction can take over a minute)."
    except FileNotFoundError:
        return None, pdf_pipeline_missing_message()
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "PDF pipeline failed.").strip()
        return None, err
    if not desc_file.exists():
        return None, "Description file was not produced."
    try:
        return desc_file.read_text(encoding="utf-8"), None
    except OSError as e:
        return None, str(e)


def _iam_pdf_error_allows_local_fallback(err: str) -> bool:
    """Same policy as expert_advisory_e2e: retry local pipeline for classifier/extraction quirks, not auth."""
    if os.environ.get("EXPERT_E2E_IAM_NO_LOCAL_FALLBACK", "").lower() in ("1", "true", "yes"):
        return False
    low = (err or "").lower()
    hard = (
        "credentials missing",
        "authentication",
        "http 401",
        "http 403",
        "http 404",
        "no document id",
        "upload failed",
        "pdf not found",
        "request error",
        "timed out waiting for extraction",
    )
    if any(h in low for h in hard):
        return False
    return True


def _web_ui_pdf_scenario_style() -> str:
    raw = (os.environ.get("WEB_UI_PDF_SCENARIO_STYLE") or "statements").strip().lower()
    if raw in ("lines", "line", "label", "labels"):
        return "lines"
    return "statements"


def _pdf_upload_to_scenario_text(pdf_path: Path, output_dir: Path) -> tuple[str | None, str | None]:
    """
    Extract scenario text from a 1040 PDF using the configured backend
    (PDF_EXTRACTION_BACKEND=des|claude|local; see pdf_extraction_config.py).
    On soft failures, fall back to local pdf_to_tax_situation (see EXPERT_E2E_IAM_NO_LOCAL_FALLBACK).
    """
    try:
        from pdf_extraction_config import pdf_extraction_backend, pdf_extraction_configured
    except Exception:
        pdf_extraction_backend = lambda: "des"  # type: ignore[assignment,misc]
        pdf_extraction_configured = None  # type: ignore[assignment]

    backend = pdf_extraction_backend() if pdf_extraction_backend else "des"
    use_remote = backend in ("des", "claude")
    if backend == "local":
        use_remote = False
    elif os.environ.get("WEB_UI_PDF_USE_INTUIT", "1").lower() in ("0", "false", "no") and backend == "des":
        use_remote = False

    remote_err: str | None = None
    if use_remote and pdf_extraction_configured and pdf_extraction_configured():
        try:
            from iam_pdf_extraction import extract_1040_from_pdf_for_scenario

            desc, err = extract_1040_from_pdf_for_scenario(
                pdf_path,
                scenario_style=_web_ui_pdf_scenario_style(),
            )
        except Exception as e:
            desc, err = None, f"PDF extraction failed ({backend}): {e}"
        if (desc or "").strip() and not err:
            return (desc or "").strip(), None
        if err:
            remote_err = err
        if err and _iam_pdf_error_allows_local_fallback(err):
            print(
                f"[web_ui] {backend} PDF extraction failed ({err}); falling back to local PDF pipeline.",
                file=sys.stderr,
            )
        elif err:
            return None, err

    if not pdf_pipeline_local_available():
        msg = pdf_pipeline_missing_message()
        if remote_err:
            return None, (
                f"PDF extraction ({backend}) did not produce a scenario ({remote_err}).\n\n{msg}"
            )
        return None, msg

    return _run_pdf_to_description(pdf_path, output_dir)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


def _debug_insights():
    v = os.environ.get("DEBUG_INSIGHTS", "1")
    return v.lower() in ("1", "true", "yes") and v not in ("0", "false", "no")


def _debug_tax_calc() -> bool:
    """When true, print full user prompts (and strategy block) to stderr for /api/calculate."""
    v = os.environ.get("DEBUG_TAX_CALC", "0")
    return v.lower() in ("1", "true", "yes")


@app.route("/api/insights", methods=["POST"])
def api_insights():
    """Get ITA strategy insights for a scenario + structured tax data. Returns list of strategy dicts."""
    import traceback
    data = request.get_json(force=True, silent=True) or {}
    scenario = (data.get("scenario") or "").strip()
    tax_result = (data.get("tax_result") or "").strip()
    data_model = data.get("data_model")
    if _debug_insights():
        print("[DEBUG INSIGHTS] Received request:", file=__import__("sys").stderr)
        print(f"  scenario length: {len(scenario)}, first 200 chars: {repr(scenario[:200])}", file=__import__("sys").stderr)
        print(f"  data_model: {bool(data_model)}, tax_result length: {len(tax_result)}", file=__import__("sys").stderr)
    if not scenario:
        return jsonify({"error": "Missing or empty 'scenario' in request body"}), 400
    if not data_model and not tax_result:
        return jsonify({"error": "Missing 'data_model' and 'tax_result'. Run Calculate Tax first."}), 400
    try:
        from ita_insights import get_ita_insights_with_strategies
        from strategy_savings import enrich_strategies_with_savings
        if _debug_insights():
            print("[DEBUG INSIGHTS] Calling get_ita_insights_with_strategies (data_model=%s)..." % bool(data_model), file=__import__("sys").stderr)
        strategies = get_ita_insights_with_strategies(
            scenario,
            tax_result if not data_model else None,
            data_model=data_model,
        )
        if _debug_insights():
            print(f"[DEBUG INSIGHTS] got {len(strategies)} strategies: {[s.get('strategy_id') for s in strategies]}", file=__import__("sys").stderr)
        strategies = enrich_strategies_with_savings(
            strategies, scenario, tax_result if not data_model else "", data_model=data_model
        )
        if _debug_insights():
            print(f"[DEBUG INSIGHTS] after enrich: {len(strategies)} strategies, returning", file=__import__("sys").stderr)
        return jsonify({"strategies": strategies})
    except Exception as e:
        if _debug_insights():
            print(f"[DEBUG INSIGHTS] EXCEPTION: {e}", file=__import__("sys").stderr)
            traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/plan", methods=["GET"])
def api_plan_read():
    """Read plan (strategies) for a scenario. Query: scenario_id. Returns entries with titles enriched."""
    scenario_id = (request.args.get("scenario_id") or "").strip()
    if not scenario_id:
        return jsonify({"error": "Missing scenario_id"}), 400
    from plan_store import read_plan
    from strategy_loader import StrategyLoader
    entries = read_plan(scenario_id)
    # Enrich with strategy titles
    try:
        loader = StrategyLoader()
        for i, e in enumerate(entries):
            if "title" not in e and e.get("strategy_id"):
                s = loader.get_strategy(e["strategy_id"])
                if s:
                    entries[i] = {**e, "title": s.get("title", e["strategy_id"])}
    except Exception:
        pass
    return jsonify({"strategies": entries})


@app.route("/api/plan", methods=["POST"])
def api_plan_add():
    """Add or update a strategy in the plan. Body: { scenario_id, strategy_id, inputs }."""
    data = request.get_json(force=True, silent=True) or {}
    scenario_id = (data.get("scenario_id") or "").strip()
    strategy_id = (data.get("strategy_id") or "").strip()
    inputs = data.get("inputs") or {}
    if not scenario_id:
        return jsonify({"error": "Missing scenario_id"}), 400
    if not strategy_id:
        return jsonify({"error": "Missing strategy_id"}), 400
    from plan_store import add_to_plan
    entry = add_to_plan(scenario_id, strategy_id, inputs)
    return jsonify(entry)


@app.route("/api/plan", methods=["PUT"])
def api_plan_update():
    """Update an existing plan entry. Body: { scenario_id, strategy_id, inputs }."""
    data = request.get_json(force=True, silent=True) or {}
    scenario_id = (data.get("scenario_id") or "").strip()
    strategy_id = (data.get("strategy_id") or "").strip()
    inputs = data.get("inputs") or {}
    if not scenario_id or not strategy_id:
        return jsonify({"error": "Missing scenario_id or strategy_id"}), 400
    from plan_store import update_plan_entry
    entry = update_plan_entry(scenario_id, strategy_id, inputs)
    if entry is None:
        return jsonify({"error": "Strategy not in plan"}), 404
    return jsonify(entry)


@app.route("/api/plan", methods=["DELETE"])
def api_plan_delete():
    """Remove a strategy from the plan. Query: scenario_id, strategy_id."""
    scenario_id = (request.args.get("scenario_id") or "").strip()
    strategy_id = (request.args.get("strategy_id") or "").strip()
    if not scenario_id or not strategy_id:
        return jsonify({"error": "Missing scenario_id or strategy_id"}), 400
    from plan_store import delete_from_plan
    removed = delete_from_plan(scenario_id, strategy_id)
    return jsonify({"removed": removed})


@app.route("/api/plan/entry", methods=["GET"])
def api_plan_entry():
    """Get a single plan entry. Query: scenario_id, strategy_id."""
    scenario_id = (request.args.get("scenario_id") or "").strip()
    strategy_id = (request.args.get("strategy_id") or "").strip()
    if not scenario_id or not strategy_id:
        return jsonify({"error": "Missing scenario_id or strategy_id"}), 400
    from plan_store import get_plan_entry
    entry = get_plan_entry(scenario_id, strategy_id)
    if entry is None:
        return jsonify({"error": "Not in plan"}), 404
    return jsonify(entry)


@app.route("/api/strategy-savings", methods=["POST"])
def api_strategy_savings():
    """Calculate strategy savings with custom inputs (for refine widget)."""
    data = request.get_json(force=True, silent=True) or {}
    strategy_id = (data.get("strategy_id") or "").strip()
    inputs = data.get("inputs") or {}
    if not strategy_id:
        return jsonify({"error": "Missing 'strategy_id'"}), 400
    try:
        from strategy_calculators import calculate_strategy_savings
        result = calculate_strategy_savings(strategy_id, inputs)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    """Run tax calculation. If strategies provided, also run with-strategies. Returns result, data_model, and optionally result_with_strategies."""
    data = request.get_json(force=True, silent=True) or {}
    scenario = (data.get("scenario") or "").strip()
    strategies = data.get("strategies") or []
    tax_year_raw = data.get("tax_year")
    tax_year: int | None = None
    if tax_year_raw is not None and str(tax_year_raw).strip() != "":
        try:
            tax_year = int(tax_year_raw)
        except (TypeError, ValueError):
            pass
    if not scenario:
        return jsonify({"error": "Missing or empty 'scenario' in request body"}), 400
    try:
        result = _get_tax_calculation_response(scenario, tax_year=tax_year)
        data_model = _fill_data_model(result, scenario)
        out = {"result": result, "data_model": data_model}
        if strategies:
            result_with_strategies = _get_tax_calculation_with_strategies(
                scenario, strategies, tax_year=tax_year
            )
            out["result_with_strategies"] = result_with_strategies
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/memory", methods=["GET"])
def api_memory_list():
    """List durable assistant memory for a scenario (UC-6 / UC-7). Query: scenario_id."""
    scenario_id = (request.args.get("scenario_id") or "").strip()
    if not scenario_id:
        return jsonify({"error": "Missing scenario_id"}), 400
    from chat_memory_store import list_memory
    return jsonify({"items": list_memory(scenario_id)})


@app.route("/api/memory", methods=["POST"])
def api_memory_add():
    """Add a memory item. Body: { scenario_id, text }."""
    data = request.get_json(force=True, silent=True) or {}
    scenario_id = (data.get("scenario_id") or "").strip()
    text = (data.get("text") or "").strip()
    if not scenario_id:
        return jsonify({"error": "Missing scenario_id"}), 400
    try:
        from chat_memory_store import add_memory
        item = add_memory(scenario_id, text)
        return jsonify(item)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/memory", methods=["DELETE"])
def api_memory_delete():
    """Delete one memory item. Query: scenario_id, memory_id."""
    scenario_id = (request.args.get("scenario_id") or "").strip()
    memory_id = (request.args.get("memory_id") or "").strip()
    if not scenario_id or not memory_id:
        return jsonify({"error": "Missing scenario_id or memory_id"}), 400
    from chat_memory_store import delete_memory
    deleted = delete_memory(scenario_id, memory_id)
    if not deleted:
        return jsonify({"error": "Memory item not found"}), 404
    return jsonify({"deleted": True})


@app.route("/api/chat", methods=["GET"])
def api_chat_get():
    """Chat message history for a scenario."""
    scenario_id = (request.args.get("scenario_id") or "").strip()
    if not scenario_id:
        return jsonify({"error": "Missing scenario_id"}), 400
    from chat_thread_store import get_messages
    return jsonify({"messages": get_messages(scenario_id)})


@app.route("/api/chat", methods=["DELETE"])
def api_chat_clear():
    """Clear chat thread for a scenario. Query: scenario_id."""
    scenario_id = (request.args.get("scenario_id") or "").strip()
    if not scenario_id:
        return jsonify({"error": "Missing scenario_id"}), 400
    from chat_thread_store import clear_thread
    n = clear_thread(scenario_id)
    return jsonify({"cleared": n})


@app.route("/api/chat", methods=["POST"])
def api_chat_post():
    """
    Send a user message; get assistant reply via ask_llm_chat (GenOS /responses on v3).
    Body: {
      scenario_id, message, scenario_text,
      optional: data_model, tax_result, tax_year, proactive (bool)
    }
    """
    data = request.get_json(force=True, silent=True) or {}
    scenario_id = (data.get("scenario_id") or "").strip()
    user_message = (data.get("message") or "").strip()
    scenario_text = (data.get("scenario_text") or "").strip()
    proactive = bool(data.get("proactive"))
    data_model = data.get("data_model")
    if data_model is not None and not isinstance(data_model, dict):
        data_model = None
    tax_result = (data.get("tax_result") or "").strip() or None
    tax_year_raw = data.get("tax_year")
    tax_year: int | None = None
    if tax_year_raw is not None and str(tax_year_raw).strip() != "":
        try:
            tax_year = int(tax_year_raw)
        except (TypeError, ValueError):
            tax_year = None

    if not scenario_id:
        return jsonify({"error": "Missing scenario_id"}), 400
    if not user_message and not proactive:
        return jsonify({"error": "Missing or empty message"}), 400

    from chat_memory_store import list_memory
    from chat_thread_store import append_message, get_messages
    from strategy_chat_agent import (
        build_strategy_enriched_prompt,
        build_strategy_system_prompt,
        fetch_applicable_strategies,
        format_proactive_strategy_reply,
        missing_data_model_reply,
        should_run_strategy_matching,
        strategies_to_client_payload,
    )
    from tax_year_utils import ensure_tax_year_in_tax_prompt

    prior = get_messages(scenario_id)
    max_msgs = 24
    prior_slice = prior[-max_msgs:] if len(prior) > max_msgs else prior
    memory_items = list_memory(scenario_id)

    if proactive:
        user_message = user_message or "What ITA strategies might apply to this return?"

    run_strategies = should_run_strategy_matching(
        user_message=user_message,
        prior_messages=prior_slice,
        data_model=data_model,
        proactive=proactive,
    )

    if run_strategies and not data_model:
        reply = missing_data_model_reply(user_message, proactive=proactive) or ""
        user_entry = append_message(scenario_id, "user", user_message)
        assistant_entry = append_message(scenario_id, "assistant", reply)
        return jsonify(
            {
                "reply": assistant_entry["content"],
                "strategies": [],
                "user_message": user_entry,
                "assistant_message": assistant_entry,
            }
        )

    matched: list = []
    if run_strategies and data_model:
        try:
            matched = fetch_applicable_strategies(
                scenario_text,
                data_model=data_model,
                tax_result=tax_result,
            )
        except Exception as e:
            return jsonify({"error": f"Strategy matching failed: {e}"}), 500

    strategy_payload = strategies_to_client_payload(matched)

    if proactive:
        reply_clean = format_proactive_strategy_reply(matched)
        user_entry = append_message(scenario_id, "user", user_message)
        assistant_entry = append_message(
            scenario_id,
            "assistant",
            reply_clean,
            strategies=strategy_payload or None,
        )
        return jsonify(
            {
                "reply": assistant_entry["content"],
                "strategies": strategy_payload,
                "user_message": user_entry,
                "assistant_message": assistant_entry,
            }
        )

    try:
        from genai_tax_core import (
            ask_llm_chat,
            build_chat_user_prompt,
            get_tax_rules_system_prompt,
            normalize_chat_assistant_reply,
        )

        if run_strategies:
            prompt = build_strategy_enriched_prompt(
                scenario_text,
                memory_items,
                prior_slice,
                user_message,
                matched,
                include_reference=True,
            )
            system_prompt = build_strategy_system_prompt(get_tax_rules_system_prompt())
        else:
            prompt = build_chat_user_prompt(
                scenario_text,
                memory_items,
                prior_slice,
                user_message,
                include_reference=True,
            )
            system_prompt = get_tax_rules_system_prompt()

        prompt = ensure_tax_year_in_tax_prompt(prompt, tax_year=tax_year)
        reply = ask_llm_chat(
            prompt,
            system_prompt=system_prompt,
            temperature=0.1,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    reply_clean = normalize_chat_assistant_reply(str(reply).strip())
    if not reply_clean:
        return jsonify({"error": "Assistant returned an empty response"}), 502

    user_entry = append_message(scenario_id, "user", user_message)
    assistant_entry = append_message(
        scenario_id,
        "assistant",
        reply_clean,
        strategies=strategy_payload if strategy_payload else None,
    )
    return jsonify(
        {
            "reply": assistant_entry["content"],
            "strategies": strategy_payload,
            "user_message": user_entry,
            "assistant_message": assistant_entry,
        }
    )


@app.route("/api/workspace/snapshots", methods=["GET"])
def api_workspace_snapshots_list():
    """List saved workspace snapshots (metadata only)."""
    from workspace_snapshots import list_snapshots

    return jsonify({"snapshots": list_snapshots()})


@app.route("/api/workspace/snapshot", methods=["POST"])
def api_workspace_snapshot_save():
    """Save a full workspace state. Body: { label?, state }."""
    data = request.get_json(force=True, silent=True) or {}
    state = data.get("state")
    if not isinstance(state, dict):
        return jsonify({"error": "Missing or invalid 'state' object"}), 400
    label = data.get("label")
    if label is not None and not isinstance(label, str):
        label = None
    from workspace_snapshots import save_snapshot

    meta = save_snapshot(label, state)
    return jsonify(meta)


@app.route("/api/workspace/snapshot/<snapshot_id>", methods=["GET"])
def api_workspace_snapshot_get(snapshot_id: str):
    """Load one snapshot (metadata + full state)."""
    from workspace_snapshots import get_snapshot

    snap = get_snapshot((snapshot_id or "").strip())
    if snap is None:
        return jsonify({"error": "Snapshot not found"}), 404
    return jsonify(snap)


@app.route("/api/workspace/snapshot/<snapshot_id>", methods=["DELETE"])
def api_workspace_snapshot_delete(snapshot_id: str):
    """Delete a snapshot."""
    from workspace_snapshots import delete_snapshot

    deleted = delete_snapshot((snapshot_id or "").strip())
    if not deleted:
        return jsonify({"error": "Snapshot not found"}), 404
    return jsonify({"deleted": True})


@app.route("/api/workspace/restore", methods=["POST"])
def api_workspace_restore():
    """Apply server-side portion of a saved state (chat, memory, plan). Body: { state }."""
    data = request.get_json(force=True, silent=True) or {}
    state = data.get("state")
    if not isinstance(state, dict):
        return jsonify({"error": "Missing or invalid 'state' object"}), 400
    server_by = state.get("serverByScenario") or state.get("server_by_scenario")
    if not isinstance(server_by, dict):
        return jsonify({"error": "state must include serverByScenario"}), 400
    from workspace_snapshots import apply_server_state

    apply_server_state(server_by)
    return jsonify({"ok": True})


@app.route("/api/pdf-to-description", methods=["POST"])
def api_pdf_to_description():
    """Upload a 1040 PDF; run extraction + description pipeline; return the narrative for the scenario box."""
    if "file" not in request.files and "pdf" not in request.files:
        return jsonify({"error": "No file uploaded. Use form field 'file' or 'pdf'."}), 400
    file = request.files.get("file") or request.files.get("pdf")
    if not file or file.filename == "":
        return jsonify({"error": "No file selected."}), 400
    if not (file.filename or "").lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted."}), 400

    with tempfile.TemporaryDirectory(prefix="pdf_upload_") as tmp:
        tmp_path = Path(tmp)
        pdf_path = tmp_path / "upload.pdf"
        try:
            file.save(str(pdf_path))
        except OSError as e:
            return jsonify({"error": f"Failed to save upload: {e}"}), 500
        description, err = _pdf_upload_to_scenario_text(pdf_path, tmp_path)
        if err:
            return jsonify({"error": err}), 500
        from tax_year_utils import parse_tax_year_from_text

        tax_year = parse_tax_year_from_text(description or "")
        out: dict = {"description": description}
        if tax_year:
            out["tax_year"] = tax_year
        return jsonify(out)


def _skill_tool_module(skill_dir_name: str, module_name: str):
    """Load a skill tools module by file path (avoids colliding `tools` packages)."""
    import importlib.util

    path = (
        _root
        / "skills"
        / "income_tax"
        / "assisted"
        / skill_dir_name
        / "tools"
        / f"{module_name}.py"
    )
    key = f"ita_skill_{skill_dir_name}_{module_name}".replace("-", "_")
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load skill tool {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _scorp_tool_module():
    return _skill_tool_module("scorp-conversion", "scorp_conversion")


def _solo401k_tool_module():
    return _skill_tool_module("solo-401k", "solo_401k")


def _ee401k_tool_module():
    return _skill_tool_module("401k-employee", "ee_401k")


@app.route("/ita-strategies")
@app.route("/ita-strategies.html")
def ita_strategies_page():
    return send_from_directory(app.static_folder, "ita-strategies.html")


@app.route("/scorp-conversion")
@app.route("/scorp-conversion.html")
def scorp_conversion_page():
    # Hub with left-nav; keep old URL working.
    from flask import redirect

    return redirect("/ita-strategies?strategy=scorp-conversion")


@app.route("/api/ita-strategies/registry")
def api_ita_strategies_registry():
    """Product strategy list → SPE folder → skill status."""
    path = _root / "ita-rules" / "strategy-registry.json"
    if not path.is_file():
        return jsonify({"error": "strategy-registry.json not found"}), 404
    import json

    with open(path, encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/ita-strategies/outline/<slug>")
def api_ita_strategies_outline(slug):
    """SPE input outline for a strategy (markdown or json)."""
    safe = "".join(c for c in slug if c.isalnum() or c in "-_")
    if not safe or safe != slug:
        return jsonify({"error": "Invalid slug"}), 400
    fmt = (request.args.get("format") or "md").lower()
    ext = "json" if fmt == "json" else "md"
    path = _root / "ita-rules" / "strategy-outlines" / f"{safe}.{ext}"
    if not path.is_file():
        return jsonify({"error": f"Outline not found for {slug}"}), 404
    if ext == "json":
        import json

        with open(path, encoding="utf-8") as f:
            return jsonify(json.load(f))
    from flask import Response

    with open(path, encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/markdown; charset=utf-8")


@app.route("/api/scorp-conversion/assess", methods=["POST"])
def api_scorp_assess():
    """Part 1 — assess S-Corp applicability (deterministic tool)."""
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data.get("activity"), dict):
        return jsonify({"error": "Missing 'activity' object."}), 400
    try:
        mod = _scorp_tool_module()
        result = mod.assess_from_dict(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/scorp-conversion/estimate", methods=["POST"])
def api_scorp_estimate():
    """Part 2 — estimate S-Corp savings given confirmed reasonable_wage."""
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data.get("activity"), dict):
        return jsonify({"error": "Missing 'activity' object."}), 400
    if data.get("reasonable_wage") is None:
        return jsonify({"error": "reasonable_wage is required."}), 400
    try:
        mod = _scorp_tool_module()
        result = mod.savings_from_dict(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/solo-401k/assess", methods=["POST"])
def api_solo401k_assess():
    """Part 1 — assess Solo 401(k) applicability."""
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data.get("person"), dict):
        return jsonify({"error": "Missing 'person' object."}), 400
    try:
        mod = _solo401k_tool_module()
        return jsonify(mod.assess_from_dict(data))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/solo-401k/estimate", methods=["POST"])
def api_solo401k_estimate():
    """Part 2 — estimate Solo 401(k) savings."""
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data.get("person"), dict):
        return jsonify({"error": "Missing 'person' object."}), 400
    try:
        mod = _solo401k_tool_module()
        return jsonify(mod.savings_from_dict(data))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/401k-employee/assess", methods=["POST"])
def api_ee401k_assess():
    """Part 1 — assess 401(k) EE applicability for a W-2."""
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data.get("w2"), dict):
        return jsonify({"error": "Missing 'w2' object."}), 400
    try:
        mod = _ee401k_tool_module()
        return jsonify(mod.assess_from_dict(data))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/401k-employee/estimate", methods=["POST"])
def api_ee401k_estimate():
    """Part 2 — estimate 401(k) EE savings."""
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data.get("w2"), dict):
        return jsonify({"error": "Missing 'w2' object."}), 400
    try:
        mod = _ee401k_tool_module()
        return jsonify(mod.savings_from_dict(data))
    except Exception as e:
        return jsonify({"error": str(e)}), 400



RETIREMENT_TOOL_MODULES = {
    "401k-employee": ("401k-employee", "ee_401k"),
    "401k-employer": ("401k-employer", "er_401k"),
    "403b-employee": ("403b-employee", "ee_403b"),
    "403b-employer": ("403b-employer", "er_403b"),
    "traditional-ira": ("traditional-ira", "traditional_ira"),
    "sep-ira": ("sep-ira", "sep_ira"),
    "backdoor-roth-ira": ("backdoor-roth-ira", "backdoor_roth"),
    "mega-backdoor-roth": ("mega-backdoor-roth", "mega_backdoor"),
    "roth-ira-conversion": ("roth-ira-conversion", "roth_conversion"),
    "solo-401k": ("solo-401k", "solo_401k"),
}


def _retirement_tool_module(slug: str):
    if slug not in RETIREMENT_TOOL_MODULES:
        raise KeyError(f"Unknown retirement strategy: {slug}")
    skill_dir, module_name = RETIREMENT_TOOL_MODULES[slug]
    return _skill_tool_module(skill_dir, module_name)


@app.route("/api/retirement/<slug>/assess", methods=["POST"])
def api_retirement_assess(slug):
    """Part 1 — assess a SPE-faithful retirement strategy."""
    safe = "".join(c for c in slug if c.isalnum() or c in "-_")
    if safe != slug:
        return jsonify({"error": "Invalid slug"}), 400
    data = request.get_json(force=True, silent=True) or {}
    try:
        mod = _retirement_tool_module(slug)
        return jsonify(mod.assess_from_dict(data))
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/retirement/<slug>/estimate", methods=["POST"])
def api_retirement_estimate(slug):
    """Part 2 — estimate SPE-faithful retirement strategy savings."""
    safe = "".join(c for c in slug if c.isalnum() or c in "-_")
    if safe != slug:
        return jsonify({"error": "Invalid slug"}), 400
    data = request.get_json(force=True, silent=True) or {}
    try:
        mod = _retirement_tool_module(slug)
        return jsonify(mod.savings_from_dict(data))
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/ita-strategies/projection-seed")
def api_ita_strategies_projection_seed():
    """Compact form seed extracted from ita-rules/2025projection.json (or ?file=)."""
    import json

    name = (request.args.get("file") or "2025projection.json").strip()
    safe = Path(name).name
    if not safe.endswith(".json"):
        return jsonify({"error": "file must be a .json under ita-rules/"}), 400
    path = _root / "ita-rules" / safe
    if not path.is_file():
        return jsonify({"error": f"{safe} not found"}), 404
    try:
        import sys as _sys

        _ita_rules = str(_root / "ita-rules")
        if _ita_rules not in _sys.path:
            _sys.path.insert(0, _ita_rules)
        from projection_ui_seed import extract_ui_seed
    except ImportError as e:
        return jsonify({"error": f"projection_ui_seed import failed: {e}"}), 500

    with open(path, encoding="utf-8") as f:
        projection = json.load(f)
    seed = extract_ui_seed(projection)
    seed["source"] = f"ita-rules/{safe}"
    return jsonify(seed)


if __name__ == "__main__":
    import os as _os
    _port = int(_os.getenv("PORT", "5000"))
    if _debug_insights():
        print("[DEBUG INSIGHTS] Insights debug logging is ON (set DEBUG_INSIGHTS=0 to disable)", file=sys.stderr)
    print(f"ITA strategies: http://localhost:{_port}/ita-strategies", file=sys.stderr)
    app.run(host="0.0.0.0", port=_port, debug=False)
