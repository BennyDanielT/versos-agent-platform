"""Run the triage golden set as a Phoenix EXPERIMENT (UI-driven, complementary to `nat eval`).

Why this exists alongside `nat eval`:
  - `nat eval`            = CLI pass/fail score → the CI regression GATE.
  - this Phoenix experiment = same golden set, but results land as a VERSIONED run in
                            the Phoenix UI: side-by-side run comparison + per-example
                            drill-down. The tool you open while ITERATING on a prompt.

It does NOT replace `nat eval`. Same exact-match logic, different surface.

Prereqs (all must be up):
  - Phoenix server running at http://localhost:6006   (python -m phoenix.server.main serve)
  - Postgres up + NIM key in .env  (the experiment runs the REAL workflow per example)

CAVEAT: running the workflow INSERTs one row per example into triage_log. Those rows
carry the [phx-exp] marker below so you can purge them:
    DELETE FROM triage_log WHERE complaint_text LIKE '[phx-exp]%';

Run:
    .venv/Scripts/python.exe nat_sandbox/severity_lab/scripts/phoenix_experiment.py
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

# Importing the package triggers @register_function so load_workflow can resolve triage_ticket.
import severity_lab.register  # noqa: F401
from severity_lab.scoring import extract_severity, severity_matches   # shared brain (also used by evals.py)
from nat.runtime.loader import load_workflow
from phoenix.client import Client
from phoenix.client.experiments import run_experiment

# --- paths (resolved from this file, so it runs from anywhere) -------------------
_PKG = Path(__file__).resolve().parents[1]          # .../severity_lab
CONFIG = _PKG / "src" / "severity_lab" / "configs" / "triage_observed.yml"
DATASET_JSON = _PKG / "eval" / "triage_eval.json"
MARKER = "[phx-exp] "                                # tags rows so they can be purged

# --- one workflow session manager, loaded lazily inside the experiment's loop ----
_sm = None
_sm_lock = asyncio.Lock()


async def _session_manager():
    global _sm
    async with _sm_lock:
        if _sm is None:
            # __aenter__ once and leave open for the whole run; process exit cleans up.
            _sm = await load_workflow(str(CONFIG)).__aenter__()
    return _sm


async def task(example) -> str:
    """Run the real triage workflow on one complaint; return the predicted severity."""
    inp = example["input"] if isinstance(example, dict) else example.input
    complaint = MARKER + inp["complaint"]
    sm = await _session_manager()
    async with sm.session() as s:
        async with s.run(complaint) as r:
            raw = await r.result(to_type=str)
    return extract_severity(raw)                           # shared parse ("" if malformed)


def severity_exact_match(output, expected) -> float:
    """Phoenix-shaped evaluator; brain is the shared severity_matches()."""
    exp = expected.get("severity", "") if isinstance(expected, dict) else expected
    return 1.0 if severity_matches(output, exp) else 0.0


def main() -> None:
    cases = json.loads(DATASET_JSON.read_text(encoding="utf-8"))
    client = Client(base_url="http://localhost:6006")

    dataset = client.datasets.create_dataset(
        name="triage_severity_golden",
        inputs=[{"complaint": c["question"]} for c in cases],
        outputs=[{"severity": c["answer"]} for c in cases],
        dataset_description="Severity golden set (same data as nat eval triage_eval.json).",
    )

    run_experiment(
        dataset=dataset,
        task=task,
        evaluators=[severity_exact_match],
        experiment_name="severity_exact_match",
        experiment_description="Triage severity vs gold; mirrors the nat eval severity_accuracy run.",
        client=client,
    )
    print("Done. Open http://localhost:6006 → Datasets → triage_severity_golden → Experiments.")


if __name__ == "__main__":
    main()
