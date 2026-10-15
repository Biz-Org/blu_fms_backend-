import { registry } from "@web/core/registry";
import { CcAction } from "@community_communication/owl/cc_action";
import { FEEDBACK_CATEGORIES, htmlHasText, labelOf, m2mIds, stripHtml } from "@community_communication/owl/utils";

const FIELDS = [
    "name", "subject", "category", "description", "anonymous", "priority", "state",
    "resident_id", "assignee_id", "community_id", "create_date", "attachment_ids",
];

export class CommunityFeedback extends CcAction {
    static template = "community_communication.Feedback";

    get staffOnlyModes() {
        return [];
    }

    get categories() {
        return FEEDBACK_CATEGORIES;
    }

    get tabs() {
        return [
            { id: "all", label: "All Feedback" },
            { id: "submitted", label: "Submitted" },
            { id: "in_progress", label: "In Progress" },
            { id: "resolved", label: "Resolved" },
            { id: "closed", label: "Closed" },
        ];
    }

    emptyForm() {
        return {
            subject: "",
            category: "facility",
            description: "",
            anonymous: false,
            community_id: this.defaultCommunityId(),
            priority: "medium",
            attachment_ids: [],
            pendingFiles: [],
        };
    }

    async load() {
        await this.loadKpis("community.communication.feedback");
        if (this.state.mode === "list") {
            const domain = this.listDomain();
            this.state.total = await this.orm.searchCount("community.communication.feedback", domain);
            this.state.records = await this.orm.searchRead(
                "community.communication.feedback",
                domain,
                FIELDS,
                { limit: this.pageSize, offset: (this.state.page - 1) * this.pageSize, order: "create_date desc" }
            );
        } else if (this.state.mode === "create") {
            this.state.form = this.emptyForm();
            await this.loadFormAttachments([]);
        } else if (this.state.resId) {
            const rows = await this.orm.searchRead("community.communication.feedback", [["id", "=", this.state.resId]], FIELDS);
            this.state.record = rows[0] || null;
            this.state.form.response = "";
            this.state.form.note = "";
            this.state.form.status = this.state.record?.state;
            const attachIds = m2mIds(this.state.record?.attachment_ids);
            this.state.extras.attachments = attachIds.length
                ? await this.orm.searchRead("ir.attachment", [["id", "in", attachIds]], ["name", "mimetype", "file_size"])
                : [];
            this.state.extras.responses = await this.orm.searchRead(
                "community.communication.feedback.response",
                [["feedback_id", "=", this.state.resId]],
                ["body", "author_id", "create_date"]
            );
            this.state.extras.notes = await this.orm.searchRead(
                "community.communication.feedback.note",
                [["feedback_id", "=", this.state.resId]],
                ["body", "author_id", "create_date"]
            ).catch(() => []);
        }
    }

    listDomain() {
        const domain = [];
        if (this.state.search) {
            domain.push("|", ["name", "ilike", this.state.search], ["subject", "ilike", this.state.search]);
        }
        if (this.state.filter && this.state.filter !== "all") {
            domain.push(["state", "=", this.state.filter]);
        }
        return domain;
    }

    categoryLabel(key) {
        return labelOf(FEEDBACK_CATEGORIES, key);
    }

    residentLabel(rec) {
        if (rec.anonymous) {
            return "Anonymous";
        }
        return this.m2oName(rec.resident_id) || "Resident";
    }

    async submit() {
        return this.withBusy("Submitting...", async () => {
            const errors = {};
            if (!(this.state.form.subject || "").trim()) {
                errors.subject = "Subject is required.";
            }
            if (!htmlHasText(this.state.form.description)) {
                errors.description = "Description is required.";
            }
            if (!this.setErrors(errors)) {
                this.notification.add("Please fix the highlighted fields.", { type: "warning" });
                return;
            }
            try {
                const ids = await this.orm.create("community.communication.feedback", [{
                    subject: this.state.form.subject,
                    category: this.state.form.category,
                    description: this.state.form.description,
                    anonymous: Boolean(this.state.form.anonymous),
                    community_id: this.defaultCommunityId(),
                    priority: this.state.form.priority,
                }]);
                await this.persistAttachments("community.communication.feedback", ids[0]);
                this.notification.add("Feedback submitted", { type: "success" });
                await this.setMode("detail", ids[0]);
            } catch (error) {
                await this.notifyError(error);
            }
        });
    }

    async respond() {
        return this.withBusy("Saving...", async () => {
            const rec = this.state.record;
            if (this.state.form.status && this.state.form.status !== rec.state) {
                const map = {
                    in_progress: "action_in_progress",
                    resolved: "action_resolve",
                    closed: "action_close",
                };
                if (map[this.state.form.status]) {
                    await this.call("community.communication.feedback", map[this.state.form.status], [rec.id]);
                }
            }
            if (this.state.form.response) {
                await this.call("community.communication.feedback", "action_respond", [rec.id, this.state.form.response]);
            }
            this.notification.add("Feedback updated", { type: "success" });
            this.reload();
        });
    }

    async saveNote() {
        if (!this.state.form.note) {
            this.setErrors({ note: "Write a note before saving." });
            return;
        }
        return this.withBusy("Saving...", async () => {
            this.setErrors({});
            await this.orm.create("community.communication.feedback.note", [{
                feedback_id: this.state.resId,
                body: this.state.form.note,
            }]);
            this.state.form.note = "";
            this.reload();
        });
    }

    exportList() {
        const rows = [["ID", "Subject", "State"], ...this.state.records.map((r) => [r.name, r.subject, r.state])];
        this.exportRows("feedback.csv", rows);
    }
}

registry.category("actions").add("community_communication.action_feedback", CommunityFeedback);
