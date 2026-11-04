view: supply_chain_kpis {
  # Semantic layer KPI view over scm_manh_wmos & scm_sap_s4_mm.
  # SEMANTIC DISAMBIGUATION RULE:
  #   When business users ask for "OTIF" without qualification, ALWAYS default to
  #   Tier-1 Vendor Inbound PO OTIF (`vendor_otif_tier1_pct` in vendor_otif_scorecard.sqlx).
  #   Only report `store_replenishment_otif_tier2_pct` when the user explicitly asks
  #   about Store Replenishment, Outbound DC-to-Store, or Tier-2 OTIF.

  derived_table: {
    sql:
      SELECT
        r.receipt_id,
        r.po_number,
        r.item_nbr,
        r.dc_id,
        DATE(r.received_at) AS received_date,
        r.status,
        r.hauler_name,
        r.inspection_status,
        CASE
          WHEN DATE(r.received_at) < DATE '2024-03-25' THEN r.received_qty / 100.0
          ELSE r.received_qty
        END AS received_eaches,
        CASE
          WHEN DATE(r.received_at) < DATE '2024-03-25' THEN r.damaged_qty / 100.0
          ELSE r.damaged_qty
        END AS damaged_eaches
      FROM `scm_manh_wmos.manh_wmos_inbound_receipts` AS r
      QUALIFY ROW_NUMBER() OVER (PARTITION BY r.receipt_id ORDER BY r.received_at DESC) = 1 ;;
  }

  dimension: receipt_id {
    primary_key: yes
    type: string
    sql: ${TABLE}.receipt_id ;;
  }

  dimension: canonical_carrier_name {
    description: "Standardizes raw dock scanner hauler_name abbreviations per seeds/carrier_aliases.csv"
    type: string
    sql:
      CASE
        WHEN UPPER(TRIM(${TABLE}.hauler_name)) IN ('JB HUNT', 'JBH') THEN 'JB Hunt'
        WHEN UPPER(TRIM(${TABLE}.hauler_name)) IN ('SWIFT TRANSPORT', 'SWIFT TRANS', 'SWIFT TRNS') THEN 'Swift Transport'
        WHEN UPPER(TRIM(${TABLE}.hauler_name)) IN ('WERNER ENTERPRISE', 'WERNER ENT') THEN 'Werner Enterprise'
        WHEN UPPER(TRIM(${TABLE}.hauler_name)) IN ('SCHNEIDER', 'SCHNEIDER NATIONAL', 'SCHNEIDER NATL') THEN 'Schneider National'
        WHEN UPPER(TRIM(${TABLE}.hauler_name)) IN ('FEDEX FREIGHT', 'FEDEX FRT') THEN 'FedEx Freight'
        ELSE INITCAP(TRIM(${TABLE}.hauler_name))
      END ;;
  }

  measure: accepted_receipt_count {
    type: count_distinct
    sql: ${TABLE}.receipt_id ;;
    filters: [status: "received, putaway_completed"]
  }

  measure: clean_receipt_rate_pct {
    label: "Clean Receipt Rate (%)"
    description: "Percentage of deduplicated accepted dock receipts (status IN ('received','putaway_completed')) with zero normalized damaged_eaches AND inspection_status = 'PASS'."
    type: number
    value_format_name: percent_2
    sql:
      ROUND(
        100.0 * COUNTIF(
          ${TABLE}.status IN ('received', 'putaway_completed')
          AND ${TABLE}.damaged_eaches = 0
          AND ${TABLE}.inspection_status = 'PASS'
        ) / NULLIF(COUNTIF(${TABLE}.status IN ('received', 'putaway_completed')), 0),
        2
      ) ;;
  }

  measure: receiving_accuracy_pct {
    label: "Net Good Receiving Accuracy (%)"
    description: "Net undamaged eaches divided by total accepted received eaches (after pre-2024-03-25 /100 normalization)."
    type: number
    value_format_name: percent_2
    sql:
      ROUND(
        100.0 * SUM(
          IF(${TABLE}.status IN ('received', 'putaway_completed'),
             ${TABLE}.received_eaches - ${TABLE}.damaged_eaches, 0)
        ) / NULLIF(
          SUM(IF(${TABLE}.status IN ('received', 'putaway_completed'), ${TABLE}.received_eaches, 0)),
          0
        ),
        2
      ) ;;
  }
}

view: store_replenishment_kpis {
  sql_table_name: `scm_sap_s4_mm.sap_s4_mm_store_replenishment_orders` ;;

  dimension: store_nbr {
    description: "Numeric store ID parsed from SAP S/4HANA string format 'Store <nbr>'."
    type: number
    sql: SAFE_CAST(REGEXP_EXTRACT(${TABLE}.store_id, r'^Store\s+(\d+)$') AS INT64) ;;
  }

  measure: store_replenishment_otif_tier2_pct {
    label: "Tier-2 Store Replenishment OTIF (%)"
    description: "Outbound DC-to-store order fulfillment rate where status = 'DELIVERED', delivered_date <= promised_date, and qty_shipped >= qty_requested."
    type: number
    sql:
      ROUND(
        100.0 * COUNTIF(
          ${TABLE}.status = 'DELIVERED'
          AND ${TABLE}.delivered_date <= ${TABLE}.promised_date
          AND ${TABLE}.qty_shipped >= ${TABLE}.qty_requested
        ) / NULLIF(COUNTIF(${TABLE}.status = 'DELIVERED'), 0),
        2
      ) ;;
  }
}
