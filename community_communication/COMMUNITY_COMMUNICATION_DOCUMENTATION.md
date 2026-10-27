# Community & Communication — Module Documentation

**Facility Management System (FMS) · Odoo 18**

| Item | Value |
|------|--------|
| **Display name** | Community & Communication |
| **Technical name** | `community_communication` |
| **Version** | 18.0.1.9.3 (see `__manifest__.py`) |
| **Odoo dependencies** | `mail`, `portal` |
| **Application** | Yes (appears as **Community** in the app switcher) |

---

## 1. Module Overview

### What this module is

Community & Communication is an Odoo 18 application for **property and facility communities**. It gives management a single place to **publish information**, run **discussions and polls**, plan **events**, display **notices**, collect **resident feedback**, and organize **interest groups**. Residents participate through the same modern web interface (OWL app) that staff use, with permissions tailored to each role.

### Why it is needed in an FMS

A facility management system must coordinate **people**, not only assets and work orders. Residents need timely, trustworthy updates. Property teams need traceable communication, engagement metrics, and structured feedback. Without a dedicated community module, updates often scatter across email, chat, and paper notices—with no audit trail, targeting, or participation data.

This module centralizes community life cycle data in Odoo: **who** was told **what**, **who** responded, and **how** engagement trends over time—all tied to **communities, buildings, units, and resident profiles**.

### Who uses it

| Role | Typical person | Summary |
|------|----------------|---------|
| **Resident** | Tenant or owner (portal user) | Read targeted content; participate in forums, polls, events, groups; submit feedback; acknowledge announcements. |
| **Officer** | Property / community staff (internal user) | Create, schedule, and publish content; manage feedback workflows; view dashboard and analytics. |
| **Moderator** | Staff with forum oversight (implies Officer) | Moderate discussions, handle reported content, extended delete rights on several content types. |
| **Administrator** | Community app admin (implies Moderator) | Configure communities, buildings, units, venues, and resident profiles. |

Each person has **one Odoo login** (`res.users`). Permissions come from **security groups**, not separate login portals.

---

## 2. Features and Their Purpose

The sections below follow the same pattern: **what**, **why**, **what users can do**, **who**, **how it works**, **example**, **expected outcome**.

---

### 2.1 Announcements

**What it is**  
Official messages from management to residents (and optionally targeted internal users), with categories, scheduling, expiry, pinning, views, and optional **acknowledgement**.

**Why it is needed**  
Urgent or policy updates (water shutdown, AGM, safety notices) must reach the right audience and, when required, prove that residents saw them.

**What users can do**

- **Officers:** Draft, schedule, publish, expire, and archive announcements; set audience (whole community, buildings, groups, specific residents, or users); send email via mail templates on publish.
- **Residents:** See **published** announcements that match their community and audience rules; open and read; **acknowledge** when required; views are logged.
- **Moderators:** Full create/write/unlink on announcements (per access rights).

**Who uses it**  
Residents (read + acknowledge); Officers and above (manage).

**How it works (workflow)**

1. Officer creates an announcement (draft), sets content, audience, and optional publish/expiry dates.
2. Officer publishes immediately or schedules for a future time.
3. Hourly cron (`community.communication.scheduler`) can auto-publish scheduled items and expire published ones past expiry.
4. Residents see the item in the Announcements screen; acknowledgements and views are stored on separate records.

**Example**  
Management publishes “Elevator maintenance — Tower B, Saturday 9–12” targeted to Tower B. Residents in that building see it and acknowledge.

**Expected outcome**  
Residents are informed; management can see reach (views/acks) and retain a record in Odoo.

---

### 2.2 Discussion Forums

**What it is**  
Threaded community discussions with comments, reactions, follow/unfollow, pin/lock, and **report** workflow for inappropriate content.

**Why it is needed**  
Residents need a moderated space to ask questions and discuss issues without unmanaged social media.

**What users can do**

- **Residents:** Start discussions (create), comment, react, follow, report posts.
- **Officers:** Manage discussions (edit, publish workflow per model rules).
- **Moderators:** Remove discussions, handle reports, access moderation logs.

**Who uses it**  
Residents and staff (Moderator for enforcement).

**How it works**

1. User opens **Discussion Forums**, creates or opens a thread.
2. Comments and reactions are stored on related models; `last_activity_at` drives sorting.
3. Residents can report content; moderators work pending reports (KPI on discussion screen links to reports for staff).

