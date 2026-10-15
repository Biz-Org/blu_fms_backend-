# -*- coding: utf-8 -*-

import logging
import re
from datetime import datetime, time, timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import html2plaintext
from odoo.tools.translate import _

from .catalog import PROPOSAL_MODELS, SOURCES

STOPWORDS = {
    "show", "me", "the", "a", "an", "of", "for", "to", "in", "on", "and", "or",
    "what", "which", "who", "how", "many", "are", "is", "was", "were", "be",
    "please", "can", "you", "my", "our", "this", "that", "these", "those",
    "with", "from", "about", "into", "need", "needs", "any", "there", "have",
    "has", "do", "does", "did", "i", "we", "it", "its", "their", "them", "ones",
    "month", "today", "yesterday", "weekend", "last", "next", "your", "all",
}
FLAG_WORDS = {
    "overdue", "servicing", "service", "summary", "summarize", "summarise",
    "pending", "open", "create", "raise", "compare", "performance", "due",
}
LOCATION_RE = re.compile(r"\b(?:tower|building|block|wing|unit)\s+[a-z0-9]+\b", re.I)
ROW_LIMIT = 8
_logger = logging.getLogger(__name__)


class AiCopilotRetrieval(models.AbstractModel):
    _name = "ai.copilot.retrieval"
    _description = "AI Copilot Retrieval"

    @api.model
    def _flags(self, question):
        text = (question or "").lower()
        return {
            "overdue": any(word in text for word in ("overdue", "past due")),
            "service": any(word in text for word in ("servic", "needs servicing", "service due")),
            "open": any(word in text for word in ("pending", "open", "not closed")),
            "summary": any(word in text for word in ("summar", "performance", "compare", "trend")),
            "create": bool(re.search(r"\b(create|raise|log|open)\b", text)) and any(
                word in text for word in ("task", "request", "ticket", "work order")
            ),
            "help": any(word in text for word in ("how do i", "what does", "explain", "help me", "what is a ")),
            "energy": any(word in text for word in ("energy", "consumption", "kwh")),
            "knowledge": any(word in text for word in (
                "policy", "policies", "sop", "procedure", "manual", "guideline", "knowledge",
            )),
            "followup": any(word in text for word in (
                "those", "these ones", "the overdue ones", "same ones", "more detail", "that list", "show them",
            )),
        }

    @api.model
    def _window(self, question):
        today = fields.Date.context_today(self)
        text = (question or "").lower()
        if "yesterday" in text:
            day = today - timedelta(days=1)
            return day, day, _("yesterday")
        if "today" in text:
            return today, today, _("today")
        if "last month" in text:
            first = today.replace(day=1)
            end = first - timedelta(days=1)
            start = end.replace(day=1)
            return start, end, _("last month")
        if "this month" in text or "month's" in text or "this month" in text:
            return today.replace(day=1), today, today.strftime("%B")
        if "weekend" in text:
            weekday = today.weekday()
            saturday = today + timedelta(days=(5 - weekday) % 7)
            return saturday, saturday + timedelta(days=1), _("this weekend")
        if "tomorrow" in text:
            day = today + timedelta(days=1)
            return day, day, _("tomorrow")
        return None, None, ""

    @api.model
    def _content_tokens(self, question):
        words = re.findall(r"[a-z0-9][a-z0-9'-]{2,}", (question or "").lower())
        tokens = [word for word in words if word not in STOPWORDS and word not in FLAG_WORDS]
        phrases = [match.group(0) for match in LOCATION_RE.finditer(question or "")]
        return tokens, phrases

    @api.model
    def _select_sources(self, question, flags):
        text = (question or "").lower()
        scored = []
        for spec in SOURCES:
            score = sum(2 for keyword in spec["keywords"] if keyword in text)
            if flags.get("energy") and spec["key"] == "iot_energy":
                score += 3
            if score:
                scored.append((score, spec))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [spec for _score, spec in scored[:4]]

    @api.model
    def _field_ok(self, model, name):
        return bool(name) and name in model._fields and model._fields[name].store

    @api.model
    def _apply_window(self, model, spec, start, end):
        field_name = spec.get("date_field")
        if not start or not end or not self._field_ok(model, field_name):
            return []
        field = model._fields[field_name]
        if field.type == "datetime":
            start_dt = datetime.combine(start, time.min)
            end_dt = datetime.combine(end, time.max)
            return [(field_name, ">=", start_dt), (field_name, "<=", end_dt)]
        return [(field_name, ">=", start), (field_name, "<=", end)]

    @api.model
    def _text_domain(self, model, spec, tokens, phrases):
        needles = list(phrases)
        needles.extend(tokens[:6])
        fields_to_search = [name for name in spec.get("search_fields", ()) if self._field_ok(model, name)]
        if not needles or not fields_to_search:
            return []
        parts = []
        for needle in needles:
            for name in fields_to_search:
                parts.append((name, "ilike", needle))
        return _or(parts)

    @api.model
    def _display(self, record, field_name):
        if field_name not in record._fields:
            return ""
        field = record._fields[field_name]
        try:
            value = record[field_name]
        except AccessError:
            return ""
        if field.type == "many2one":
            return value.display_name if value else ""
        if field.type == "selection":
            selection = field.selection(record) if callable(field.selection) else field.selection
            return dict(selection or []).get(value, value or "")
        if field.type == "date":
            return fields.Date.to_string(value) if value else ""
        if field.type == "datetime":
            return fields.Datetime.to_string(value) if value else ""
        if field.type == "html":
            return html2plaintext(value or "")[:240]
        if field.type == "boolean":
            return _("Yes") if value else _("No")
        if field.type in ("float", "monetary", "integer"):
            return value if value not in (False, None) else ""
        if not value:
            return ""
        return str(value)[:240]

    @api.model
    def _row(self, record, spec):
        columns = [name for name in spec.get("list_fields", ()) if name in record._fields]
        values = {name: self._display(record, name) for name in columns}
        label = values.get("name") or values.get(columns[0] if columns else "name") or record.display_name
        return {
            "id": record.id,
            "model": record._name,
            "label": label,
            "values": values,
        }

    @api.model
    def _search_source(self, spec, question, flags, window, id_domain=None):
        model_name = spec["model"]
        label = spec["label"]
        if model_name not in self.env:
            return {
                "key": spec["key"],
                "model": model_name,
                "label": label,
                "kind": spec["kind"],
                "status": "unavailable",
                "reason": _("%(module)s is not installed, so %(label)s cannot be searched.") % {
                    "module": spec["module"],
                    "label": label,
                },
                "count": 0,
                "records": [],
                "ids": [],
            }
        model = self.env[model_name]
        if not model.has_access("read"):
            return {
                "key": spec["key"],
                "model": model_name,
                "label": label,
                "kind": spec["kind"],
                "status": "restricted",
                "reason": _("You do not have permission to read %s.") % label,
                "count": 0,
                "records": [],
                "ids": [],
            }
        start, end, _period = window
        today = fields.Date.context_today(self)
        domain = list(spec["domain"](model, today, flags) or [])
        domain += self._apply_window(model, spec, start, end)
        if id_domain:
            domain += id_domain
        else:
            tokens, phrases = self._content_tokens(question)
            structured = bool(
                flags.get("overdue") or flags.get("service") or flags.get("summary")
                or flags.get("open") or start
            )
            if phrases or (tokens and not structured):
                domain += self._text_domain(model, spec, [] if structured else tokens, phrases)
        try:
            count = model.search_count(domain)
            records = model.search(domain, limit=ROW_LIMIT, order=spec.get("order") or "id desc")
        except AccessError:
            return {
                "key": spec["key"],
                "model": model_name,
                "label": label,
                "kind": spec["kind"],
                "status": "restricted",
                "reason": _("You do not have permission to read %s.") % label,
                "count": 0,
                "records": [],
                "ids": [],
            }
        except Exception:
            _logger.exception("AI Copilot could not search %s", model_name)
            return {
                "key": spec["key"],
                "model": model_name,
                "label": label,
                "kind": spec["kind"],
                "status": "unavailable",
                "reason": _("Could not search %s.") % label,
                "count": 0,
                "records": [],
                "ids": [],
            }
        rows = [self._row(record, spec) for record in records]
        note = spec.get("note") or ""
        measure = None
        if spec.get("measure") and spec["measure"] in model._fields and count:
            values = records.mapped(spec["measure"])
            measure = {
                "field": spec["measure"],
                "sample_total": round(sum(values), 3),
                "sample_size": len(values),
                "total_count": count,
            }
        return {
            "key": spec["key"],
            "model": model_name,
            "label": label,
            "kind": spec["kind"],
            "status": "ok" if count else "empty",
            "reason": "",
            "count": count,
            "records": rows,
            "ids": records.ids,
            "note": note,
            "measure": measure,
            "domain_note": "",
        }

    @api.model
    def _energy_compare(self, question):
        spec = next(item for item in SOURCES if item["key"] == "iot_energy")
        if "integration.iot.energy.reading" not in self.env:
            return self._search_source(spec, question, self._flags(question), (None, None, ""))
        model = self.env["integration.iot.energy.reading"]
        if not model.has_access("read") or "kwh" not in model._fields or "captured_at" not in model._fields:
            pack = self._search_source(spec, question, self._flags(question), (None, None, ""))
            if model.has_access("read"):
                pack["status"] = "unavailable"
                pack["reason"] = _("Energy readings do not expose a comparable kWh history.")
            return pack
        today = fields.Date.context_today(self)
        this_start = today.replace(day=1)
        previous_end = this_start - timedelta(days=1)
        previous_start = previous_end.replace(day=1)
        windows = (
            (_("this month"), this_start, today),
            (_("last month"), previous_start, previous_end),
        )
        periods = []
        for label, start, end in windows:
            start_dt = datetime.combine(start, time.min)
            end_dt = datetime.combine(end, time.max)
            domain = [("captured_at", ">=", start_dt), ("captured_at", "<=", end_dt)]
            records = model.search(domain)
            periods.append({
                "label": label,
                "count": len(records),
                "kwh": round(sum(records.mapped("kwh")), 3),
            })
        total = sum(item["count"] for item in periods)
        return {
            "key": spec["key"],
            "model": model._name,
            "label": spec["label"],
            "kind": "fms_data",
            "status": "ok" if total else "empty",
            "reason": "",
            "count": total,
            "records": [],
            "ids": [],
            "note": "",
            "measure": None,
            "periods": periods,
        }

    @api.model
    def _search_knowledge(self, question, id_domain=None):
        document_model = self.env["ai.copilot.document"]
        if not document_model.has_access("read"):
            return {
                "status": "restricted",
                "reason": _("You do not have permission to read knowledge documents."),
                "count": 0,
                "records": [],
            }
        tokens, phrases = self._content_tokens(question)
        needles = list(phrases)
        needles.extend(tokens[:6])
        domain = [("active", "=", True)]
        if id_domain:
            domain += id_domain
        elif needles:
            parts = []
            for needle in needles:
                parts.extend([
                    ("name", "ilike", needle),
                    ("summary", "ilike", needle),
                    ("body", "ilike", needle),
                ])
            domain += _or(parts)
        elif not self._flags(question).get("knowledge"):
            return {"status": "empty", "reason": "", "count": 0, "records": []}
        records = document_model.search(domain, limit=ROW_LIMIT, order="name")
        count = document_model.search_count(domain)
        rows = []
        for record in records:
            rows.append({
                "id": record.id,
                "model": record._name,
                "label": record.name,
                "category": record.category,
                "excerpt": (record.summary or html2plaintext(record.body or ""))[:400],
                "kind": "knowledge",
            })
        return {
            "status": "ok" if count else "empty",
            "reason": "",
            "count": count,
            "records": rows,
        }

    @api.model
    def _current_record(self, context):
        context = context or {}
        model_name = context.get("model") or ""
        res_id = context.get("res_id") or False
        if not model_name:
            return None
        if model_name not in self.env:
            return {
                "status": "unavailable",
                "model": model_name,
                "reason": _("The current screen model is not installed."),
            }
        model = self.env[model_name]
        if not model.has_access("read"):
            return {
                "status": "restricted",
                "model": model_name,
                "reason": _("You do not have permission to read records on this screen."),
            }
        help_states = []
        state_field = model._fields.get("state")
        if state_field and state_field.type == "selection":
            selection = state_field.selection(model) if callable(state_field.selection) else state_field.selection
            help_states = [{"value": key, "label": label} for key, label in (selection or [])]
        payload = {
            "status": "help",
            "model": model_name,
            "description": model._description,
            "states": help_states,
            "record": None,
        }
        if not res_id:
            return payload
        try:
            res_id = int(res_id)
        except (TypeError, ValueError):
            return payload
        record = model.search([("id", "=", res_id)], limit=1)
        if not record:
            payload["status"] = "unavailable"
            payload["reason"] = _("That record is not available to you.")
            return payload
        fields_to_read = []
        for name, field in model._fields.items():
            if name in ("id", "display_name") or not field.store or field.type in ("binary", "one2many", "many2many", "html"):
                continue
            if field.type in ("char", "selection", "date", "datetime", "many2one", "boolean", "integer", "float"):
                fields_to_read.append(name)
            if len(fields_to_read) >= 12:
                break
        payload["status"] = "ok"
        payload["record"] = {
            "id": record.id,
            "model": model_name,
            "label": record.display_name,
            "values": {name: self._display(record, name) for name in fields_to_read},
        }
        return payload

    @api.model
    def _capabilities(self):
        labels = []
        for spec in SOURCES:
            if spec["model"] not in self.env:
                continue
            if self.env[spec["model"]].has_access("read"):
                labels.append(spec["label"])
        if self.env["ai.copilot.document"].has_access("read"):
            labels.append(_("Knowledge documents"))
        return labels

    @api.model
    def _recommendations(self, packs, knowledge):
        items = []
        for pack in packs:
            if pack["status"] != "ok" or not pack["count"]:
                continue
            items.append({
                "title": _("Review %s") % pack["label"],
                "detail": _(
                    "%(count)s %(label)s record(s) matched this question in data you can access."
                ) % {"count": pack["count"], "label": pack["label"]},
                "model": pack["model"],
                "ids": pack.get("ids") or [],
            })
        if knowledge.get("count"):
            items.append({
                "title": _("Check the cited knowledge documents"),
                "detail": _(
                    "%s approved document(s) matched. Read them before acting on the guidance."
                ) % knowledge["count"],
                "model": "ai.copilot.document",
                "ids": [row["id"] for row in knowledge.get("records", [])],
            })
        return items[:4]

    @api.model
    def _result_table(self, pack):
        records = pack.get("records") or []
        if not records:
            return None
        columns = []
        seen = []
        for name in records[0]["values"]:
            field = self.env[pack["model"]]._fields.get(name) if pack["model"] in self.env else None
            columns.append({"key": name, "label": field.string if field else name})
            seen.append(name)
        return {
            "title": pack["label"],
            "model": pack["model"],
            "ids": pack.get("ids") or [],
            "total": pack["count"],
            "columns": columns,
            "rows": [{"id": row["id"], "cells": [row["values"].get(key, "") for key in seen]} for row in records],
        }

    @api.model
    def _prepare_proposal(self, question, packs):
        flags = self._flags(question)
        if not flags.get("create"):
            return None
        target = None
        for model_name, meta in PROPOSAL_MODELS.items():
            if model_name in self.env and self.env[model_name].has_access("create"):
                target = (model_name, meta)
                if model_name == "maintenance.request":
                    break
        title = _("Create Maintenance Task")
        issue = (question or "").strip()
        if not target:
            return {
                "status": "unavailable",
                "title": title,
                "reason": _(
                    "No maintenance or service-request model is installed that you are allowed to create."
                ),
                "lines": [],
                "can_confirm": False,
            }
        model_name, meta = target
        subject = ""
        for pack in packs:
            if pack.get("records"):
                subject = pack["records"][0]["label"]
                break
        if model_name == "mobile.service.request":
            vals = {
                "category": subject or _("Facility"),
                "description": issue,
            }
            lines = [
                {"label": _("Category"), "value": vals["category"]},
                {"label": _("Description"), "value": issue[:240]},
            ]
        else:
            vals = {"name": (subject or issue)[:120]}
            if "description" in self.env[model_name]._fields:
                vals["description"] = issue
            lines = [{"label": _("Subject"), "value": vals["name"]}]
            if "description" in vals:
                lines.append({"label": _("Description"), "value": issue[:240]})
        return {
            "status": "pending",
            "title": meta["title"],
            "model": model_name,
            "vals": vals,
            "lines": lines,
            "reason": "",
            "can_confirm": True,
        }

    @api.model
    def _compose(self, question, packs, knowledge, current, proposal):
        usable = [pack for pack in packs if pack["status"] == "ok" and pack["count"]]
        restricted = [pack for pack in packs if pack["status"] == "restricted"]
        unavailable = [pack for pack in packs if pack["status"] == "unavailable"]
        empty = [pack for pack in packs if pack["status"] == "empty"]
        knowledge_hits = knowledge.get("records") or []
        sections = []
        sources = []
        for pack in packs:
            sources.append({
                "label": pack["label"],
                "kind": pack["kind"],
                "model": pack["model"] if pack["status"] == "ok" else False,
                "res_id": (pack.get("records") or [{}])[0].get("id") if pack["status"] == "ok" else False,
                "status": pack["status"],
                "count": pack["count"],
                "reason": pack.get("reason") or "",
            })
        for row in knowledge_hits:
            sources.append({
                "label": row["label"],
                "kind": "knowledge",
                "model": "ai.copilot.document",
                "res_id": row["id"],
                "status": "ok",
                "count": 1,
                "reason": "",
            })

        if not packs and not knowledge_hits and not (current and current.get("record")):
            labels = self._capabilities()
            text = _("Tell me which facility records you want to look up.")
            if labels:
                text = _(
                    "I can search these sources you are allowed to read: %(sources)s. Ask a specific question and I will only use records you can access."
                ) % {"sources": ", ".join(labels)}
            return {
                "status": "ok",
                "answer": text,
                "answer_kind": "guidance",
                "sections": [],
                "sources": [],
                "recommendations": [],
                "table": None,
                "stats": None,
                "proposal": None,
            }

        if packs and not usable and not knowledge_hits and restricted and not empty and not unavailable:
            return {
                "status": "restricted",
                "answer": restricted[0]["reason"],
                "answer_kind": "fms_data",
                "sections": [],
                "sources": sources,
                "recommendations": [],
                "table": None,
                "stats": None,
                "proposal": None,
            }
        if packs and not usable and not knowledge_hits and unavailable and not empty and not restricted:
            return {
                "status": "unavailable",
                "answer": unavailable[0]["reason"],
                "answer_kind": "fms_data",
                "sections": [],
                "sources": sources,
                "recommendations": [],
                "table": None,
                "stats": None,
                "proposal": None,
            }
        if packs and not usable and not knowledge_hits and not (current and current.get("status") == "ok"):
            if restricted and not empty:
                status = "restricted"
                answer = restricted[0]["reason"]
            elif unavailable and not empty:
                status = "unavailable"
                answer = unavailable[0]["reason"]
            else:
                status = "no_results"
                answer = _("No matching records were found in the sources you can access.")
            return {
                "status": status,
                "answer": answer,
                "answer_kind": "fms_data",
                "sections": [],
                "sources": sources,
                "recommendations": [],
                "table": None,
                "stats": None,
                "proposal": proposal if proposal and proposal.get("status") == "pending" else None,
            }

        sentences = []
        primary = usable[0] if usable else None
        table = self._result_table(primary) if primary and not primary.get("periods") else None
        stats = None
        if primary and primary.get("periods"):
            bits = []
            for period in primary["periods"]:
                bits.append(_("%(kwh)s kWh across %(count)s reading(s) %(label)s") % period)
                sentences.append(bits[-1])
            stats = {
                "title": _("Energy"),
                "period": _("This month and last month"),
                "total": primary["periods"][0]["kwh"] if primary["periods"] else 0,
                "total_label": _("kWh this month"),
                "lines": [
                    {"label": period["label"], "count": period["kwh"], "tone": "info"}
                    for period in primary["periods"]
                ],
            }
            sentences = [_("Energy readings you can access: %s.") % "; ".join(
                _("%(kwh)s kWh (%(count)s readings, %(label)s)") % period for period in primary["periods"]
            )]
        elif primary:
            window = self._window(question)
            period = window[2]
            period_bit = _(" for %s") % period if period else ""
            sentences.append(_(
                "I found %(count)s %(label)s record(s)%(period)s that you are allowed to read."
            ) % {"count": primary["count"], "label": primary["label"], "period": period_bit})
            if primary.get("note"):
                sentences.append(primary["note"])
            if len(usable) > 1:
                extra = ", ".join(_("%(count)s %(label)s") % pack for pack in usable[1:])
                sentences.append(_("Also matched: %s.") % extra)
        if knowledge_hits:
            sentences.append(_(
                "I found %(count)s knowledge document(s). The excerpts below are from those documents."
            ) % {"count": knowledge["count"]})
            for row in knowledge_hits[:3]:
                sections.append({
                    "kind": "knowledge",
                    "title": row["label"],
                    "text": row["excerpt"],
                })
        if current and current.get("status") == "restricted":
            sentences.append(current["reason"])
        elif current and current.get("record"):
            record = current["record"]
            sections.append({
                "kind": "fms_data",
                "title": record["label"],
                "text": "; ".join(
                    "%s: %s" % (key, value) for key, value in record["values"].items() if value
                ),
            })
            if current.get("states"):
                sections.append({
                    "kind": "guidance",
                    "title": _("Status values"),
                    "text": ", ".join("%s (%s)" % (item["label"], item["value"]) for item in current["states"]),
                })
        elif current and current.get("states") and self._flags(question).get("help"):
            sections.append({
                "kind": "guidance",
                "title": current.get("description") or current["model"],
                "text": _("Status values: %s") % ", ".join(item["label"] for item in current["states"]),
            })
        for pack in restricted:
            sentences.append(pack["reason"])
        for pack in unavailable:
            sentences.append(pack["reason"])
        recommendations = self._recommendations(usable, knowledge if knowledge_hits else {"count": 0})
        answer_kind = "knowledge" if knowledge_hits and not usable else "fms_data"
        if sections and any(item["kind"] == "guidance" for item in sections) and not usable:
            answer_kind = "guidance"
        return {
            "status": "ok",
            "answer": " ".join(sentences).strip(),
            "answer_kind": answer_kind,
            "sections": sections,
            "sources": [source for source in sources if source["status"] == "ok" or source["status"] == "restricted"],
            "recommendations": recommendations,
            "table": table,
            "stats": stats,
            "proposal": proposal,
        }

    @api.model
    def retrieve(self, question, context=None, memory=None):
        context = context or {}
        memory = memory or {}
        flags = self._flags(question)
        window = self._window(question)
        sources = self._select_sources(question, flags)
        id_domain = None
        if flags.get("followup") and memory.get("last_model") and memory.get("last_ids"):
            remembered = next((spec for spec in SOURCES if spec["model"] == memory["last_model"]), None)
            if remembered:
                sources = [remembered]
                id_domain = [("id", "in", list(memory["last_ids"]))]
            elif memory.get("last_model") == "ai.copilot.document":
                sources = []
        packs = []
        if flags.get("energy"):
            packs.append(self._energy_compare(question))
            sources = [spec for spec in sources if spec["key"] != "iot_energy"]
        for spec in sources:
            packs.append(self._search_source(spec, question, flags, window, id_domain=id_domain))
        if memory.get("last_model") == "ai.copilot.document" and flags.get("followup"):
            knowledge = self._search_knowledge(question, id_domain=[("id", "in", list(memory.get("last_ids") or []))])
        else:
            knowledge = self._search_knowledge(question)
        current = self._current_record(context)
        proposal = self._prepare_proposal(question, packs)
        composed = self._compose(question, packs, knowledge, current, proposal)
        memory_out = dict(memory)
        remembered_pack = next((pack for pack in packs if pack["status"] == "ok" and pack.get("ids")), None)
        if remembered_pack:
            memory_out["last_model"] = remembered_pack["model"]
            memory_out["last_ids"] = remembered_pack["ids"]
        elif knowledge.get("records"):
            memory_out["last_model"] = "ai.copilot.document"
            memory_out["last_ids"] = [row["id"] for row in knowledge["records"]]
        memory_out["screen_model"] = context.get("model") or memory.get("screen_model") or ""
        memory_out["screen_res_id"] = context.get("res_id") or False
        composed["memory"] = memory_out
        composed["context_facts"] = {
            "question": question,
            "packs": [
                {
                    "label": pack["label"],
                    "status": pack["status"],
                    "count": pack["count"],
                    "reason": pack.get("reason") or "",
                    "records": pack.get("records") or [],
                    "periods": pack.get("periods") or [],
                    "note": pack.get("note") or "",
                }
                for pack in packs
            ],
            "knowledge": knowledge.get("records") or [],
            "current": current,
        }
        return composed


def _or(parts):
    parts = [part for part in parts if part]
    if not parts:
        return []
    if len(parts) == 1:
        return [parts[0]]
    domain = ["|"] * (len(parts) - 1)
    domain.extend(parts)
    return domain
