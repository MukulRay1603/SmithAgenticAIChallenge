# Session Changes — Cascading Execution, Context Assembly & Data Enrichment

Summary of all changes made to the SmithAgenticAIChallenge repository in this session. Three areas were addressed: dynamic cascade execution in the orchestrator, a new context assembly layer for per-window enrichment, and comprehensive rewrites of the reference data files.

---

## New Files

### `src/context_assembler.py`

A new module that assembles a fully enriched context object for a single scored window before it enters the orchestrator. Previously, the orchestrator received only raw CSV columns from the risk engine output; this module computes the additional fields needed for cascade execution.

**Key functions:**

| Function | Description |
|---|---|
| `build_window_context(window_id, df, profiles)` | Main entry point — merges the scored row with product profile, facility data, and product costs into a single dict |
| `compute_delay_ratio(current_delay_min, max_excursion_min)` | Computes `current_delay / product_tolerance` |
| `compute_delay_class(delay_ratio)` | Returns `negligible` (<0.5×), `developing` (0.5–1.0×), or `critical` (>1.0×) |
| `compute_hours_to_breach(avg_temp_c, slope, temp_low, temp_high)` | Estimates time until temperature crosses the nearest boundary at the current slope; returns `None` if temperature is stable or moving away from the boundary |

The returned context includes all raw telemetry columns, risk scores, product profile limits, the three derived cascade fields, and the full `facility` and `product_cost` dicts — so downstream tools do not need to reload data files individually.

---

## Modified Files

### `orchestrator/state.py`

Added `cascade_context: Dict[str, Any]` to `OrchestratorState`. This field accumulates each tool's result during execution, keyed by tool name, and is returned in the final output for inspection and audit.

---

### `orchestrator/nodes.py`

The most significant change in the session.

#### Problem

The original `execute()` used tool inputs that were pre-baked during `plan()` — before any tool had run. This meant later tools had no awareness of what earlier tools found. Additionally, execution halted when `approval_workflow` was reached, so insurance, scheduling, and other downstream tools never ran for CRITICAL shipments.

#### New functions

**`_compute_revised_eta(ri) -> Optional[str]`**

Adds `current_delay_min` (as a `timedelta`) to `window_end` and returns an ISO-format revised ETA string. Used to enrich notification and scheduling inputs.

**`_enrich_tool_input(tool_name, base_input, cascade_ctx, ri) -> dict`**

Called immediately before each `tool.invoke()`. Patches the baseline input using results accumulated in `cascade_ctx` from earlier tools in the same run:

| Tool | Injected fields |
|---|---|
| `notification_agent` | `revised_eta`, `spoilage_probability`, `facility_name` from cold storage result (if available); facility appended to message body |
| `scheduling_agent` | `revised_eta`, real facility name and location from cascade or `ri.facility` |
| `insurance_agent` | `supporting_evidence` containing compliance `log_id`; pre-computed `estimated_loss_usd` using the itemised loss formula |
| `approval_workflow` | `proposed_actions` replaced with actual `tool: status` summaries from all prior steps |

#### Rewritten `execute()`

- `cascade_ctx` accumulates every tool result as execution proceeds
- `_enrich_tool_input()` is called before each invocation
- `approval_workflow` queues an approval ID and continues — it no longer causes an early return
- Tool failures are caught, logged, and recorded; they do not abort the remaining steps
- `cascade_context` is returned as part of the state update

#### Updated `TIER_PLAN_TEMPLATES`

| Tier | Execution plan |
|---|---|
| CRITICAL | compliance → notification → cold_storage → scheduling → insurance → approval |
| HIGH | compliance → notification → scheduling → approval |
| MEDIUM | compliance → notification |
| LOW | — |

Insurance was previously appended conditionally after plan generation. It is now a fixed step in the CRITICAL template.

#### Updated `_build_tool_input()`

- Reads `delay_class` and `hours_to_breach` from the enriched `risk_input`
- Builds a `context_suffix` (`~X.Xh to breach. Delay: <class>.`) appended to messages and incident summaries
- `notification_agent`: includes `spoilage_probability` and `facility_name` from `ri.facility`
- `insurance_agent`: includes `leg_id` and `spoilage_probability`
- `scheduling_agent`: resolves facility name and location from `ri.facility`; falls back to `"facility_TBD"` only when genuinely absent

---

### `tools/notification_agent.py`

Added three optional cascade-enriched fields to `NotificationInput`:

