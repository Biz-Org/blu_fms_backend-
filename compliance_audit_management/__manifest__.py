# -*- coding: utf-8 -*-
{
    "name": "Compliance & Audit Management",
    "version": "18.0.2.8.0",
    "category": "Services/Compliance",
    "summary": "Statutory compliance checks, documents, audits, non-compliance, and regulatory reporting",
    "description": """
Compliance & Audit Management for facility management.

Standalone Odoo 18 addon (FMS module #24) for statutory compliance
requirements and checklists, compliance documents and expiry tracking,
audits and inspections, non-compliance and corrective actions,
regulatory reporting, and compliance KPIs.
    """,
    "author": "FMS Compliance",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "depends": [
        "mail",
    ],
    "data": [
        "security/compliance_groups.xml",
        "security/ir.model.access.csv",
        "security/compliance_rules.xml",
        "data/ir_sequence_data.xml",
        "data/ir_cron_data.xml",
        "views/location_views.xml",
        "views/requirement_views.xml",
        "views/checklist_views.xml",
        "views/check_views.xml",
        "views/audit_views.xml",
        "views/finding_views.xml",
        "views/non_compliance_views.xml",
        "views/action_views.xml",
        "views/document_views.xml",
        "views/regulatory_views.xml",
        "views/alert_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "compliance_audit_management/static/src/scss/_tokens.scss",
            "compliance_audit_management/static/src/scss/compliance_audit.scss",
            "compliance_audit_management/static/src/owl/ui/**/*",
            "compliance_audit_management/static/src/owl/screens/**/*",
        ],
    },
}
