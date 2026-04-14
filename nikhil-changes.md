# Session Changes — Cascading Execution, Context Assembly, Data Enrichment, Extended Scheduling & Extended Cold Storage

Summary of all changes made to the SmithAgenticAIChallenge repository in this session. Five areas were addressed: dynamic cascade execution in the orchestrator, a new context assembly layer for per-window enrichment, comprehensive rewrites of the reference data files, a full rebuild of the scheduling agent with feasibility checking, backup facility routing, appointment priority ranking, and downstream financial impact estimation, and a full rebuild of the cold storage agent with temperature compatibility scoring, proximity ranking, and structured facility selection.

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
| `notification_agent` | `revised_eta`, `spoilage_probability`, `facility_name` from cold storage result (if available); facility, advance notice hours, and temp range appended to message body |
| `cold_storage_agent` | `location_hint` back-filled from `ri.facility.airport_code` if absent; `hours_to_breach`, `avg_temp_c`, `temp_slope_c_per_hr` filled from risk input |
| `scheduling_agent` | `revised_eta`, real facility name and location from cascade or `ri.facility`; `advance_notice_required_hours` and `temp_range_supported` forwarded from cold storage result (audit context) |
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
- `cold_storage_agent`: now passes `location_hint` (from `ri.facility.airport_code` or `transit_phase`), `hours_to_breach`, `avg_temp_c`, and `temp_slope_c_per_hr` — previously only passed `product_id` and `urgency`
- `scheduling_agent`: resolves facility name and location from `ri.facility`; falls back to `"facility_TBD"` only when genuinely absent. Now also passes `delay_class`, `hours_to_breach`, `ml_spoilage_probability`, and `risk_tier` as proper schema fields (previously these were only embedded as text in the `reason` string)

#### Updated `_enrich_tool_input()` — scheduling_agent block

After the existing revised_eta and affected_facilities override, defensive fills ensure the four risk context fields are present even if `_build_tool_input` did not set them (guards prevent overwriting a value that was already placed by the baseline builder):

```python
if "delay_class" not in enriched:
    enriched["delay_class"] = ri.get("delay_class", "")
if "hours_to_breach" not in enriched:
    enriched["hours_to_breach"] = ri.get("hours_to_breach")
if "ml_spoilage_probability" not in enriched:
    enriched["ml_spoilage_probability"] = ri.get("ml_spoilage_probability", 0.0)
if "risk_tier" not in enriched:
    enriched["risk_tier"] = ri.get("risk_tier", "")
```

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

### `tools/scheduling_agent.py` — fully rewritten

The scheduling agent was rebuilt from a thin recommendation generator into a reasoning layer that evaluates feasibility, selects routing, ranks appointment priority, and estimates financial impact.

#### Problem

The previous implementation unconditionally selected the primary facility, always used the regular `contact` email regardless of timing, derived a binary `high/medium` patient impact from appointment count alone, and never consulted the `backup_facility` block in `facilities.json`. The rich data available — advance notice constraints, operating hours, capacity, emergency contacts, product cost data — was entirely unused.

#### New module-level additions

`product_costs.json` is now loaded at module level with the same process-lifetime cache pattern as `facilities.json`:

```python
_COSTS_PATH = Path(__file__).resolve().parent.parent / "data" / "product_costs.json"
_costs_cache: Optional[dict] = None

def _load_product_costs() -> dict: ...
```

A `_NO_BACKUP` sentinel constant prevents `KeyError` when a product has no `backup_facility` block defined.

#### New helper functions

**`_parse_any_time_window_open(operating_hours, local_dt) -> bool`**

Extracts all `HH:MM-HH:MM` pairs from the facility's `operating_hours` string using a regex and checks whether the given local time falls inside any of them. Day names are deliberately ignored for simplicity. Returns `True` if no operating hours are specified (open assumption). Used by `_check_facility_feasibility`.

