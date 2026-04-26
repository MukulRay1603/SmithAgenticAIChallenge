# Route Agent

**File:** `tools/route_agent.py` · **Author:** Mukul Ray (Team Synapse, 2026)

Selects an alternative cold-chain route when a shipment is at risk.
Called by the orchestrator for CRITICAL/HIGH tiers at `air_handoff`
or `customs_clearance` transit phases.

---

## Selection Flow

```
product_id
    │
    ▼
temp class resolution
(frozen / refrigerated / crt)
    │
    ▼
candidate lookup (_ROUTE_TABLE)
    │
    ├─── LLM available? ──Yes──► LLM selects from candidates
    │                             (uses real Supabase route context:
    │                              origin, destination, carrier,
    │                              weather, delay probability)
    │                                    │
    └─── No / parse failure ─────────────┤
                                         ▼
                              rule-based selection
                              (urgency keywords → sort by ETA)
                                         │
                                         ▼
                              result dict
                              requires_approval: True (always)
```

---

## Temperature Class Taxonomy

| Class | Condition | Examples |
|-------|-----------|---------|
| `frozen` | `temp_high ≤ -15°C` | mRNA vaccines, cryogenic biologics |
| `refrigerated` | `temp_high ≤ 8°C` | Standard vaccines, biologics |
| `crt` | `temp_high > 8°C` | Controlled room temp products |

Routing by class (not product ID) keeps the route table stable as
new products are added.

---

## Key Design Decisions

**LLM is enrichment, not a dependency.** Every input combination
produces a valid output without LLM involvement.

**`requires_approval` is structurally always `True`.** Route changes
are operationally irreversible — the approval gate is not optional.

**LLM cannot invent routes.** It selects from the pre-validated
candidate list only. Output space stays bounded and auditable.

---

## Failure Modes

| Failure | Behaviour |
|---------|-----------|
| LLM unavailable / bad JSON | Rule-based fallback |
| Supabase unavailable | Proceeds without route enrichment |
| Unknown product ID | Defaults to `refrigerated` |
| Unknown transport mode | Falls back to `default` route key |
