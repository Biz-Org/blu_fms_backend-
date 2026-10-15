import { registry } from "@web/core/registry";
import { CcAction } from "@community_communication/owl/cc_action";
import { ANNOUNCEMENT_CATEGORIES, audienceLabel, htmlHasText, labelOf, m2mIds, stripHtml } from "@community_communication/owl/utils";

const FIELDS = [
    "title", "body", "category", "priority", "state", "is_pinned", "audience_type",
    "community_id", "building_ids", "audience_group_ids", "attachment_ids",
    "author_name", "date_publish", "date_expiry", "view_count", "ack_count",
    "reach_count", "ack_rate", "create_date", "write_date",
];
const MODEL = "community.communication.announcement";

export class CommunityAnnouncements extends CcAction {
    static template = "community_communication.Announcements";

    get categories() {
        return ANNOUNCEMENT_CATEGORIES;
    }

    emptyForm() {
        return {
            title: "",
            body: "",
            category: "general",
            priority: "medium",
            audience_type: "community",
            community_id: this.defaultCommunityId(),
            date_publish: "",
            date_expiry: "",
            publish_mode: "now",
            is_pinned: false,
            building_ids: [],
            audience_group_ids: [],
            attachment_ids: [],
            pendingFiles: [],
            buildingQuery: "",
            groupQuery: "",
        };
    }

    async load() {
        await this.loadKpis(MODEL);
        if (this.state.mode === "list") {
            await this.loadList();
        } else if (this.state.mode === "create") {
            this.state.form = this.emptyForm();
            await this.loadFormAttachments([]);
        } else if (this.state.resId) {
            await this.loadRecord(this.state.resId);
            if (this.state.mode === "edit") {
                this.state.form = this.formFromRecord(this.state.record);
                await this.loadFormAttachments(this.state.record.attachment_ids);
            }
        }
    }

    async loadList() {
        const domain = await this.listDomain();
        this.state.total = await this.orm.searchCount(MODEL, domain);
        this.state.records = await this.orm.searchRead(MODEL, domain, FIELDS, {
            limit: this.pageSize,
            offset: (this.state.page - 1) * this.pageSize,
            order: "is_pinned desc, date_publish desc, id desc",
        });
    }

    async listDomain() {
        const domain = this.domainIlike("title");
        if (this.state.filter && this.state.filter !== "all") {
            if (this.state.filter === "expiring_soon" || this.state.filter === "expiring") {
                const extra = await this.orm.call(
                    "community.communication.dashboard",
                    "announcement_expiring_soon_domain",
                    []
                );
                domain.push(...extra);
            } else {
                domain.push(["state", "=", this.state.filter]);
            }
        }
        if (this.state.category) {
            domain.push(["category", "=", this.state.category]);
        }
        if (this.state.audience) {
            domain.push(["audience_type", "=", this.state.audience]);
        }
        return domain;
    }

    async loadRecord(id) {
        const rows = await this.orm.searchRead(MODEL, [["id", "=", id]], FIELDS);
        this.state.record = rows[0] || null;
        if (this.state.record) {
            await this.call(MODEL, "action_log_view", [id]).catch(() => null);
            const attachIds = m2mIds(this.state.record.attachment_ids);
            this.state.extras.attachments = attachIds.length
                ? await this.orm.searchRead("ir.attachment", [["id", "in", attachIds]], ["name", "mimetype", "file_size"])
                : [];
            this.state.extras.acked = Boolean(
                await this.orm.searchCount("community.communication.announcement.ack", [
                    ["announcement_id", "=", id],
                    ["resident_id.user_id", "=", this.state.userId],
                ])
            );
        }
    }

