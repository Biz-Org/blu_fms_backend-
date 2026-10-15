import { registry } from "@web/core/registry";
import { CcAction } from "@community_communication/owl/cc_action";
import { GROUP_CATEGORIES, fileToBase64, guessMimetype, labelOf, stripHtml, validateUploadFile } from "@community_communication/owl/utils";

const FIELDS = [
    "name", "description", "category", "visibility", "state", "member_count",
    "community_id", "image_1920", "create_date",
];

export class CommunityGroups extends CcAction {
    static template = "community_communication.Groups";

    get categories() {
        return GROUP_CATEGORIES;
    }

    get detailTabs() {
        return [
            { id: "overview", label: "Overview" },
            { id: "members", label: "Members" },
            { id: "discussions", label: "Discussions" },
        ];
    }

    emptyForm() {
        return {
            name: "",
            description: "",
            category: "other",
            visibility: "public",
            community_id: this.defaultCommunityId(),
            coverName: "",
            coverSize: 0,
            coverMime: "",
            add_resident_id: false,
        };
    }

    async load() {
        await this.loadKpis("community.communication.group");
        const mine = await this.orm.searchRead(
            "community.communication.group.member",
            [["resident_id.user_id", "=", this.state.userId], ["state", "in", ["member", "requested", "invited"]]],
            ["group_id", "state", "role"]
        ).catch(() => []);
        this.state.extras.membership = Object.fromEntries(
            mine.map((row) => [this.m2oId(row.group_id), row])
        );
        if (this.state.mode === "list") {
            const domain = this.listDomain();
            this.state.total = await this.orm.searchCount("community.communication.group", domain);
            this.state.records = await this.orm.searchRead(
                "community.communication.group",
                domain,
                FIELDS,
                { limit: 24, offset: (this.state.page - 1) * 24, order: "name" }
            );
        } else if (this.state.mode === "create") {
            this.state.form = this.emptyForm();
        } else if (this.state.resId) {
            const rows = await this.orm.searchRead("community.communication.group", [["id", "=", this.state.resId]], FIELDS);
            this.state.record = rows[0] || null;
            this.state.form.add_resident_id = false;
            this.state.extras.tab = this.state.extras.tab || "overview";
            this.state.extras.members = await this.orm.searchRead(
                "community.communication.group.member",
                [["group_id", "=", this.state.resId], ["state", "=", "member"]],
                ["resident_id", "role", "state"]
            );
            this.state.extras.discussions = await this.orm.searchRead(
                "community.communication.discussion",
                [["group_id", "=", this.state.resId], ["state", "!=", "removed"]],
                ["title", "author_id", "last_activity_at", "comment_count"],
                { limit: 8, order: "last_activity_at desc" }
            );
        }
    }

    listDomain() {
        const domain = this.domainIlike("name", [["state", "=", "active"]]);
        if (this.state.category) {
            domain.push(["category", "=", this.state.category]);
        }
        if (this.state.filter && this.state.filter !== "all") {
            domain.push(["visibility", "=", this.state.filter]);
        }
        return domain;
    }

    categoryLabel(key) {
        return labelOf(GROUP_CATEGORIES, key);
    }

    membership(id) {
        return (this.state.extras.membership || {})[id];
    }

    imageUrl(rec) {
        return `/web/image/community.communication.group/${rec.id}/image_1920`;
    }

    async join(id) {
        await this.call("community.communication.group", "action_join", [id]);
        this.notification.add("Join request sent", { type: "success" });
        this.reload();
    }

    async leave(id) {
        await this.call("community.communication.group", "action_leave", [id]);
        this.reload();
    }

    async onCoverSelected(fileList) {
        const file = [...(fileList || [])][0];
        if (!file) {
            return;
        }
        const mimetype = guessMimetype(file.name, file.type);
        const invalid = validateUploadFile(file);
        if (invalid || !mimetype.startsWith("image/")) {
            this.setErrors({ cover: invalid || "Use PNG, JPG, or SVG for the cover image." });
            return;
        }
        this._pendingImage = {
            datas: await fileToBase64(file),
            name: file.name,
            size: file.size,
            mimetype,
        };
        this.state.form.coverName = file.name;
        this.state.form.coverSize = file.size;
        this.state.form.coverMime = mimetype;
        this.setErrors({});
    }

    removeCover() {
        this._pendingImage = null;
        this.state.form.coverName = "";
        this.state.form.coverSize = 0;
        this.state.form.coverMime = "";
    }

    get coverList() {
        if (!this.state.form.coverName) {
            return [];
        }
        return [{
            key: "cover",
            name: this.state.form.coverName,
            size: this.state.form.coverSize,
            mimetype: this.state.form.coverMime,
        }];
    }

    get availableResidents() {
        const memberIds = new Set(
            (this.state.extras.members || []).map((row) => this.m2oId(row.resident_id))
        );
        const communityId = this.m2oId(this.state.record?.community_id);
        return this.residentsFor(communityId).filter((row) => !memberIds.has(row.id));
    }

    async addMember() {
        const residentId = parseInt(this.state.form.add_resident_id, 10);
        if (!residentId) {
            this.setErrors({ add_resident_id: "Select a resident to add." });
            return;
        }
        return this.withBusy("Adding...", async () => {
            this.setErrors({});
            await this.call("community.communication.group", "action_add_member", [this.state.resId, residentId]);
            this.state.form.add_resident_id = false;
            this.notification.add("Member added", { type: "success" });
            this.reload();
        });
    }

    async create() {
        return this.withBusy("Saving...", async () => {
            if (!(this.state.form.name || "").trim()) {
                this.setErrors({ name: "Name is required." });
                this.notification.add("Please fix the highlighted fields.", { type: "warning" });
                return;
            }
            this.setErrors({});
            const vals = {
                name: this.state.form.name,
                description: this.state.form.description,
                category: this.state.form.category,
                visibility: this.state.form.visibility,
                community_id: this.defaultCommunityId(),
            };
            if (this._pendingImage?.datas) {
                vals.image_1920 = this._pendingImage.datas;
            }
            try {
                const ids = await this.orm.create("community.communication.group", [vals]);
                this._pendingImage = null;
                this.notification.add("Group created", { type: "success" });
                await this.setMode("detail", ids[0]);
            } catch (error) {
                await this.notifyError(error);
            }
        });
    }

    snippet(rec) {
        return stripHtml(rec.description).slice(0, 120);
    }

    get leaders() {
        return (this.state.extras.members || []).filter((row) => row.role !== "member");
    }

    onGroupCta(rec) {
        const mem = this.membership(rec.id);
        if (mem?.state === "member") {
            this.setMode("detail", rec.id);
        } else {
            this.join(rec.id);
        }
    }

    joinLabel(rec) {
        const mem = this.membership(rec.id);
        if (mem?.state === "member") {
            return "Open Group";
        }
        if (mem?.state === "requested") {
            return "Requested";
        }
        return rec.visibility === "restricted" ? "Request Join" : "Join Group";
    }
}

registry.category("actions").add("community_communication.action_groups", CommunityGroups);