```python
revised_eta: Optional[str]             # ISO datetime — window_end + current_delay_min
spoilage_probability: Optional[float]  # ML spoilage probability (0–1)
facility_name: Optional[str]           # Destination or backup facility name from cascade
```

`_execute()` now constructs a structured `alert_payload` dict rather than forwarding the message string alone. The output includes `alert_payload` (with all enriched fields present) and `message_preview`.

---

### `tools/scheduling_agent.py`

- `facilities.json` loaded once at module level with a process-lifetime cache
- `revised_eta: Optional[str]` added to `SchedulingInput`
- `_execute()` looks up the product's facility record to obtain `appointment_count` and `facility_contact`
- `patient_impact` is derived as `"high"` when appointment count ≥ 10 and a revised ETA is present, `"medium"` otherwise
- Output includes `total_appointments_affected` and `facility_contact`

---

### `tools/insurance_agent.py`

Three new internal functions were added.

**`_aggregate_leg_history(leg_id) -> dict`**
Reads `artifacts/scored_windows.csv`, filters to the given leg, and computes:
- `total_excursion_min` — cumulative minutes outside temperature range
- `peak_temp_c` — highest recorded average temperature
- `window_count`, `windows_in_breach`
- `breach_timeline` — last 10 breached windows (window ID, temperature, rules fired)

**`_compute_loss_breakdown(product_id, spoilage_probability, appointment_count=0) -> dict`**
Itemised loss estimate:

| Component | Formula |
|---|---|
| `product_loss_usd` | `unit_cost × units × spoilage_prob` |
| `disposal_cost_usd` | `disposal_per_unit × units × spoilage_prob` |
| `downstream_disruption_usd` | `disruption_per_appointment × appointments × spoilage_prob` |
| `handling_cost_usd` | Sunk cost — included at full value regardless of outcome |
| `total_estimated_loss_usd` | Sum of all components × `cold_chain_risk_multiplier` |

**`_compute_loss(product_id, spoilage_probability) -> float`**
Backward-compatible single-float wrapper for `_compute_loss_breakdown()`.

`InsuranceInput` updated with `leg_id: Optional[str]` and `spoilage_probability: Optional[float]`.

`_execute()` updated to call `_aggregate_leg_history()` and `_compute_loss_breakdown()` and to load `regulatory_class`, `therapeutic_area`, and the `replacement` block from `product_costs.json`. Claim output now includes: `product_name`, `regulatory_class`, `therapeutic_area`, `loss_breakdown`, `replacement_lead_time_days`, `expedited_lead_time_days`, `substitute_available`, and `next_steps` with concrete lead-time values.

---

### `backend/app.py`

Added imports:

```python
from src.context_assembler import build_window_context
from src.data_loader import load_product_profiles
```

Added `_profiles` cache with `_get_profiles()` loader.

The `/api/risk/score-window/{window_id}` endpoint now calls `build_window_context()` instead of performing a raw CSV row lookup. The response includes the full set of cascade context fields:

```
delay_ratio, delay_class, hours_to_breach, current_delay_min,
facility, product_cost, window_end
```

---

## Data Files

### `data/facilities.json` — fully rewritten

Product-keyed (P01–P06). Each product now has a `primary` and `backup_facility` block.

Top-level flat fields retained for backward compatibility: `name`, `location`, `contact`, `appointment_count`.

Additional fields per facility block:
- Identity: `id`, `role`, `full_address`, `city`, `country`, `airport_code`, `timezone`, `operating_hours`
- Contacts: `emergency_contact`, `emergency_phone`
- Certifications: `GDP`, `WHO-PQ`, `FDA-21CFR`, `IATA-CEIV-Pharma`, `AABB`, etc.
- Capacity: `storage_capacity_units`, `current_occupancy_pct`, `temp_range_supported`
- Operational flags: `accepts_emergency_delivery`, `min_advance_notice_hours`, `receiving_dock_temp_controlled`, `pharmacist_on_site_24h`, `cold_chain_validated_receiving`
- Product-specific flags where applicable: `licensed_blood_bank`, `licensed_radiopharmacy`, `cryo_storage_available`

Appointment counts revised to realistic values: P01=120, P02=34, P03=180, P04=8, P05=45, P06=72.

### `data/product_costs.json` — fully rewritten

Product-keyed (P01–P06).

Top-level fields retained for backward compatibility: `unit_cost_usd`, `units_per_shipment`, `currency`.

