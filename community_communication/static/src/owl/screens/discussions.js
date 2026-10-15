import { registry } from "@web/core/registry";
import { CcAction } from "@community_communication/owl/cc_action";
import { DISCUSSION_CATEGORIES, htmlHasText, labelOf, m2mIds, stripHtml } from "@community_communication/owl/utils";

const FIELDS = [
    "title", "body", "category", "state", "is_pinned", "community_id", "author_id",
    "comment_count", "view_count", "last_activity_at", "is_followed", "support_count",
    "oppose_count", "group_id", "create_date", "attachment_ids",
];
const MODEL = "community.communication.discussion";

export class CommunityDiscussions extends CcAction {
    static template = "community_communication.Discussions";

    get categories() {
        return DISCUSSION_CATEGORIES;
    }

    get staffOnlyModes() {
        return [];
    }

    get tabs() {
        const reported = this.state.kpis.find((c) => c.key === "reported");
        const items = [
            { id: "all", label: "All Discussions" },
            { id: "mine", label: "My Discussions" },
            { id: "following", label: "Following" },
        ];
        if (this.state.isOfficer) {
            items.push({ id: "reported", label: "Reported", badge: reported?.value || 0 });
        }
        return items;
    }

    emptyForm() {
        return {
            title: "",
            body: "",
            category: "general",
            community_id: this.defaultCommunityId(),
            is_pinned: false,
            subscribe: true,
            attachment_ids: [],
            pendingFiles: [],
            reply: "",
            reportReason: "",
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
            this.state.extras.thread = await this.call(MODEL, "get_thread_payload", [this.state.resId]);
            this.state.form.reply = this.state.form.reply || "";
            this.state.form.reportReason = this.state.form.reportReason || "";
            const attachIds = m2mIds(this.state.extras.thread?.attachment_ids);
            this.state.extras.attachments = attachIds.length
                ? await this.orm.searchRead("ir.attachment", [["id", "in", attachIds]], ["name", "mimetype", "file_size"])
                : [];
        }
    }

    async loadList() {
        const domain = await this.listDomain();
        this.state.total = await this.orm.searchCount(MODEL, domain);
        this.state.records = await this.orm.searchRead(MODEL, domain, FIELDS, {
            limit: this.pageSize,
            offset: (this.state.page - 1) * this.pageSize,
            order: "is_pinned desc, last_activity_at desc",
        });
    }

    async pendingReportedDiscussionIds() {
        const reports = await this.orm.searchRead(
            "community.communication.report",
            [["state", "=", "pending"], ["res_model", "=", MODEL]],
            ["res_id"]
        );
        return [...new Set(reports.map((row) => row.res_id).filter(Boolean))];
    }

    async listDomain() {
        const domain = this.domainIlike("title", [["state", "!=", "removed"]]);
        if (this.state.filter === "mine") {
            domain.push(["author_id", "=", this.state.userId]);
        }
        if (this.state.filter === "following") {
            domain.push(["follow_ids.user_id", "=", this.state.userId]);
        }
        if (this.state.filter === "reported") {
            const ids = await this.pendingReportedDiscussionIds();
            domain.push(["id", "in", ids.length ? ids : [0]]);
        }
        if (this.state.category) {
            domain.push(["category", "=", this.state.category]);
        }
        return domain;
    }

    categoryLabel(key) {
        return labelOf(DISCUSSION_CATEGORIES, key);
    }

    async save() {
        return this.withBusy("Saving...", async () => {
            const errors = {};
            if (!(this.state.form.title || "").trim()) {
                errors.title = "Title is required.";
            }
            if (!htmlHasText(this.state.form.body)) {
                errors.body = "Content is required.";
            }
            if (!this.setErrors(errors)) {
                this.notification.add("Please fix the highlighted fields.", { type: "warning" });
                return;
            }
            try {
                const ids = await this.orm.create(MODEL, [{
                    title: this.state.form.title,
                    body: this.state.form.body,
                    category: this.state.form.category,
                    community_id: this.defaultCommunityId(),
                }]);
                const id = ids[0];
                await this.persistAttachments(MODEL, id);
                if (this.state.form.is_pinned) {
                    await this.call(MODEL, "action_pin", [id]).catch(() => null);
                }
                if (this.state.form.subscribe) {
                    await this.call(MODEL, "action_follow", [id]).catch(() => null);
                }
                this.notification.add("Discussion created", { type: "success" });
                await this.setMode("detail", id);
            } catch (error) {
                await this.notifyError(error);
            }
        });
    }

    async follow() {
        const method = this.state.extras.thread.is_followed ? "action_unfollow" : "action_follow";
        await this.call(MODEL, method, [this.state.resId]);
        this.reload();
    }

    async react(type) {
        await this.call(MODEL, "action_react", [this.state.resId, type]);
        this.reload();
    }

    async postReply() {
        return this.withBusy("Posting...", async () => {
            if (!htmlHasText(this.state.form.reply)) {
                this.setErrors({ reply: "Write a reply before posting." });
                return;
            }
            this.setErrors({});
            await this.call(MODEL, "action_post_comment", [this.state.resId, this.state.form.reply]);
            this.state.form.reply = "";
            this.reload();
        });
    }

    async reportDiscussion() {
        return this.withBusy("Reporting...", async () => {
            if (!(this.state.form.reportReason || "").trim()) {
                this.setErrors({ reportReason: "Please describe why you are reporting this." });
                return;
            }
            this.setErrors({});
            await this.call(MODEL, "action_report", [this.state.resId, this.state.form.reportReason]);
            this.state.form.reportReason = "";
            this.notification.add("Report submitted", { type: "success" });
        });
    }

    async moderate(method) {
        await this.call(MODEL, method, [this.state.resId]);
        this.reload();
    }

    previewBody() {
        return stripHtml(this.state.form.body).slice(0, 180);
    }
}

registry.category("actions").add("community_communication.action_discussions", CommunityDiscussions);