**`_check_facility_feasibility(facility_record, revised_eta_iso, now_dt) -> dict`**

Evaluates whether a facility can accept a delivery at the revised ETA. Works identically for primary and backup records — both have the same field schema.

Logic:
1. `advance_notice_hours = (revised_eta − now).total_seconds() / 3600`
2. `advance_notice_deficit_hours = advance_notice_hours − min_advance_notice_hours`
3. `capacity_flag = current_occupancy_pct > 85`
4. After-hours: converts `now_dt` to facility local time via `ZoneInfo(timezone)`, runs `_parse_any_time_window_open`. Skipped if `pharmacist_on_site_24h` is True.
5. Contact selection: if `after_hours_flag` or notice is short → use `emergency_contact` + `emergency_phone`, mode = `"emergency"`. Otherwise use regular `contact`, mode = `"standard"`.
6. `feasible = notice_ok OR accepts_emergency_delivery`. Capacity flag is a warning, not a hard block.

Return dict keys: `feasible`, `routing_reason`, `advance_notice_hours`, `advance_notice_deficit_hours`, `contact_to_use`, `phone_to_use`, `contact_mode`, `capacity_flag`, `capacity_pct`, `after_hours_flag`, `after_hours_note`

**`_rank_appointment_priority(product_cost_data, hours_to_breach) -> dict`**

Computes an appointment priority tier from three signals pulled from `product_costs.json`:

| Signal | Source |
|---|---|
| `downstream_disruption_per_appointment_usd` | Normalised by $8,500 (P04 ceiling) |
| `cold_chain_risk_multiplier` | Product sensitivity weight (1.0–2.5) |
| `hours_to_breach` urgency amplifier | `<4h → 3×`, `<12h → 2×`, else `1×` |

`score = (disruption_usd / 8500) × multiplier × urgency_factor`

| Score | Priority tier |
|---|---|
| ≥ 2.0 | `critical` |
| ≥ 1.0 | `high` |
| ≥ 0.4 | `medium` |
| < 0.4 | `routine` |

Return dict keys: `priority_tier`, `priority_score`, `priority_reason`

**`_resolve_facility_routing(primary_record, backup_record, feasibility_primary, feasibility_backup) -> dict`**

Determines routing from the two feasibility results:

| Condition | Decision |
|---|---|
| Both infeasible | `no_feasible_option` |
| Both feasible + primary capacity flag + backup has appointments | `split` |
| Both feasible, no capacity issue | `primary` |
| Only primary feasible | `primary` |
| Only backup feasible | `backup` |

Return dict keys: `routing_decision`, `routing_summary`

#### Expanded `SchedulingInput`

Five Optional fields added after `reason`. All default to `None` for full backward compatibility with existing callers:

```python
container_id: Optional[str]            # audit traceability
delay_class: Optional[str]             # negligible | developing | critical
hours_to_breach: Optional[float]       # hours until temperature breach
ml_spoilage_probability: Optional[float]  # 0.0–1.0
risk_tier: Optional[str]               # LOW | MEDIUM | HIGH | CRITICAL
```

#### Rewritten `_execute()`

Step-by-step execution:
1. Load facilities + product costs; resolve `facility_record`, `backup_record`, `cost_record`
2. `feasibility_primary = _check_facility_feasibility(facility_record, revised_eta, now_dt)`
3. `feasibility_backup = _check_facility_feasibility(backup_record, ...) if backup_record else _NO_BACKUP`
4. `routing = _resolve_facility_routing(...)` — determines which facility records are active
5. `priority = _rank_appointment_priority(cost_record, hours_to_breach)`
6. `financial_impact_usd = disruption_per_appt × appointment_count × spoilage_prob`
7. `compliance_flags` collected from facility-level fields: `chain_of_custody_required`, `regulatory_release_required`, `patient_registry_required`, `blood_product_registry_required`
8. `active_records` selected based on `routing_decision`; one recommendation dict built per active facility
9. `actions_required` list constructed from compliance flags, after-hours flags, routing decision, spoilage risk, and capacity flags
10. `summary_line` string assembled: `[TIER] product — routing_summary | Priority: tier | Est. downstream impact: $X | Replacement lead time: Xd expedited`