New top-level fields: `product_name`, `regulatory_class`, `cold_chain_category`, `who_atc_code`, `therapeutic_area`, `shipment_value_usd`.

**`cost_components` block:** `handling_cost_per_shipment_usd`, `disposal_cost_per_unit_usd`, `testing_cost_per_batch_usd`, `regulatory_release_cost_usd`, `emergency_resupply_surcharge_usd`

**`downstream_impact` block:** `downstream_disruption_per_appointment_usd`, `disruption_description`, `critical_patient_segments`

**`replacement` block:** `lead_time_days`, `expedited_lead_time_days`, `expedited_premium_pct`, `substitute_available`, `substitute_notes`

**`product_characteristics` block:** `shelf_life_days`, `cold_chain_risk_multiplier`, `controlled_substance`, `biological_product`, `storage_condition_label`

Cold chain risk multipliers: P01=1.2, P02=1.5, P03=1.0, P04=2.5, P05=1.8, P06=1.4. These scale the total estimated loss and differentiate between a delayed insulin shipment and a delayed cryogenic cell therapy.

Unit costs revised for clinical accuracy: P01=$45, P02=$850, P03=$15, P04=$3,800, P05=$380, P06=$210.

Estimated total loss at 100% spoilage:

| Product | Total estimated loss |
|---|---|
| P03 — CRT insulin | ~$17,180 |
| P01 — Monoclonal antibody | ~$138,420 |
| P06 — Oncology agent | ~$202,440 |
| P02 — Lyophilised biologic | ~$322,500 |
| P05 — Cell therapy | ~$423,720 |
| P04 — Cryogenic CAR-T | ~$666,875 |

---

## Testing Guide

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Generate the scored dataset — required before anything else
python pipeline.py train
# Output: artifacts/scored_windows.csv, artifacts/xgb_spoilage.joblib
```

---

### 1. Context assembler (unit level)

Verify that `build_window_context()` computes the cascade fields correctly:

```python
import pandas as pd
import src.context_assembler as ca

df = pd.read_csv("artifacts/scored_windows.csv")
window_id = df[df["risk_tier"] == "CRITICAL"].iloc[0]["window_id"]

ctx = ca.build_window_context(window_id, df, {})
print(f"delay_class={ctx['delay_class']}, hours_to_breach={ctx['hours_to_breach']}")
# Expect a non-empty facility dict and product_cost dict
assert ctx["delay_class"] in ("negligible", "developing", "critical")
assert isinstance(ctx["facility"], dict)
assert isinstance(ctx["product_cost"], dict)
```

---

### 2. Insurance loss formula (unit level)

Verify itemised breakdown and multipliers across all products:

```python
from tools.insurance_agent import _compute_loss_breakdown

for pid in ["P01", "P02", "P03", "P04", "P05", "P06"]:
    b = _compute_loss_breakdown(pid, spoilage_probability=1.0)
    print(f"{pid}: ${b['total_estimated_loss_usd']:,.2f}  multiplier={b['risk_multiplier']}")

# Expected order: P03 lowest (~$17k), P04 highest (~$667k)
```

---

### 3. Individual tool invocations

Each tool can be tested in isolation without starting the orchestrator or API:

```python
from tools import TOOL_MAP

# Test notification with cascade-enriched fields
result = TOOL_MAP["notification_agent"].invoke({
    "shipment_id": "SHP-001",
    "container_id": "CTR-001",
    "risk_tier": "CRITICAL",
    "recipients": ["ops_team", "management"],
    "message": "Temperature breach detected.",
    "revised_eta": "2025-01-15T14:30:00+00:00",
    "spoilage_probability": 0.87,
    "facility_name": "Memorial Medical Center",
})
assert result["status"] == "notification_queued"
assert "spoilage_probability_pct" in result["alert_payload"]

# Test insurance with leg excursion aggregation
result = TOOL_MAP["insurance_agent"].invoke({
    "shipment_id": "SHP-001",
    "container_id": "CTR-001",
    "product_id": "P04",
    "risk_tier": "CRITICAL",
    "incident_summary": "Cryogenic temperature breach during air handoff.",
    "leg_id": "LEG-001",   # must exist in scored_windows.csv
    "spoilage_probability": 0.9,
})
assert "loss_breakdown" in result
assert result["loss_breakdown"]["risk_multiplier"] == 2.5
```

---

### 4. Full orchestrator cascade (no API required)

The most complete integration test — exercises the entire interpret → plan → reflect → execute chain:

```python
import pandas as pd
from src.context_assembler import build_window_context
from src.data_loader import load_product_profiles
from orchestrator.graph import run_orchestrator

