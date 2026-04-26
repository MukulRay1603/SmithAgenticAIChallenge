# LLM Provider Architecture

**File:** `orchestrator/llm_provider.py` · **Author:** Mukul Ray (Team Synapse, 2026)

Abstracts all LLM access behind a single `get_llm()` call with
automatic priority-ordered fallback. The system never fails hard
due to LLM unavailability.

---

## Fallback Chain

```
get_llm()
    │
    ├──► Groq (llama-3.3-70b-versatile)   ~1–2s  ← primary
    │         GROQ_API_KEY present?
    │
    ├──► OpenAI (gpt-4o-mini)             ~2–3s  ← fallback 1
    │         OPENAI_API_KEY present?
    │
    ├──► Anthropic (claude-3-5-haiku)     ~2–3s  ← fallback 2
    │         ANTHROPIC_API_KEY present?
    │
    ├──► Ollama (qwen2.5:7b)              ~5–10s ← offline fallback
    │         localhost:11434 reachable?
    │
    └──► None ──► deterministic-only mode  <1s
```

Priority order is configurable via a single env var:
```
CARGO_LLM_PRIORITY="groq,ollama,openai,anthropic"
```
No redeployment required. Takes effect immediately on next `get_llm()` call.

---

## Deterministic Fallback

When `get_llm()` returns `None`, every LLM node falls back silently:

| LLM node | Deterministic fallback |
|----------|----------------------|
| `plan_llm` | Tier templates |
| `reflect_llm` | 5-point checklist |
| `revise_llm` | GAP keyword scan |
| `observe_llm` | Error count check |

Full orchestration output is still produced. Response time drops
from ~12–15s to under 1 second.

---

## Ollama — Data Sovereignty Mode

For clients where data leaving the network is a compliance issue,
Ollama runs fully offline with no internet dependency. Detected
automatically by pinging `localhost:11434`. Model configurable
via `OLLAMA_MODEL` env var.

---

## Cache Invalidation

Provider instance is cached at module level. Invalidated when
`/api/llm/configure` is called — enabling hot-swap of credentials
and priority without server restart.