#### Backward compatibility

All existing outer return keys preserved: `tool`, `status`, `shipment_id`, `product_id`, `reason`, `facility_recommendations`, `total_appointments_affected`, `note`, `requires_approval`, `timestamp`.

All existing per-recommendation keys preserved: `facility`, `facility_contact`, `action`, `appointment_count`, `original_eta`, `revised_eta`, `patient_impact`, `notification_sent`.

All new keys are additive. The `approval_workflow` and any other downstream consumer that reads the existing structure is unaffected.

#### New additive outer keys

`container_id`, `routing_decision`, `routing_summary`, `priority_tier`, `priority_score`, `priority_reason`, `financial_impact_estimate_usd`, `ml_spoilage_probability`, `delay_class`, `hours_to_breach`, `risk_tier`, `compliance_flags`, `actions_required`, `summary_line`, `substitute_available`, `replacement_lead_time_days`, `expedited_lead_time_days`, `cascade_suggested_facilities`

#### New additive per-recommendation keys

`facility_id`, `facility_city`, `facility_country`, `airport_code`, `contact_mode`, `phone`, `advance_notice_hours`, `advance_notice_deficit_hours`, `capacity_pct`, `capacity_flag`, `after_hours_flag`, `after_hours_note`, `feasibility_reason`, `cold_chain_validated`, `certifications`

---

### `tools/cold_storage_agent.py` — fully rewritten

The cold storage agent was rebuilt from a random stub into a scored, data-driven facility selector.

#### Problem

The previous implementation called `random.choice(FACILITIES)` on a hardcoded list of four fictional facilities that had no relationship to `data/facilities.json`. All three meaningful inputs — `product_id`, `location_hint`, `urgency` — were accepted but ignored. The output (`recommended_facility`, `location`) fed directly into `notification_agent` and `scheduling_agent` in the CRITICAL cascade, meaning both downstream tools were building on a random result.

#### New module-level additions

`facilities.json` and `product_profiles.json` are now loaded with process-lifetime caches following the same pattern as `scheduling_agent.py`:

```python
_FACILITIES_PATH = Path(__file__).resolve().parent.parent / "data" / "facilities.json"
_PROFILES_PATH   = Path(__file__).resolve().parent.parent / "data" / "product_profiles.json"

_facilities_cache: Optional[dict] = None
_profiles_cache:   Optional[dict] = None

def _load_facilities() -> dict: ...
def _load_profiles() -> dict:    # calls load_product_profiles(_PROFILES_PATH) from src.data_loader
```

The hardcoded `FACILITIES` list was deleted.

#### New helper functions

**`_parse_temp_range(range_str) -> tuple[float, float]`**

Parses `temp_range_supported` strings from `facilities.json` into `(low, high)` float tuples. Handles two formats present in the data:

| Input | Output |
|---|---|
| `"2-8C"`, `"15-25C"` | `(2.0, 8.0)`, `(15.0, 25.0)` |
| `"-80C to -15C"`, `"-80C to -20C"` | `(-80.0, -15.0)`, `(-80.0, -20.0)` |

Three-pass logic: (1) "TO"-separated split for negative ranges, (2) dash-separated split for positive ranges, (3) regex fallback `re.findall(r"-?\d+(?:\.\d+)?", ...)`. Returns `(-999.0, 999.0)` if all passes fail.

**`_check_temp_compatibility(facility_record, product_id, profiles) -> dict`**

Hard gate: facility is compatible iff `fac_low ≤ prod_low AND fac_high ≥ prod_high`.