**Example**  
A resident asks about parking rules; others comment; a moderator locks the thread after the answer is posted.

**Expected outcome**  
Transparent, auditable community dialogue within property boundaries.

---

### 2.3 Polls

**What it is**  
Single- or multi-option polls with audience targeting, open/close dates, and vote tracking.

**Why it is needed**  
Management needs structured resident input (amenity hours, renovation priorities) with countable results.

**What users can do**

- **Officers:** Create polls, manage options, publish/open/close (including cron-assisted open/close).
- **Residents:** Vote when poll is **active** and audience matches; typically one vote per resident (enforced in business logic — **Requires verification** for all edge cases in UI).

**Who uses it**  
Residents (vote); Officers (manage).

**How it works**

1. Officer creates poll and options, sets audience and dates, activates poll.
2. Residents vote from the Polls screen.
3. Scheduler cron runs poll open/close helpers with announcements and notices.

**Example**  
“Which day works best for the summer BBQ?” — residents vote; officer closes poll and shares results.

**Expected outcome**  
Documented community preference for decisions.

---

### 2.4 Events

**What it is**  
Community events with schedule, venue, capacity, categories, and lifecycle states (e.g. published, completed, cancelled). Uses mail thread/activities for staff collaboration.

**Why it is needed**  
Facilities run social and educational events; residents need one calendar of what is happening on site.

**What users can do**

- **Officers:** Create and publish events, set capacity and venue, complete or cancel events; reminders via cron.
- **Residents:** Browse published events in their scope; register (see Event Registrations).

**Who uses it**  
Residents (attend/register); Officers (manage).

**How it works**

1. Officer creates event, publishes when ready.
2. Cron sends reminders and can mark past events completed.
3. Residents register from the event UI (creates registration records).

**Example**  
“Fire safety awareness session” at the clubhouse with 50 seats.

**Expected outcome**  
Clear event calendar and attendance tracking.

---

### 2.5 Event Registrations

**What it is**  
Records linking a **resident** to an **event** (RSVP / attendance).

**Why it is needed**  
Capacity limits, attendance lists, and follow-up communication require per-person registration data.

**What users can do**

- **Residents:** Create their own registrations (per access rights) for events they can see.
- **Officers:** Full management of all registrations (menu **Event Registration** is **officer-only**).

**Who uses it**  
Residents (self-register); Officers (manage all attendees).

**How it works**

1. Resident registers from Event Calendar (or related UI).
2. Officer opens **Event Registration** to see and manage the attendee list across events.

**Example**  
45 of 50 seats filled; officer exports or contacts waitlist — export behavior **Requires verification** if not exposed in OWL UI.

**Expected outcome**  
Controlled attendance and headcount for events.

---

### 2.6 Notices and Digital Notice Board

**What it is**  
Shorter or board-style notices (distinct from long-form announcements), with publish/archive lifecycle and audience targeting. The **Digital Notice Board** menu uses the same screen with context `cc_board: True` for a board-oriented presentation.

**Why it is needed**  
Lobby screens and “notice board” content differ from formal announcements—faster updates, visual board layout.

**What users can do**

- **Officers:** Create, publish, archive notices.
- **Residents:** View **published** notices matching audience rules.

**Who uses it**  
Residents and Officers.

**How it works**

1. Officer publishes notices.
2. Cron (`_cron_publish_and_archive` on notices) supports scheduled behavior.
3. Residents use **Community Notices** or **Digital Notice Board** menus (same underlying feature, different menu context).

**Example**  
“Lost & found: keys at reception” on the digital board.

**Expected outcome**  
Residents see timely board-style information.

---

### 2.7 Resident Feedback

**What it is**  
Tickets for suggestions, complaints, and questions with category, priority, optional anonymity, attachments, internal notes (staff), and official responses. States: Submitted → In Progress → Resolved → Closed.

**Why it is needed**  
Properties need a trackable channel for resident issues instead of unstructured email.

**What users can do**

- **Residents:** Submit feedback (linked to their resident profile or anonymous); limited updates (e.g. attachments only after submit — enforced in code).
- **Officers:** Assign, change status, add internal notes and responses, full management.

**Who uses it**  
Residents (submit); Officers (process); Moderators/Admins inherit officer capabilities for feedback models.

**How it works**

1. Resident submits feedback from **Resident Feedback** screen.
2. Officer moves to In Progress, adds notes, sends response, resolves/closes.
3. Mail thread/activities support follow-up on the backend model.

