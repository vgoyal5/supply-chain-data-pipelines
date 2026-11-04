"""Manhattan WMOS inventory ledger unit-of-measure & store key normalization.

Standardizes historical snapshots in `scm_manh_wmos.manh_wmos_inventory_ledgers`
and store identifiers in `scm_sap_s4_mm.sap_s4_mm_store_replenishment_orders`.
"""

from datetime import date
import re

SOURCE_LEDGER_TABLE = "scm_manh_wmos.manh_wmos_inventory_ledgers"
SOURCE_STORE_ORDERS_TABLE = "scm_sap_s4_mm.sap_s4_mm_store_replenishment_orders"

# Before 2023-03-06, Manhattan WMOS wrote `on_hand_qty`, `allocated_qty`, and
# `available_qty` in master cases (12 sellable eaches per case). Starting
# 2023-03-06, WMOS switched ledger snapshots to sellable eaches. Multiply all
# pre-2023-03-06 ledger quantities by 12 when comparing multi-year inventory.
LEDGER_CASE_PACK_CUTOVER = date(2023, 3, 6)
LEGACY_EACHES_PER_CASE = 12

_STORE_ID_RE = re.compile(r"^Store\s+(\d+)$")


def parse_store_number(store_id: str) -> int | None:
    """Extract integer store number from SAP S/4HANA string key `'Store <nbr>'`."""
    m = _STORE_ID_RE.match((store_id or "").strip())
    return int(m.group(1)) if m else None


def build_normalized_ledger_sql(project_id: str) -> str:
    """Return BigQuery SQL normalizing WMOS inventory ledgers to sellable eaches."""
    cutover = LEDGER_CASE_PACK_CUTOVER.isoformat()
    return f"""
SELECT
  l.ledger_id,
  l.dc_id,
  l.item_nbr,
  l.snapshot_date,
  CASE
    WHEN l.snapshot_date < DATE '{cutover}' THEN l.on_hand_qty * {LEGACY_EACHES_PER_CASE}
    ELSE l.on_hand_qty
  END AS on_hand_eaches,
  CASE
    WHEN l.snapshot_date < DATE '{cutover}' THEN l.allocated_qty * {LEGACY_EACHES_PER_CASE}
    ELSE l.allocated_qty
  END AS allocated_eaches,
  CASE
    WHEN l.snapshot_date < DATE '{cutover}' THEN l.available_qty * {LEGACY_EACHES_PER_CASE}
    ELSE l.available_qty
  END AS available_eaches
FROM `{project_id}.{SOURCE_LEDGER_TABLE}` AS l
""".strip()


def build_store_key_extract_sql() -> str:
    """SQL snippet extracting numeric `store_nbr` from `sap_s4_mm_store_replenishment_orders.store_id`."""
    return "SAFE_CAST(REGEXP_EXTRACT(store_id, r'^Store\\s+(\\d+)$') AS INT64)"