Critical edge case — P04 backup (EWR): supports `-80C to -20C`; P04 product requires `-25C to -15C`. Check: `fac_high=-20 ≥ prod_high=-15` evaluates to `False` → **incompatible → disqualified**. P04 primary (JFK) supports `-80C to -15C` → `fac_high=-15 ≥ -15` → compatible.

Return dict keys: `compatible`, `facility_range`, `required_range`, `compatibility_note`

**`_score_facility(facility_record, product_id, location_hint, hours_to_breach, urgency, profiles) -> dict`**

Computes a suitability score for a single facility candidate. Two hard disqualification gates checked first:

1. Temperature incompatibility → `disqualification_reason: "temperature_incompatible"`
2. `urgency == "critical"` and `accepts_emergency_delivery == False` → `disqualification_reason: "no_emergency_delivery"`

If both gates pass, a weighted composite score is computed:

| Sub-score | Formula | Weight |
|---|---|---|
| Capacity | `(100 − occupancy_pct) / 100` | 0.4 |
| Proximity | 1.0 exact airport match, 0.5 city/string partial, 0.0 none | 0.3 |
| Notice window | `min(hours_to_breach / min_advance_notice_hours, 1.0)` | 0.2 |
| Certifications | `min(0.5 + (len(certs) − 1) × 0.1, 1.0)` | 0.1 |

Urgency amplifier on capacity (mirrors `_rank_appointment_priority`): if `hours_to_breach < 4.0` → `capacity_score = min(capacity_score × 1.5, 1.0)`.

Tier thresholds: `≥0.75 → ideal`, `≥0.50 → good`, `≥0.25 → acceptable`, else `last_resort`.

Return dict keys: `suitability_score`, `suitability_tier`, `suitability_reason`, `disqualified`, `disqualification_reason`, `temp_compatibility`

**`_build_candidate_list(product_id, location_hint, hours_to_breach, urgency, profiles) -> list`**

Loads `facilities.json[product_id]`, extracts primary (strips `backup_facility` key, tags `_candidate_role="primary"`) and backup (tags `_candidate_role="backup"`), scores each with `_score_facility()`, and sorts by `(disqualified_bool, -suitability_score)` — viable candidates first, then by score descending. Returns empty list if `product_id` not found.

#### Expanded `ColdStorageInput`

Three Optional fields added after `urgency`. All default to `None` for full backward compatibility:

```python
hours_to_breach:     Optional[float]  # hours until temp breach at current slope
avg_temp_c:          Optional[float]  # current average container temp °C
temp_slope_c_per_hr: Optional[float]  # temperature trend slope °C/hr
```

#### Rewritten `_execute()`

Step-by-step execution:
1. `candidates = _build_candidate_list(product_id, location_hint, hours_to_breach, urgency, profiles)`
2. `primary_rec = candidates[0]`; `alt_facilities = candidates[1:]`
3. `transfer_window_hours = round(hours_to_breach × 0.8, 2)` — 20% safety margin before breach
4. `compliance_flags` collected from facility fields: `chain_of_custody_required`, `regulatory_release_required`, `patient_registry_required`, `blood_product_registry_required`
5. `selection_rationale` built; prefixed with `WARNING:` if all candidates disqualified
6. `alternative_facilities` array of slim dicts — one per non-primary candidate

#### Backward compatibility

All existing outer return keys preserved: `tool`, `status`, `shipment_id`, `container_id`, `product_id`, `recommended_facility`, `location`, `available_capacity_pct`, `temp_range`, `urgency`, `requires_approval`, `timestamp`.

All new keys are additive: `recommended_facility_id`, `temp_range_supported`, `certifications`, `contact`, `emergency_phone`, `advance_notice_required_hours`, `transfer_window_hours`, `suitability_score`, `suitability_tier`, `alternative_facilities`, `selection_rationale`, `compliance_flags`, `temp_compatibility`, `all_candidates_disqualified`, `avg_temp_c`, `temp_slope_c_per_hr`, `hours_to_breach`.

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