**Example**  
Anonymous noise complaint → officer assigns to security → resolved with response to resident.

**Expected outcome**  
Accountable handling of resident concerns.

---

### 2.8 Community Groups

**What it is**  
Interest or activity groups (e.g. book club, running group) with membership states and link to community scope.

**Why it is needed**  
Engagement works better in smaller communities; groups also feed **audience targeting** for announcements and polls.

**What users can do**

- **Officers:** Create and manage groups.
- **Residents:** View active groups in their community; join (create membership records).

**Who uses it**  
Residents and Officers.

**How it works**

1. Officer creates group and sets community.
2. Resident requests or joins membership (workflow per UI — **Requires verification** for approval steps).
3. Group membership affects `user.cc_member_group_ids` for audience rules.

**Example**  
“Tower A gardening club” receives targeted poll on shared tool storage.

**Expected outcome**  
Organized sub-communities and sharper targeting.

---

### 2.9 Dashboard

**What it is**  
A summary screen: KPIs (announcements, discussions, polls, events, open feedback), weekly engagement counts, upcoming events, recent activity, active polls.

**Why it is needed**  
Staff and residents need a single landing page instead of opening every feature.

**What users can do**

- **Residents and Officers:** Open **Dashboard** (menu allows both groups).
- Data is loaded via `community.communication.dashboard` → `get_dashboard_data()` (counts respect user access rules).

**Who uses it**  
Residents and Officers (not a separate “dashboard role”).

**How it works**

1. User opens Community → Dashboard.
2. OWL client calls the dashboard service; cards and lists render from returned JSON.

**Example**  
Officer sees 3 open feedback items and 2 events this week.

**Expected outcome**  
Faster orientation and prioritization.

---

### 2.10 Analytics

**What it is**  
**Engagement Analytics** for staff: trends over a selectable period, building filter, views/acks on announcements, discussion categories, poll participation, event registrations, feedback volumes, etc. (`get_analytics_data`).

**Why it is needed**  
Management reports on communication effectiveness and participation.

**What users can do**

- **Officers only:** Menu and server method enforce officer check (`AccessError` if resident calls analytics API).

**Who uses it**  
Officers (Moderators/Admins included via implied groups).

**How it works**

1. Officer opens **Engagement Analytics**.
2. UI requests analytics payload for date range (and optional building).
3. Charts/tables render from aggregated counts.

**Example**  
Compare announcement views vs acknowledgements over the last 30 days for Building A.

**Expected outcome**  
Data-informed communication strategy.

---

### 2.11 Community Configuration

**What it is**  
Master data under **Configuration** (Administrator menu): **Communities**, **Buildings**, **Units**, **Venues**, **Residents** (profiles linking partners/users to units and communities).

**Why it is needed**  
All targeting, scoping, and resident portal access depend on correct structure data.

**What users can do**

- **Administrators:** Full CRUD on configuration models (per ACL).
- **Officers:** Read-only on communities/buildings/units/venues/residents in many cases; cannot access Configuration menu (admin group on menu).

**Who uses it**  
Primarily Administrators; Officers use data indirectly when creating content.

**How it works**

1. Admin defines community → buildings → units → venues.
2. Admin creates **resident** records and links portal users (post-init hooks sync portal access — see `hooks.py`).
3. Content creators select communities and audiences on announcements, polls, etc.

**Example**  
New tower added as building; units imported; residents invited as portal users with Resident group.

**Expected outcome**  
Accurate audience targeting and resident logins.

---

## 3. User Roles and Permissions

### Role purposes

| Role | Purpose |
|------|---------|
| **Resident** | Portal-based community member; same OWL Community app with strict record rules (own community, published content, own votes/registrations/feedback). |
| **Officer** | Day-to-day publisher and feedback handler; full visibility on community content within company. |
| **Moderator** | Forum safety: reports, removal, moderation log, extra delete rights. |
| **Administrator** | Structural setup and full configuration access. |

### Feature access summary

Legend: **V** = view (in scope), **C** = create, **E** = edit, **P** = publish/manage lifecycle, **M** = moderate/delete, **—** = not intended / blocked by ACL or menu.