df = pd.read_csv("artifacts/scored_windows.csv")
profiles = load_product_profiles()

window_id = df[df["risk_tier"] == "CRITICAL"].iloc[0]["window_id"]
ctx = build_window_context(window_id, df, profiles)

risk_input = {
    "shipment_id":  ctx["shipment_id"],
    "container_id": ctx["container_id"],
    "window_id":    ctx["window_id"],
    "leg_id":       ctx["leg_id"],
    "product_type": ctx["product_id"],
    "transit_phase": ctx["transit_phase"],
    "window_end":   ctx["window_end"],
    "risk_tier":    ctx["risk_tier"],
    "fused_risk_score":      ctx["final_score"],
    "ml_spoilage_probability": ctx["ml_score"],
    "deterministic_rule_flags": ctx["det_rules_fired"],
    "key_drivers": [],
    "delay_ratio":      ctx["delay_ratio"],
    "delay_class":      ctx["delay_class"],
    "hours_to_breach":  ctx["hours_to_breach"],
    "current_delay_min": ctx["current_delay_min"],
    "facility":     ctx["facility"],
    "product_cost": ctx["product_cost"],
}

decision = run_orchestrator(risk_input)

tools_run = [a["tool"] for a in decision["actions_taken"]]
print("Tools executed:", tools_run)

# For CRITICAL tier, all 6 steps should run
assert len(tools_run) >= 5, "Expected 5+ tools for CRITICAL"
assert "compliance_agent"  in tools_run
assert "notification_agent" in tools_run
assert "insurance_agent"   in tools_run
assert "approval_workflow" in tools_run

# Verify cascade enrichment reached insurance
ins = next(a["result"] for a in decision["actions_taken"] if a["tool"] == "insurance_agent")
assert ins.get("estimated_loss_usd", 0) > 0
assert "loss_breakdown" in ins
print(f"Estimated loss: ${ins['estimated_loss_usd']:,.2f}")

# Verify notification received spoilage probability
notif = next(a["result"] for a in decision["actions_taken"] if a["tool"] == "notification_agent")
assert "spoilage_probability_pct" in notif.get("alert_payload", {})

# Verify approval was queued but didn't block the chain
assert decision.get("approval_id") is not None
```

---

### 5. API end-to-end

Start the backend:

```bash
uvicorn backend.app:app --reload --port 8000
```

Sequence of calls to exercise the full stack:

```bash
# 1. Find CRITICAL windows
curl "http://localhost:8000/api/windows?risk_tier=CRITICAL&limit=5"

# 2. Verify enriched context output from context_assembler
curl http://localhost:8000/api/risk/score-window/<window_id>
# Response should include: delay_ratio, delay_class, hours_to_breach, facility, product_cost

# 3. Run full orchestration cascade
curl -X POST http://localhost:8000/api/orchestrator/run/<window_id>
# Response: actions_taken with 5–6 entries for CRITICAL, approval_id set

# 4. Check the approval queue
curl http://localhost:8000/api/approvals/pending

# 5. Approve the queued action
curl -X POST http://localhost:8000/api/approvals/<approval_id>/decide \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "decided_by": "ops_manager"}'

# 6. Review the audit log
curl "http://localhost:8000/api/audit-logs?risk_tier=CRITICAL&limit=10"
```

---

### Key assertions per test area

| Assertion | Where to check |
|---|---|
| All 6 tools ran for CRITICAL (approval did not halt the chain) | `decision.actions_taken` — length ≥ 5 |
| `notification_agent` alert has `spoilage_probability_pct` | `actions_taken[notification_agent].result.alert_payload` |
| `insurance_agent` loss breakdown has correct `risk_multiplier` | `actions_taken[insurance_agent].result.loss_breakdown` |
| `scheduling_agent` shows real facility name, not `facility_TBD` | `actions_taken[scheduling_agent].result.facility_recommendations[0].facility` |
| Compliance `log_id` appears in insurance `supporting_evidence` | Compare `actions_taken[0].result.log_id` vs `actions_taken[4].result.supporting_evidence` |
| `approval_id` is set and non-null | `decision.approval_id` |
| `delay_ratio`, `delay_class`, `hours_to_breach` present in API response | `GET /api/risk/score-window/<id>` response body |
