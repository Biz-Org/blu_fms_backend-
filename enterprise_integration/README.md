# Enterprise Integration (PrecastMPS)

Odoo 18 custom application for the PrecastMPS Facility Management System.

## Scope

Ten functional areas, **exactly six primary UIs**:

1. Dashboard
2. API & Webhook Management
3. Enterprise Connectors
4. Data Synchronization
5. Master Data Integration
6. Integration Monitoring & Logs

## Dependencies

- `base`
- `web`

## Installation

1. Place `enterprise_integration` under your Odoo `addons` / `custom_addons` path.
2. Update Apps List.
3. Install **Enterprise Integration**.

## Security groups

- Enterprise Integration User
- Enterprise Integration Manager
- Enterprise Integration Administrator

## Connectors

ERP / CRM / Bank / WhatsApp / Legacy use adapter interfaces with **mock/stub** implementations until real provider credentials are supplied.

## Async

Uses native `ir.cron` only (no `queue_job`).

## Branding

- Primary: `#5629CE`
- Light primary: `#F0EBFF`