| Feature | Resident | Officer | Moderator | Administrator |
|---------|----------|---------|-----------|---------------|
| Announcements | V, ack | V, C, E, P | V, C, E, P, M (unlink) | Same as Moderator + config |
| Discussions | V, C (posts) | V, C, E | V, C, E, M | Same |
| Polls | V, vote | V, C, E, P | V, C, E, P, M | Same |
| Events | V | V, C, E, P | V, C, E, P, M | Same |
| Event registrations | V, C (own) | V, C, E, all (menu) | Same as Officer | Same |
| Notices / board | V | V, C, E, P | V, C, E, P, M | Same |
| Feedback | V, C (submit) | V, C, E, P (status) | Same as Officer | Same |
| Groups | V, join | V, C, E | V, C, E, M | Same |
| Dashboard | V | V | V | V |
| Analytics | — | V | V | V |
| Configuration | — | — | — | V, C, E, M |

**Notes**

- Residents are **not** internal users (`base.group_user`); they use **portal** plus `group_community_resident`.
- Record rules further restrict residents to **published** content and matching **audience** (community, building, group, or specific resident).
- Exact OWL button visibility may hide actions even when ACL allows — **Requires verification** per screen.

---

## 4. How the Module Works

### General user flow

1. **Login** — Same Odoo login page for everyone.
2. **Routing** — Portal residents with the Resident group are redirected to the **web client** (`/odoo`) for the Community app (see `controllers/portal.py`), not only the classic “My Account” portal pages.
3. **App** — User opens **Community** from the app switcher (if their groups show the menu).
4. **Feature** — User picks a menu item (Announcements, Polls, etc.); Odoo loads an **OWL client action**.
5. **Action** — UI calls Odoo (`orm.call`) to read or write data on `community.communication.*` models.
6. **Rules** — Server applies **access rights** and **record rules**; only allowed data is returned or saved.
7. **Feedback** — User sees updated lists, KPIs, or messages; email may be sent via **mail** templates on publish events.

### Staff vs resident interface

| Aspect | Staff (Officer+) | Resident |
|--------|------------------|----------|
| Odoo user type | Internal (`base.group_user`) | Portal (`base.group_portal`) |
| Community UI | Full OWL app | Same OWL shell (`cc_shell`), fewer menus (e.g. no Analytics, no Event Registration admin menu) |
| Data scope | Company-wide content management | Scoped to resident profile, community, and audience |
| Configuration | Administrators only | No Configuration menu |

Both use the same **asset bundles** declared in `__manifest__.py` for core OWL screens (scss, `owl/ui`, `owl/screens`).

---

## 5. Module Structure (Simple Language)

| Part | Purpose in plain English |
|------|---------------------------|
| **Python models** | Database tables and business rules (publish states, voting, registration, cron helpers). |
| **OWL / JavaScript** | Interactive screens in the browser (lists, forms, dashboard cards). |
| **XML (views, menus, actions)** | Registers menus, links menu items to OWL actions, defines optional classic form views for configuration. |
| **Security groups** | Job roles (Resident, Officer, …). |
| **Access CSV** | Which role can read/write/create/delete each model. |
| **Record rules** | Row-level filters (e.g. “resident only sees published announcements in their community”). |
| **Portal controllers** | Special login and web-client routing for residents. |
| **Mail** | Email templates and chatter on records (feedback, events, polls). |
| **Scheduled task** | Hourly cron calls `community.communication.scheduler` to publish/expire content and run poll/event helpers. |
| **Other FMS modules** | Optional bridge from Fire Safety mock drills to announcements (`fire_safety_community`). |

---

## 6. Integrations and Dependencies

### Odoo `mail`

- **Why:** Chatter, activities, and emailed announcements (e.g. template on publish).
- **Effect:** Officers can use familiar Odoo follow-up; residents may receive email when templates are configured.

### Odoo `portal`

- **Why:** Resident logins without full backend licenses.
- **Effect:** Resident group implies portal; hooks sync portal access when residents are provisioned.

### `fire_safety_community` (optional separate addon)

- **Confirmed behavior:** Extends `fire.safety.drill`. When participants are set and staff notify them, the bridge creates or updates a **Community announcement** targeted at participants’ resident profiles and can link back via `cc_announcement_id`.
- **Requires:** `fire_safety_management` and `community_communication` installed.
- **Note:** Fire Safety staff can trigger notification without holding Community ACLs (sudo in bridge code).

---

## 7. Installation and Configuration

### Dependencies

Install **mail** and **portal** automatically when installing `community_communication`.

### Install (example)

From your Odoo 18 environment, include the addons path that contains `community_communication`, then:

```bash
-i community_communication --stop-after-init
```

(Use your database name and full `--addons-path` as in project `run_setup`.)