### 3. Scheduling agent (unit level)

Verify feasibility checking, priority ranking, and the full tool invocation:

```python
from tools.scheduling_agent import _rank_appointment_priority, _check_facility_feasibility
from datetime import datetime, timezone, timedelta
import json, pathlib

costs = json.loads(pathlib.Path("data/product_costs.json").read_text())
facs  = json.loads(pathlib.Path("data/facilities.json").read_text())

# Priority: P04 at 2.5h to breach should score critical
r = _rank_appointment_priority(costs["P04"], hours_to_breach=2.5)
assert r["priority_tier"] == "critical"

# Priority: P03 with stable temperature should score routine
r = _rank_appointment_priority(costs["P03"], hours_to_breach=None)
assert r["priority_tier"] in ("routine", "medium")

# Feasibility: P04 with 4h notice (12h required) — short notice but emergency accepted
now = datetime(2026, 4, 13, 9, 0, 0, tzinfo=timezone.utc)
eta = (now + timedelta(hours=4)).isoformat()
r = _check_facility_feasibility(facs["P04"], eta, now)
assert r["feasible"] is True
assert r["contact_mode"] == "emergency"    # short notice forces emergency contact
assert r["advance_notice_deficit_hours"] < 0

# Feasibility: P01 with 6h notice during business hours — standard contact
eta_ok = (now + timedelta(hours=6)).isoformat()
r = _check_facility_feasibility(facs["P01"], eta_ok, now)
assert r["feasible"] is True
assert r["contact_mode"] == "standard"

# Full tool invocation with all cascade context fields
from tools import TOOL_MAP
result = TOOL_MAP["scheduling_agent"].invoke({
    "shipment_id": "SHP-TEST-001",
    "container_id": "CTR-TEST-001",
    "product_id": "P04",
    "affected_facilities": ["CryoMed (JFK)"],
    "original_eta": "2025-01-15T10:00:00+00:00",
    "revised_eta": "2025-01-15T12:00:00+00:00",
    "reason": "Cryogenic breach during air handoff.",
    "delay_class": "critical",
    "hours_to_breach": 2.0,
    "ml_spoilage_probability": 0.88,
    "risk_tier": "CRITICAL",
})
assert result["routing_decision"] in ("primary", "backup", "split", "no_feasible_option")
assert result["priority_tier"] in ("critical", "high")
assert isinstance(result["actions_required"], list)
assert "summary_line" in result
assert result["compliance_flags"] == ["chain_of_custody_required", "regulatory_release_required"]
# P04: $8500/appt × 8 appts × 0.88 spoilage = $59,840
assert result["financial_impact_estimate_usd"] == 59840.0
# Backward compat
rec = result["facility_recommendations"][0]
for key in ("facility", "facility_contact", "action", "appointment_count",
            "original_eta", "revised_eta", "patient_impact", "notification_sent"):
    assert key in rec
```

---

### 4. Cold storage agent (unit level)

Verify temperature parsing, compatibility checking, and the full scored selection:

