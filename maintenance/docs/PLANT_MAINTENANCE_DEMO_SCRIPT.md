# Plant Maintenance — One-Page Live Demo Script
**Asset:** Air Compressor 2 · **Time:** ~30 min · **App:** Maintenance (Odoo 18)

---

## Opening (30 sec)
> “We manage plant assets from **registration → work order → execution → safety decision → root cause → dashboards**. Today we follow **Air Compressor 2** through a real breakdown and show how leadership sees **risk (RUL & TOBM)** before failure.”

| Say this | Meaning |
|----------|---------|
| Equipment = asset master | Every machine has one record |
| Request = work order | One ticket for the full job life |
| Workflow = 8 steps | Nobody guesses ‘where is this stuck?’ |
| RUL & TOBM = health | Plan maintenance before breakdown |

---

## Demo path — follow in order

| # | Go to | Do / show | Say |
|---|--------|-----------|-----|
| **1** | **Equipment** → Air Compressor 2 | Name, category **Machines**, team, location, **Life consumed %**, **Expected MTBF** | “All jobs and dashboards link to this asset.” |
| **2** | **Operations → Maintenance Requests** → **New** | Subject: *High discharge temp – AC-2* · Equipment: **Air Compressor 2** · Type: **Corrective** · Team + priority | “Operator reports a problem; one record tracks everything.” |
| **3** | Same form — **Spares** tab | Add line: filter kit / oil (demo) | “Parts are planned before we promise downtime.” |
| **4** | Same form — **Manpower** tab | Assign mechanic (or owner) | “Right skill on the job.” |
| **5** | Same form — **Planning** | Plan type: breakdown · planned date | “Supervisor schedules the window.” |
| **6** | **Operations → Workflow / Timeline** | Open this request → 8 steps: Issue → Plan → Spares → Assigned → Execution → **Go/No-Go** → Root cause → Completed | “Green = done. Highlight = current step. Management sees blockers instantly.” |
| **7** | Back to request — **Execution** | Actual hours, execution notes | “Technician logs work on the floor.” |
| **8** | Same form — **Go / No-Go** | Set **GO** + short note | “Machine safe to run—or NO-GO keeps it stopped.” |
| **9** | Same form — **Root cause** | e.g. *Blocked cooler / poor airflow* · Stage → **Repaired** | “We close with cause, not only ‘fixed’.” |
| **10** | **Reporting → RUL & TOBM** | Filter: **Machines** · Period: **Last 365 days** | “Health view for all plant machines in scope.” |
| **11** | RUL screen — **KPI row** | **Average RUL** · **Failure threshold 75%** · **TOBM opportunities** (e.g. 1) · **Next critical** | “TOBM = machines at **65–75% life**—plan service now. Next critical = closest to **75% life used**.” |
| **12** | RUL screen — **chart** | Select **Air Compressor 2** in dropdown | “Chart is one machine; KPIs are the whole filtered fleet.” |
| **13** | **Analysis → AI Why-Why RCA** (or Fishbone) | Open linked / sample RCA | “Repeat failures get structured investigation—not guesswork.” |
| **14** | **Reporting → Maintenance Analytics** | Cost / type mix (corrective vs preventive) | “Management summary for the period.” |

---

## 8 workflow steps (reference)

`Issue` → `Maintenance plan` → `Spare planning` → `WO assigned` → `Work execution` → `Go/No-Go` → `Root cause` → `Completed`

---

## Three maintenance types (one line each)

| Type | When | Demo example |
|------|------|----------------|
| **Corrective** | Breakdown | Compressor overheating (today) |
| **Preventive** | Scheduled PM | Quarterly service |
| **Predictive** | Condition / sensors | High vibration → inspect early |

---

## RUL & TOBM — don’t mix these up

| Control | Updates |
|---------|---------|
| **Category / date** (top filters) | **All KPIs** + equipment count in meta line |
| **Equipment** (chart dropdown) | **Chart / timeline title only** |
| **TOBM = 1** | One machine with **65–75% life consumed** |
| **Failure threshold 75%** | **Life used** at high risk (= **25% RUL** left) |

---

## Closing (20 sec)
> “**Air Compressor 2** is registered once, maintained through a visible **8-step workflow**, and monitored on **RUL & TOBM** so we maintain in the **opportunity window**—not only after shutdown. Questions?”

---

**Pre-demo checklist:** [ ] Module upgraded · [ ] Air Compressor 2 exists with category **Machines** · [ ] At least one open/done request on AC-2 · [ ] Browser hard-refresh (Ctrl+Shift+R)

*Bizlem Odoo 18 — Maintenance*