### Post-install

- `post_init_hook` runs setup in `hooks.py` (including resident portal access sync — review code for your provisioning process).

### Assign roles

**Settings → Users & Companies → Users**

- Staff: **Community & Communication** privilege → Officer / Moderator / Administrator as needed.
- Residents: **Resident** group + portal access; link **Resident** profile to community/unit.

### Basic setup order

1. Configure **Communities → Buildings → Units → Venues** (Administrator).
2. Create **Residents** and portal users.
3. Assign **Officer** users for publishing.
4. Install optional **`fire_safety_community`** if drill announcements are required.

### Python extras

No extra pip packages beyond standard Odoo; project may list `python-dateutil` at repo level for other modules.

---

## 8. Testing and Verification

Automated tests exist under `community_communication/tests/` (install, domain, event workflow, form persistence, UI layer). **This documentation does not state that tests passed** in your environment unless you run them.

### Recommended manual checks

| Area | What to verify |
|------|----------------|
| **Announcements** | Draft → publish → resident sees item → acknowledge; schedule/expiry via cron **Requires verification** on a running cron. |
| **Discussions** | Create thread, comment, report; moderator handles report. |
| **Polls** | Activate, vote as resident, close; counts update. |
| **Events** | Publish, register, capacity **Requires verification**. |
| **Registrations** | Officer menu lists attendees; resident sees own registration. |
| **Notices / board** | Publish; both menus behave as expected. |
| **Feedback** | Resident submit; officer status change; resident cannot change status. |
| **Groups** | Create, join, use group in announcement audience. |
| **Dashboard** | KPIs load for officer and resident. |
| **Analytics** | Officer can open; resident denied. |
| **Permissions** | Resident cannot open Configuration or Analytics menus. |
| **Portal** | Resident login lands in Community OWL app. |
| **Validation** | Required fields (e.g. feedback subject/category) reject empty submits. |
| **Mail** | Publish announcement sends email if outgoing mail configured — **Requires verification**. |
| **Cron** | `ir_cron_community_communication` active — **Requires verification**. |
| **Fire safety bridge** | With `fire_safety_community`, drill notify creates announcement — **Requires verification**. |
| **Frontend assets** | After install, hard refresh; SCSS/OWL load without console errors. |

Run automated tests example:

```bash
.venv/bin/python odoo-bin --addons-path="..." -d YOUR_DB --test-enable --stop-after-init -i community_communication
```

---

## 9. Known Issues and Limitations

### Confirmed from code review

| Issue | Detail |
|-------|--------|
| **Manifest vs extra static files** | `__manifest__.py` lists `owl/ui`, `owl/screens`, scss, `cc_action.js`, `utils.js` only. Additional bundles under `static/src/components`, `dashboard`, `analytics`, and `views` exist but are **not** all declared in `assets`. Some screens may depend on manifest-listed paths only; duplicate registrations exist for `action_dashboard` and `action_analytics` in two JS files each (last load wins). |
| **Module `README.md` outdated** | States the module is an “empty bootstrap”; the implementation is full-featured. Prefer this document and `__manifest__.py` version. |
| **Analytics access** | Server enforces officer-only on `get_analytics_data`; residents must not see Analytics menu (menu groups officer-only). |
| **Feedback resident edits** | After submit, residents may only update attachments (not status/assignee). |
| **Officer delete on announcements** | ACL: officers have unlink=0 on announcements; moderators have unlink=1. |

### Requires verification

- End-to-end email delivery for all mail templates.
- Every OWL screen’s buttons vs ACL (UI may differ slightly from table above).
- Mobile/responsive behavior on all screens (SCSS includes mobile work — not fully regression-tested in this doc).
- Export/print on registrations or analytics.
- Whether all cron paths run correctly on your server timezone and worker setup.

### Not tested in this documentation pass

- No install test, Docker deploy, or browser test was executed while writing this file.

---

## 10. Conclusion

Community & Communication turns the FMS into a **resident-facing communication hub** as well as a **staff operations tool**. Announcements and notices deliver official information; forums and polls capture voice; events and groups build participation; feedback closes the loop on service quality; dashboard and analytics give management visibility. Together with portal access and optional fire-drill announcements, the module supports **transparent, targeted, and measurable** community management inside Odoo 18.

---

*Document generated from the `community_communication` codebase (models, security, manifest, menus, portal, scheduler, tests listing). For technical module name in commands and paths, use `community_communication`.*
