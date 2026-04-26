# Triage Agent

**File:** `tools/triage_agent.py`  
**API:** `GET /api/triage/critical-shipments` · `POST /api/triage/rank`  
**Author:** Mukul Ray / Rahul Sharma (Team Synapse, 2026)

Ranks multiple at-risk shipments by urgency before any orchestration
decisions are made. Ensures the worst cases are handled first.

---

## Flow

```
shipment list (N shipments)
        │
        ▼
  enrich=True?
   ├── Yes ──► join scored_windows.csv
   │            hours_at_risk · peak_temp_c
   │            primary_breach_rule · breach density
   │
   └── No ──► skip join
        │
        ▼
  two-key sort
  ┌─────────────────────────────────────┐
  │ Key 1: tier priority                │
  │   CRITICAL=0, HIGH=1, MEDIUM=2, LOW=3│
  │ Key 2: fused_risk_score descending  │
  │         (tiebreaker within tier)    │
  └─────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────┬────────────────────────────────┐
  │  priority_list      │  recommended_orchestration_order│
  │  (all shipments)    │  (CRITICAL + HIGH only)         │
  └─────────────────────┴────────────────────────────────┘
```

---

## Why Triage Runs Before Orchestration

Without it, the orchestrator processes shipments in arbitrary order.
A CRITICAL shipment with 2 hours to breach should not queue behind a
HIGH shipment with 8 hours of margin.

Triage also prevents LLM rate-limit saturation — by sequencing
decisions rather than firing them in parallel.

---

## API Endpoints

`GET /api/triage/critical-shipments` — pulls worst CRITICAL/HIGH
window per shipment from the scored DataFrame, returns ranked queue.
Used by the dashboard batch orchestration trigger.

`POST /api/triage/rank` — ranks a caller-supplied shipment list.
Used when the caller already has a specific set in mind.