```python
from tools.cold_storage_agent import _parse_temp_range, _check_temp_compatibility, _load_profiles
import json

profiles = _load_profiles()
with open("data/facilities.json") as f:
    facs = json.load(f)

# Temperature range parsing
assert _parse_temp_range("2-8C")          == (2.0, 8.0)
assert _parse_temp_range("15-25C")        == (15.0, 25.0)
assert _parse_temp_range("-80C to -15C")  == (-80.0, -15.0)
assert _parse_temp_range("-80C to -20C")  == (-80.0, -20.0)

# P04 primary (JFK): -80 to -15C, product requires -25 to -15C → compatible
r = _check_temp_compatibility(facs["P04"], "P04", profiles)
assert r["compatible"] is True

# P04 backup (EWR): -80 to -20C, fac_high=-20 < prod_high=-15 → incompatible
r = _check_temp_compatibility(facs["P04"]["backup_facility"], "P04", profiles)
assert r["compatible"] is False

# Full tool invocation — CRITICAL P04 at JFK
from tools import TOOL_MAP
result = TOOL_MAP["cold_storage_agent"].invoke({
    "shipment_id": "SHP-TEST",
    "container_id": "CTR-TEST",
    "product_id": "P04",
    "location_hint": "JFK",
    "urgency": "critical",
    "hours_to_breach": 3.0,
    "avg_temp_c": -12.0,
    "temp_slope_c_per_hr": 0.5,
})
assert result["recommended_facility"] == "CryoMed Advanced Biologics Receiving Centre"
assert result["suitability_tier"] in ("ideal", "good", "acceptable", "last_resort")
assert isinstance(result["alternative_facilities"], list)
assert "temp_compatibility" in result
# P04 backup is temperature-incompatible — should appear as disqualified in alternatives
assert result["alternative_facilities"][0]["disqualified"] is True
assert result["alternative_facilities"][0]["disqualification_reason"] == "temperature_incompatible"
# transfer_window = hours_to_breach × 0.8
assert result["transfer_window_hours"] == 2.4
# Backward compat keys
for key in ("recommended_facility", "location", "available_capacity_pct",
            "temp_range", "urgency", "requires_approval", "timestamp"):
    assert key in result

# Unknown product → no_facility_data status
r2 = TOOL_MAP["cold_storage_agent"].invoke({
    "shipment_id": "SHP-X", "container_id": "CTR-X", "product_id": "P99",
})
assert r2["status"] == "no_facility_data"
```

---

### 5. Individual tool invocations

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

### 6. Full orchestrator cascade (no API required)

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

### 7. API end-to-end

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
| `scheduling_agent` `routing_decision` is set (not absent) | `actions_taken[scheduling_agent].result.routing_decision` |
| `scheduling_agent` `priority_tier` reflects product and breach timing | `actions_taken[scheduling_agent].result.priority_tier` |
| `scheduling_agent` shows real facility name, not `facility_TBD` | `actions_taken[scheduling_agent].result.facility_recommendations[0].facility` |
| `scheduling_agent` `contact_mode` is `"emergency"` when notice is short | `actions_taken[scheduling_agent].result.facility_recommendations[0].contact_mode` |
| `scheduling_agent` `compliance_flags` populated for P04/P05/P06 | `actions_taken[scheduling_agent].result.compliance_flags` |
| `scheduling_agent` `financial_impact_estimate_usd` is non-zero | `actions_taken[scheduling_agent].result.financial_impact_estimate_usd` |
| Compliance `log_id` appears in insurance `supporting_evidence` | Compare `actions_taken[0].result.log_id` vs `actions_taken[4].result.supporting_evidence` |
| `approval_id` is set and non-null | `decision.approval_id` |
| `delay_ratio`, `delay_class`, `hours_to_breach` present in API response | `GET /api/risk/score-window/<id>` response body |
| `cold_storage_agent` selects real facility from `facilities.json`, not hardcoded stub | `actions_taken[cold_storage_agent].result.recommended_facility` |
| `cold_storage_agent` `suitability_tier` is set and facility was scored | `actions_taken[cold_storage_agent].result.suitability_tier` |
| P04 backup (EWR) appears as disqualified in `alternative_facilities` | `actions_taken[cold_storage_agent].result.alternative_facilities[0].disqualification_reason == "temperature_incompatible"` |
| `notification_agent` message includes advance notice hours from cold storage | Message body contains `"Advance notice required: Xh."` |
| `notification_agent` message includes temp range from cold storage | Message body contains `"Storage range: ..."` |
| `cold_storage_agent` `transfer_window_hours` equals `hours_to_breach × 0.8` | `actions_taken[cold_storage_agent].result.transfer_window_hours` |
