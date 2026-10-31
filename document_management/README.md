# Document Management

Odoo 18 Community addon for Facility Management System (FMS) document control: repository, versions, access, sequential approval, expiry overlay, keyword search, in-module notifications, and append-only audit.

This module is standalone. It does not depend on Command Center, Video Analytics, Workflow Engine, or Enterprise Integration.

## 1. Purpose

Provide eight primary Document Management screens inside Odoo. All business operations go through `document.management.ui.api`. The OWL UI does not enforce authorization by itself.

## 2. Installation

Module location:

`C:\Users\deeks\OneDrive\Desktop\Fms\custom_addons\document_management`

Odoo addons path must include that `custom_addons` directory (see `odoo.conf`).

```text
python odoo-bin -c odoo.conf -d ei_dev -i document_management --stop-after-init --without-demo=all
```

Assign users one of the three Document Management groups. Admin and root receive Manager and Administrator by default.

## 3. Upgrade

```text
python odoo-bin -c odoo.conf -d ei_dev -u document_management --stop-after-init --without-demo=all
```

No data migration scripts are required for 18.0.1.0.0. Sequence `document.management.document` is the only data XML record.

## 4. Module location

Technical name: `document_management`

| Area | Path |
| --- | --- |
| Models | `models/` |
| Services | `services/` |
| Share controller | `controllers/share.py` |
| Security | `security/` |
| OWL UI | `static/src/` |
| Tests | `tests/` |

## 5. Dependencies

Exactly:

- `base`
- `web`

No `mail`, cron, bus, portal, OAuth, or sibling FMS modules.

## 6. Menu architecture

1 root + 8 children = 9 menus. No Settings, Reports, Analytics, Configuration, AI Provider, or Users menu.

```text
Document Management
    Document Management Dashboard
    Document Repository
    Document Upload
    Document Details
    Access Control & Sharing
    Approval & Expiry
    Document Search
    Activity & Audit
```

## 7. Screen architecture

8 client actions, tag `document_management_app`, 8 OWL screen IDs:

| PPT | Screen ID | Destination |
| --- | --- | --- |
| Page 1 | `dashboard` | Document Management Dashboard |
| Page 2 | `repository` | Document Repository |
| Page 3 | `upload` | Document Upload |
| Page 4 | `details` | Document Details |
| Page 5 | `access` | Access Control & Sharing |
| Page 6 | `approval` | Approval & Expiry |
| Page 7 | `search` | Document Search |
| Page 8 | `audit` | Activity & Audit |

PPT page 9 is unused. No ninth screen.

## 8. Security groups

Exactly three groups:

| XML ID | Name |
| --- | --- |
| `group_dm_user` | Document Management User |
| `group_dm_manager` | Document Management Manager |
| `group_dm_admin` | Document Management Administrator |

Implied chain: Admin → Manager → User → Internal User.

Document roles (ACL, not extra groups): owner, editor, viewer. Assigned approvers receive read during a pending request. Managers override approval decisions. Only Administrator can hard-delete after archive.

Authorization is enforced in services (`DocumentAccessService.can` / `require`) plus company record rules. Frontend buttons only reflect the DTO `permissions` map.

## 9. Document lifecycle

States: `draft`, `pending_approval`, `approved`, `rejected`, `returned`, `archived`.

Allowed transitions:

- `draft` → `pending_approval` | `approved` | `archived`
- `pending_approval` → `approved` | `rejected` | `returned`
- `returned` / `rejected` → `pending_approval` | `archived`
- `approved` → `archived`
- archive restore returns to `prior_state`

`pending_approval → archived` is forbidden.

Upload with `requires_approval` enters `pending_approval`. Upload that skips approval enters `approved`.

## 10. Versioning

First file is `v1.0`. Each later upload increments the minor (`v1.1`, `v1.2`, …). Exactly one current version. Previous versions are immutable. Restoring an older version copies its file into a new current version.

## 11. Approval workflow

Owned entirely by this module. Steps are supplied on submit (`approver_id` + name/sequence). There are no hardcoded Legal/Finance/Final roles.

