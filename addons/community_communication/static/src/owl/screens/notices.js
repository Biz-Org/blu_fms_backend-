import { registry } from "@web/core/registry";
import { CcAction } from "@community_communication/owl/cc_action";
import { NOTICE_CATEGORIES, actionParams, htmlHasText, labelOf, m2mIds, stripHtml } from "@community_communication/owl/utils";

const FIELDS = [
    "title", "body", "category", "state", "is_important", "is_pinned", "community_id",
    "audience_type", "date_publish", "date_expiry", "author_id", "attachment_ids",
    "building_ids", "audience_group_ids",
];

export class CommunityNotices extends CcAction {
    static template = "community_communication.Notices";

    get categories() {
        return NOTICE_CATEGORIES;
    }

    get isBoard() {
        const params = actionParams(this.props);
        return Boolean(params.board || params.cc_board);
    }

    emptyForm() {
        return {
            title: "",
            body: "",
            category: "general",
            community_id: this.defaultCommunityId(),
            audience_type: "community",
            date_publish: "",
            date_expiry: "",
            is_pinned: false,
            is_important: false,
            publish_mode: "now",
            building_ids: [],
            audience_group_ids: [],
            attachment_ids: [],
            pendingFiles: [],
            buildingQuery: "",
            groupQuery: "",
        };
    }

    async load() {
        if (this.isBoard && this.state.filter === "all") {
            this.state.filter = "published";
        }
        if (this.state.mode === "list") {
            const domain = this.listDomain();
            this.state.total = await this.orm.searchCount("community.communication.notice", domain);
            this.state.records = await this.orm.searchRead(
                "community.communication.notice",
                domain,
                FIELDS,
                { limit: 24, offset: (this.state.page - 1) * 24, order: "is_pinned desc, date_publish desc" }
            );
        } else if (this.state.mode === "create") {
            this.state.form = this.emptyForm();
            await this.loadFormAttachments([]);
        } else if (this.state.resId) {
            const rows = await this.orm.searchRead("community.communication.notice", [["id", "=", this.state.resId]], FIELDS);
            this.state.record = rows[0] || null;
            if (this.state.record) {
                const attachIds = m2mIds(this.state.record.attachment_ids);
                this.state.extras.attachments = attachIds.length
                    ? await this.orm.searchRead("ir.attachment", [["id", "in", attachIds]], ["name", "mimetype", "file_size"])
                    : [];
            }
            if (this.state.mode === "edit" && this.state.record) {
                this.state.form = {
                    ...this.emptyForm(),
                    ...this.state.record,
                    community_id: this.m2oId(this.state.record.community_id),
                    date_publish: this.toDatetimeLocal(this.state.record.date_publish),
                    date_expiry: this.toDatetimeLocal(this.state.record.date_expiry),
                    publish_mode: this.state.record.state === "scheduled" ? "later" : "now",
                    building_ids: m2mIds(this.state.record.building_ids),
                    audience_group_ids: m2mIds(this.state.record.audience_group_ids),
                    attachment_ids: m2mIds(this.state.record.attachment_ids),
                    pendingFiles: [],
                    buildingQuery: "",
                    groupQuery: "",
                };
                await this.loadFormAttachments(this.state.record.attachment_ids);
            }
        }
    }

    listDomain() {
        const domain = this.domainIlike("title");
        if (this.isBoard) {
            domain.push(["state", "=", "published"]);
        } else if (this.state.filter && this.state.filter !== "all") {
            domain.push(["state", "=", this.state.filter]);
        }
        if (this.state.category) {
            domain.push(["category", "=", this.state.category]);
        }
        return domain;
    }

    categoryLabel(key) {
        return labelOf(NOTICE_CATEGORIES, key);
    }

    snippet(rec) {
        return stripHtml(rec.body).slice(0, 140);
    }

    async save(publish) {
        return this.withBusy(publish ? "Publishing..." : "Saving...", async () => {
            const form = this.state.form;
            const errors = {};
            if (!(form.title || "").trim()) {
                errors.title = "Title is required.";
            }
            if (!htmlHasText(form.body)) {
                errors.body = "Content is required.";
            }
            this.validateAudience(errors, form);
            if (publish || form.publish_mode === "later") {
                this.validateSchedule(errors, form);
            }
            if (!this.setErrors(errors)) {
                this.notification.add("Please fix the highlighted fields.", { type: "warning" });
                return;
            }
            const vals = {
                title: form.title,
                body: form.body,
                category: form.category,
                community_id: this.defaultCommunityId(),
                is_pinned: Boolean(form.is_pinned),
                is_important: Boolean(form.is_important),
                date_publish: form.publish_mode === "later" ? this.fromDatetimeLocal(form.date_publish) : false,
                date_expiry: this.fromDatetimeLocal(form.date_expiry),
                ...this.audienceVals(form),
            };
            let id = this.state.resId;
            try {
                if (this.state.mode === "edit" && id) {
                    await this.orm.write("community.communication.notice", [id], vals);
                } else {
                    id = (await this.orm.create("community.communication.notice", [vals]))[0];
                }
                await this.persistAttachments("community.communication.notice", id);
                if (publish) {
                    if (form.publish_mode === "later") {
                        await this.call("community.communication.notice", "action_schedule", [id]);
                        this.notification.add("Notice scheduled", { type: "success" });
                    } else {
                        await this.call("community.communication.notice", "action_publish", [id]);
                        this.notification.add("Notice published", { type: "success" });
                    }
                } else {
                    this.notification.add("Draft saved", { type: "success" });
                }
                await this.setMode("detail", id);
            } catch (error) {
                if (!error?.data) {
                    await this.notifyError(error);
                }
            }
        });
    }
}

registry.category("actions").add("community_communication.action_notices", CommunityNotices);
