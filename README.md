# Prism-Reviewer — Agentic Multi-Agent Code Review

One LLM reviewer gives you one opinion. **Prism runs a council of three
specialist agents** — then guards their output with a verifier before anything
reaches your PR.

## The council

```
PR opened
  └─► build_context ─┬─► WARDEN     (security & compliance)
                     ├─► ARCHITECT  (structure, coupling, design)
                     └─► INSPECTOR  (logic, correctness, edge cases)
                              │  (parallel fan-out, findings merged)
                     verifier_node   — hallucination guard: drops findings not
                                       in the diff, dedups by signature
                              │
                     aggregator_node — severity-sorted Markdown report
```

- **Warden** — the AppSec gatekeeper: hardcoded secrets, injection vectors,
  XSS, SSRF, insecure deserialization. Paranoid by design.
- **Architect** — structure and design: god functions, coupling, layering,
  dependency smells (backed by AST maps + dependency scans).
- **Inspector** — logic and correctness: off-by-ones, error handling,
  edge cases, dead code.
- **Verifier** — drops findings whose (file, line) isn't in the diff and
  deduplicates by content signature, so re-runs don't re-report.
- **Aggregator** — renders the final severity-sorted Markdown report.

Any model, via **LiteLLM**: OpenAI, Anthropic, Gemini, Groq, Ollama… with
per-agent model overrides (e.g. a strong model for Warden, a cheap one for
Inspector).

## Use it

**As a GitHub Action** — drop the workflow in, set two secrets:

```yaml
- uses: HuzaifaAqeel/Prism-Reviewer@main
  with:
    llm-model-name: openai/gpt-4o
  env:
    LLM_PROVIDER_API_KEY: ${{ secrets.LLM_PROVIDER_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Locally:**

```bash
pip install -r requirements.txt
cp .env.example .env        # GITHUB_TOKEN, LLM_PROVIDER_API_KEY, LLM_MODEL
prism-review --help
```

All secrets come from env vars (or `prism_reviewer.toml` with `${VAR}`
placeholders) — nothing is hardcoded.

## Offline demo (no API key)

```bash
python demo_review.py
```

Runs the real LangGraph pipeline on a fabricated PR diff with deterministic
stubbed findings: watch the three agents fan out in parallel, the verifier
drop a hallucinated finding, and the aggregator render the final report.
Set `PRISM_DEMO_LIVE=1` with `LLM_MODEL` + `LLM_PROVIDER_API_KEY` to run the
same script against a real model.

## Layout

```
src/prism_reviewer/
  agents/        # LangGraph graph, warden/architect/inspector nodes,
                 # verifier, aggregator, agent personas
  codelens/      # AST parsing, dependency scanning, code search context
  core/          # env-var config loader (TOML + ${VAR} placeholders)
  services/      # LiteLLM client with retry, GitHub API client
  monitoring/    # run observability
action.yml       # the GitHub Action definition
demo_review.py   # offline end-to-end demo
```

## License

Apache-2.0 — see `LICENSE`.