Only the active step reviewer can decide, unless the user is a Document Manager/Admin (frozen override). Reject and request-changes require a non-empty comment. Each decision writes audit and notification records. A new submit after reject/return creates a new request; the previous request stays closed.

## 12. Access control

Access levels: `private`, `role_restricted`, `internal`, `shared`.

Rules may target a user or an access group, on a document or a folder. Folder rules inherit down the folder chain. Owner ACL cannot be revoked. A user cannot grant a permission they do not have. Internal documents are readable by Document Users; download still requires ACL/owner/manager.

## 13. Share links

Route: `/document_management/share/<token>`

Token is `secrets.token_urlsafe(32)`. Expiry is required. Links can be revoked. Download is allowed only when the link is active, not expired, not revoked, `perm_download` is true, the document is not archived, and the attachment is not public. No raw `/web/content/` URL is returned to the UI. There is no public document browser or portal.

## 14. Expiry behavior

Overlay only: `none`, `active`, `expiring_soon` (≤ 30 days), `expired`. Expiry never changes lifecycle state. Renewal updates the date (optional replacement file) and logs `expiry_renewed`. `ensure_expiry_notifications()` is idempotent for unread expiry kinds. No cron.

## 15. Search behavior

Keyword search is authorization-aware (`visible_documents` then `can(read)`).

Fields: name, code, description, tags, owner, type, category, department, property, asset.

Filters: property/asset, department, date. CSV export uses the same authorized hit set. There is no file-content indexing.

## 16. AI unavailable state

`document.management.ai.provider.is_configured()` is always false. Exact RPC contract:

```text
configured = false
available = false
message = "AI Search is not configured"
answer = false
citations = []
sources = []
related = []
```

No external AI provider is connected.

## 17. Notifications

Kinds: `approval_submitted`, `approval_decision`, `access_granted`, `expiry_soon`, `expired`.

Stored in `document.management.notification`. Recipient- and company-scoped. Unread count and mark-read are recipient-only. No email, bus, or cron.

## 18. Audit

Backend-generated, append-only. Users cannot write or unlink events.

Event types used: `created`, `uploaded`, `metadata_modified`, `downloaded`, `access_changed`, `submitted`, `approved`, `rejected`, `returned`, `expiry_renewed`, `archived`, `restored`, `deleted`, `unauthorized_access`.

`viewed` exists on the selection but is discarded by `DocumentAuditService.log` and is never written. Audit list/CSV only include events for documents the caller can read. No failed-login monitoring.

## 19. File storage

`Document` → `Version` → `ir.attachment`

Attachment: `res_model = document.management.version`, `res_id = version.id`, `public = False`. Files stay in Odoo filestore. Allowed types: PDF, DOCX, XLSX, JPG, PNG. Maximum 50 MB.

## 20. Testing

From the addon directory (no Odoo):

```text
python -m compileall -q .
python -m unittest discover -s tests -p "test_structure.py"
python -m unittest discover -s tests -p "test_owl_ui.py"
python -m unittest discover -s tests -p "test_visual_ui.py"
```

From the Odoo root against `ei_dev`:

```text
python odoo-bin -c odoo.conf -d ei_dev --test-enable --test-tags /document_management --stop-after-init --without-demo=all
```

Odoo tests use `TransactionCase` and roll back. Do not load operational demo data.

## 21. Known intentional limitations

- AI Search is permanently unconfigured in this release.
- No email, bus, cron, portal, or public repository.
- No file-content / full-text indexing.
- No preview/view audit events and no failed-login monitoring.
- No property/building/site master models; those are labels (`property_ref`, `asset_ref`, `department_label`).
- Hard-delete is Administrator-only and requires archive first.
- Share tokens appear in the URL by design; they are not written to audit metadata.
- Generic ORM `search_read` record rules walk one folder parent; UI API uses service-level `can()` for the full folder chain.
- Odoo core web-push “Failed to enable push notifications” can appear in the browser and is not part of this module.
- Depends only on `base` + `web`; sibling FMS modules are not integrated.
