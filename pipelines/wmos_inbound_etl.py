"""Manhattan WMOS inbound dock receipt normalization pipeline.

Normalizes raw dock scan events in `scm_manh_wmos.manh_wmos_inbound_receipts`
before downstream vendor OTIF, receiving accuracy, and putaway backlog queries.
"""

from datetime import date

SOURCE_RECEIPTS_TABLE = "scm_manh_wmos.manh_wmos_inbound_receipts"
CARRIER_SEED_PATH = "seeds/carrier_aliases.csv"

# Prior to 2024-03-25 (WMOS parser v1.8 rollout), the legacy EDI 856 ASN/dock
# adapter wrote `received_qty` and `damaged_qty` as fixed-point centi-units
# (100x sellable eaches, e.g. 100 eaches stored as 10000.0). From 2024-03-25
# onward, quantities are stored directly in sellable eaches (1x).
EDI_856_CENTIUNIT_CUTOVER = date(2024, 3, 25)
LEGACY_CENTIUNIT_DIVISOR = 100.0

# Only dock receipts in `received` or `putaway_completed` state represent
# inventory accepted by DC Receiving QA. Loads in `quarantine_hold` or
# `rejected` failed dock inspection and MUST be excluded from accepted receipts,
# vendor fill rate, OTIF, and putaway backlog metrics.
ACCEPTED_RECEIPT_STATUSES: tuple[str, ...] = ("received", "putaway_completed")
EXCLUDED_RECEIPT_STATUSES: tuple[str, ...] = ("quarantine_hold", "rejected")


def normalize_edi856_qty(raw_qty: float, received_date: date) -> float:
    """Convert raw WMOS receipt quantity into sellable eaches across the 2024-03-25 cutover."""
    if received_date < EDI_856_CENTIUNIT_CUTOVER:
        return raw_qty / LEGACY_CENTIUNIT_DIVISOR
    return float(raw_qty)


def build_normalized_receipts_sql(project_id: str) -> str:
    """Return canonical BigQuery SQL producing deduplicated, eaches-normalized dock receipts.

    Key rules enforced:
      1. Shift-handoff deduplication: RF dock scanners replay buffered events at
         06:00 / 14:00 / 22:00 shift changes, producing duplicate `receipt_id` rows.
         Always deduplicate by keeping ONLY the latest `received_at` per `receipt_id`.
      2. Pre-2024-03-25 EDI 856 centi-unit conversion: divide `received_qty` and
         `damaged_qty` by 100.0 when `DATE(received_at) < DATE '2024-03-25'`.
      3. Accepted status filter: restrict to `status IN ('received', 'putaway_completed')`
         unless specifically auditing rejected/quarantined dock loads.
    """
    cutover = EDI_856_CENTIUNIT_CUTOVER.isoformat()
    statuses = ", ".join(f"'{s}'" for s in ACCEPTED_RECEIPT_STATUSES)
    return f"""
WITH deduped_receipts AS (
  SELECT
    r.receipt_id,
    r.po_number,
    r.item_nbr,
    r.dc_id,
    CASE
      WHEN DATE(r.received_at) < DATE '{cutover}' THEN r.received_qty / {LEGACY_CENTIUNIT_DIVISOR}
      ELSE r.received_qty
    END AS received_eaches,
    CASE
      WHEN DATE(r.received_at) < DATE '{cutover}' THEN r.damaged_qty / {LEGACY_CENTIUNIT_DIVISOR}
      ELSE r.damaged_qty
    END AS damaged_eaches,
    r.received_at,
    DATE(r.received_at) AS received_date,
    r.dock_door,
    r.status,
    UPPER(TRIM(r.hauler_name)) AS normalized_hauler_key,
    r.inspection_status
  FROM `{project_id}.{SOURCE_RECEIPTS_TABLE}` AS r
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY r.receipt_id
    ORDER BY r.received_at DESC
  ) = 1
)
SELECT
  *,
  GREATEST(received_eaches - damaged_eaches, 0.0) AS net_good_received_eaches
FROM deduped_receipts
WHERE status IN ({statuses})
""".strip()