    formFromRecord(rec) {
        return {
            title: rec.title || "",
            body: rec.body || "",
            category: rec.category || "general",
            priority: rec.priority || "medium",
            audience_type: rec.audience_type || "community",
            community_id: this.m2oId(rec.community_id),
            date_publish: this.toDatetimeLocal(rec.date_publish),
            date_expiry: this.toDatetimeLocal(rec.date_expiry),
            publish_mode: rec.state === "scheduled" ? "later" : "now",
            is_pinned: rec.is_pinned,
            building_ids: m2mIds(rec.building_ids),
            audience_group_ids: m2mIds(rec.audience_group_ids),
            attachment_ids: m2mIds(rec.attachment_ids),
            pendingFiles: [],
            buildingQuery: "",
            groupQuery: "",
        };
    }

    categoryLabel(key) {
        return labelOf(ANNOUNCEMENT_CATEGORIES, key);
    }

    previewBody() {
        return stripHtml(this.state.form.body).slice(0, 180);
    }

    previewMeta() {
        const audience = this.audiencePreviewLabel();
        if (this.state.form.publish_mode === "later" && this.state.form.date_publish) {
            return `${audience} • Scheduled`;
        }
        return `${audience} • Just now`;
    }

    onKpi(card) {
        this.state.filter = card.filter || "all";
        this.state.page = 1;
        this.setMode("list");
    }

    valsFromForm() {
        const form = this.state.form;
        return {
            title: form.title,
            body: form.body,
            category: form.category,
            priority: form.priority,
            community_id: this.defaultCommunityId(),
            is_pinned: Boolean(form.is_pinned),
            date_publish: form.publish_mode === "later" ? this.fromDatetimeLocal(form.date_publish) : false,
            date_expiry: this.fromDatetimeLocal(form.date_expiry),
            ...this.audienceVals(form),
        };
    }

    validateAnnouncement(forPublish) {
        const errors = {};
        const form = this.state.form;
        if (!(form.title || "").trim()) {
            errors.title = "Title is required.";
        }
        if (!form.category) {
            errors.category = "Category is required.";
        }
        if (!htmlHasText(form.body)) {
            errors.body = "Content is required.";
        }
        this.validateAudience(errors, form);
        if (forPublish) {
            this.validateSchedule(errors, form);
        } else if (form.publish_mode === "later") {
            this.validateSchedule(errors, form);
        }
        return this.setErrors(errors);
    }

    async saveDraft() {
        return this.withBusy("Saving...", async () => {
            const id = await this.saveRecord(false);
            if (id) {
                this.notification.add("Draft saved", { type: "success" });
                await this.setMode("detail", id);
            }
        });
    }

    async publish() {
        return this.withBusy("Publishing...", async () => {
            const id = await this.saveRecord(true);
            if (!id) {
                return;
            }
            const form = this.state.form;
            try {
                if (form.publish_mode === "later") {
                    await this.call(MODEL, "action_schedule", [id]);
                    this.notification.add("Announcement scheduled", { type: "success" });
                } else {
                    await this.call(MODEL, "action_publish", [id]);
                    this.notification.add("Announcement published successfully.", { type: "success" });
                }
                await this.setMode("detail", id);
            } catch {
                this.notification.add("Unable to publish announcement. Please try again.", { type: "danger" });
                await this.setMode("detail", id);
            }
        });
    }

    async saveRecord(forPublish) {
        if (!this.validateAnnouncement(forPublish)) {
            this.notification.add("Please fix the highlighted fields.", { type: "warning" });
            return false;
        }
        const vals = this.valsFromForm();
        let id = this.state.resId;
        try {
            if (id && this.state.mode === "edit") {
                await this.orm.write(MODEL, [id], vals);
            } else {
                id = (await this.orm.create(MODEL, [vals]))[0];
                this.state.resId = id;
            }
            await this.persistAttachments(MODEL, id);
            return id;
        } catch (error) {
            await this.notifyError(error);
            return false;
        }
    }

    async acknowledge() {
        await this.call(MODEL, "action_acknowledge", [this.state.resId]);
        this.notification.add("Acknowledged", { type: "success" });
        this.reload();
    }

    audienceText(rec) {
        return audienceLabel(rec);
    }

    ackPct(rec) {
        return Math.round(((rec.ack_rate || 0) * 100));
    }
}

registry.category("actions").add("community_communication.action_announcements", CommunityAnnouncements);
