# NorthStar Retail — Supply Chain Data Pipelines

Production ingestion, warehouse transformation, BI semantic definitions, and governance policies for NorthStar Retail's Distribution Center (DC) and Procurement analytics estate on BigQuery.

## BigQuery Source Estate

| Domain | Dataset | Core Tables | System |
| :--- | :--- | :--- | :--- |
| Procurement (ERP) | `scm_sap_s4_mm` | `sap_s4_mm_vendors`, `sap_s4_mm_purchase_orders`, `sap_s4_mm_po_lines`, `sap_s4_mm_store_replenishment_orders`, `sap_s4_mm_bookings` | SAP S/4HANA Materials Management |
| Warehouse Ops (WMS) | `scm_manh_wmos` | `manh_wmos_products`, `manh_wmos_inbound_receipts`, `manh_wmos_putaway_tasks`, `manh_wmos_inventory_ledgers`, `manh_wmos_shipments`, `manh_wmos_consignments` | Manhattan Active WMOS |

## Repository Structure

- `pipelines/` — Python ETL normalization modules for Manhattan WMOS inbound dock receipts (`wmos_inbound_etl.py`) and daily inventory ledger snapshots (`inventory_ledger_sync.py`).
- `definitions/marts/` — Dataform SQLX analytical marts joining SAP S/4HANA purchase orders with WMOS dock receiving and putaway execution (`vendor_otif_scorecard.sqlx`).
- `lookml/views/` — LookML semantic layer views defining executive KPIs for receiving quality and fulfillment (`supply_chain_kpis.view.lkml`).
- `configs/` — Declarative System-of-Record table governance rules and supplier SLA contract policy (`governance_sla_policy.yaml`).
- `schemas/` — Protobuf event contracts for inbound EDI 856 dock scan ingestion (`inbound_dock_scan.proto`).
- `seeds/` — Reference lookup tables for carrier code and name standardization (`carrier_aliases.csv`).
- `notebooks/` — Executed data engineering audit notebooks (`q1_2024_receiving_cutover_audit.ipynb`).
