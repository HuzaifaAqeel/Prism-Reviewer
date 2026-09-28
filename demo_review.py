#!/usr/bin/env python3
"""
demo_review.py — Prism-Reviewer offline demo.

Runs the real multi-agent review graph (LangGraph: build_context -> warden /
architect / inspector -> verifier -> aggregator) against a fabricated PR diff.
No API key needed: the LiteLLM completion layer is stubbed with deterministic,
per-agent findings. Set PRISM_DEMO_LIVE=1 with LLM_MODEL + LLM_PROVIDER_API_KEY
to run against a real model.
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from prism_reviewer.core.config import Config
from prism_reviewer.services import llm as llm_service
from prism_reviewer.agents import graph as graph_mod

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(HERE, "demo_repo")

PAYMENTS_PY = '''import os
import sqlite3

API_KEY = "sk-live-9f2c4a1b7e"

DB_PATH = os.getenv("DB_PATH", "app.db")


def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return conn.execute(query).fetchall()


def process_payment(user_id, amount, currency, method, retry, notify, log):
    for attempt in range(3):
        try:
            charge(user_id, amount)
        except:
            pass
    notify(user_id, "done")
    return True
'''

DIFF = """diff --git a/src/payments.py b/src/payments.py
new file mode 100644
index 0000000..1a2b3c4
--- /dev/null
+++ b/src/payments.py
@@ -0,0 +1,22 @@
+import os
+import sqlite3
+
+API_KEY = "sk-live-9f2c4a1b7e"
+
+DB_PATH = os.getenv("DB_PATH", "app.db")
+
+
+def get_user(user_id):
+    conn = sqlite3.connect(DB_PATH)
+    query = f"SELECT * FROM users WHERE id = {user_id}"
+    return conn.execute(query).fetchall()
+
+
+def process_payment(user_id, amount, currency, method, retry, notify, log):
+    for attempt in range(3):
+        try:
+            charge(user_id, amount)
+        except:
+            pass
+    notify(user_id, "done")
+    return True
"""

TOML = """# Minimal config for the offline demo. All secrets come from env vars.
[llm]
model = "${LLM_MODEL|-openai/gpt-4o-mini}"

[github]
token = "${GITHUB_TOKEN|-}"

[agents.reasoning_effort]
warden = "medium"
architect = "medium"
inspector = "medium"
"""

# Canned per-agent findings. (file, line) pairs MUST exist in DIFF above —
# the verifier drops anything else as a hallucination.
CANNED = {
    "Warden": [
        {"file": "src/payments.py", "line": 4, "severity": "CRITICAL",
         "message": "Hardcoded live API key committed to source; rotate it and move to a secret manager."},
        {"file": "src/payments.py", "line": 11, "severity": "CRITICAL",
         "message": "SQL injection: user_id is interpolated into the query via f-string instead of a parameter."},
    ],
    "Architect": [
        {"file": "src/payments.py", "line": 15, "severity": "MAJOR",
         "message": "process_payment takes 7 parameters, signalling a god function; split charging, retry and notification."},
        {"file": "src/payments.py", "line": 9, "severity": "MAJOR",
         "message": "get_user opens a DB connection per call and never closes it; use a context manager or pool."},
    ],
    "Inspector": [
        {"file": "src/payments.py", "line": 19, "severity": "MAJOR",
         "message": "Bare except: swallows every error including KeyboardInterrupt and hides charge failures."},
        {"file": "src/payments.py", "line": 16, "severity": "ADVISORY",
         "message": "Magic number 3 for retry attempts; name it MAX_RETRIES for clarity."},
    ],
}


def fake_completion_with_retry(self, messages, reasoning_effort=None, model=None):
    import re
    system = messages[0].get("content", "") if messages else ""
    m = re.search(r"# System Persona:\s*(\w+)", system)
    agent = m.group(1) if m else ""
    findings = CANNED.get(agent, [])
    return json.dumps({"findings": findings})


def fake_build_context(state):
    """Stand-in for build_context_node: injects the fabricated PR context."""
    return {
        "regions": [],
        "ast_map": {},
        "repo_structure": "src/payments.py",
        "readme_content": "",
        "context_content": "",
        "rules_content": "",
        "codelens_search_hits": "",
        "codelens_dep_summary": "",
        "previous_signatures": [],
    }


def main():
    os.makedirs(os.path.join(REPO_DIR, "src"), exist_ok=True)
    with open(os.path.join(REPO_DIR, "src", "payments.py"), "w") as f:
        f.write(PAYMENTS_PY)
    toml_path = os.path.join(HERE, "prism_reviewer.toml")
    with open(toml_path, "w") as f:
        f.write(TOML)

    Config.load(toml_path)

    if os.getenv("PRISM_DEMO_LIVE") == "1":
        print("[demo] LIVE mode — real LLM via LiteLLM")
    else:
        print("[demo] offline mode — stubbed LLM findings (no API key needed)")
        llm_service.ResilientLLMClient.completion_with_retry = fake_completion_with_retry

    graph_mod.build_context_node = fake_build_context
    graph = graph_mod.build_graph()

    initial_state = {
        "repo_path": REPO_DIR,
        "git_diff": DIFF,
        "pr_title": "Add payments module",
        "pr_description": "Adds get_user and process_payment helpers.",
    }
    print("\n== Running agent council: Warden + Architect + Inspector ==\n")
    result = graph.invoke(initial_state)

    print("\n" + "=" * 70)
    print("FINAL REVIEW REPORT")
    print("=" * 70 + "\n")
    print(result.get("report_markdown", "(no report)"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
