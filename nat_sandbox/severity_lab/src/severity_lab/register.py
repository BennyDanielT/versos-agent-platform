# flake8: noqa

# Make Python's SSL use the OS (Windows) certificate store, which already trusts a
# corporate proxy's CA. Fixes "CERTIFICATE_VERIFY_FAILED" on calls like the model
# lookup that with_structured_output performs. Must run before any HTTPS call.
import truststore
truststore.inject_into_ssl()

# Load .env into the environment BEFORE NAT builds the LLM, so NVIDIA_API_KEY is
# available without a manual shell export. NAT imports this file when loading the
# package, which happens before the LLM is constructed.
from dotenv import load_dotenv
load_dotenv()

# Opt-in rich LLM tracing: when PHOENIX_TRACING=1, send OpenInference LLM spans
# (with token counts → cost/token panels) to Phoenix. Off by default so plain runs
# don't try to reach Phoenix. This instruments LangChain calls automatically.
import os
if os.getenv("PHOENIX_TRACING") == "1":
    try:
        from phoenix.otel import register as _phoenix_register
        _phoenix_register(project_name="versos_triage",
                          endpoint="http://localhost:6006/v1/traces",
                          auto_instrument=True)
    except Exception as _e:  # never let telemetry break the workflow
        print(f"[phoenix] tracing setup skipped: {_e}")

# Import the functions to trigger their registration with NAT.
from .severity_lab import triage_ticket_function
from .review import review_ticket_function
from .evals import register_severity_accuracy
from .index_hygiene import index_hygiene_function
