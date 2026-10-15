import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { CC_COMPONENTS } from "@community_communication/owl/ui/cc_ui";
import {
    PAGE_SIZE,
    actionParams,
    audienceLabel,
    fileToBase64,
    formatDay,
    formatFileSize,
    formatWhen,
    fromDatetimeLocal,
    guessMimetype,
    htmlHasText,
    labelOf,
    m2mIds,
    statusTone,
    stripHtml,
    toDatetimeLocal,
    validateUploadFile,
} from "@community_communication/owl/utils";

export class CcAction extends Component {
    static props = ["*"];
    static components = { ...CC_COMPONENTS };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this._pendingUploads = [];
        const params = actionParams(this.props);
        this.state = useState({
            mode: params.mode || params.cc_mode || this.defaultMode,
            resId: params.resId || params.cc_res_id || false,
            loading: true,
            records: [],
            total: 0,
            page: 1,
            search: "",
            filter: params.filter || params.cc_filter || "all",
            category: "",
            audience: "",
            kpis: [],
            record: null,
            form: {},
            communities: [],
            buildings: [],
            groups: [],
            venues: [],
            residents: [],
            extras: {},
            confirm: null,
            isOfficer: false,
            userId: user.userId,
            busy: "",
            errors: {},
        });
        onWillStart(async () => {
            this.state.isOfficer = await user.hasGroup("community_communication.group_community_officer");
            this.enforceResidentMode();
            await this.loadLookups();
            await this.reload();
        });
    }

    get staffOnlyModes() {
        return ["create", "edit"];
    }

    get isOfficer() {
        return this.state.isOfficer;
    }

    enforceResidentMode() {
        if (this.state.isOfficer) {
            return;
        }
        if (this.staffOnlyModes.includes(this.state.mode)) {
            this.state.mode = this.defaultMode;
            this.state.resId = false;
        }
    }

    get defaultMode() {
        return "list";
    }

    get pageSize() {
        return PAGE_SIZE;
    }

    m2oId(value) {
        if (Array.isArray(value)) {
            return value[0];
        }
        return value || false;
    }

    m2oName(value) {
        if (Array.isArray(value)) {
            return value[1];
        }
        return value || "";
    }

    m2mIds = m2mIds;
    formatWhen = formatWhen;
    formatDay = formatDay;
    formatFileSize = formatFileSize;
    audienceLabel = audienceLabel;
    labelOf = labelOf;
    statusTone = statusTone;
    stripHtml = stripHtml;
    htmlHasText = htmlHasText;
    toDatetimeLocal = toDatetimeLocal;
    fromDatetimeLocal = fromDatetimeLocal;

    html(value) {
        return markup(value || "");
    }

    async loadLookups() {
        const opts = { limit: 200 };
        this.state.communities = await this.orm.searchRead(
            "community.communication.community",
            [],
            ["name"],
            opts
        );
        this.state.buildings = await this.orm.searchRead(
            "community.communication.building",
            [],
            ["name", "community_id"],
            opts
        );
        this.state.groups = await this.orm.searchRead(
            "community.communication.group",
            [["state", "=", "active"]],
            ["name", "community_id"],
            opts
        );
        this.state.venues = await this.orm.searchRead(
            "community.communication.venue",
            [],
            ["name", "community_id"],
            opts
        );
        this.state.residents = await this.orm.searchRead(
            "community.communication.resident",
            [],
            ["name", "community_id", "unit_id"],
            opts
        ).catch(() => []);
    }

    defaultCommunityId() {
        const fromForm = parseInt(this.state.form?.community_id, 10);
        if (fromForm) {
            return fromForm;
        }
        return this.state.communities[0]?.id || false;
    }

    get communityId() {
        return this.defaultCommunityId();
    }

    buildingsFor(communityId) {
        return this.state.buildings.filter(
            (row) => this.m2oId(row.community_id) === communityId
        );
    }

    groupsFor(communityId) {
        return this.state.groups.filter(
            (row) => this.m2oId(row.community_id) === communityId
        );
    }

    venuesFor(communityId) {
        return this.state.venues.filter(
            (row) => this.m2oId(row.community_id) === communityId
        );
    }

    residentsFor(communityId) {
        return this.state.residents.filter(
            (row) => this.m2oId(row.community_id) === communityId
        );
    }

    async reload() {
        this.state.loading = true;
        try {
            await this.load();
        } finally {
            this.state.loading = false;
        }
    }

    async load() {
        /* screens override */
    }

    setMode(mode, resId = false, extra = {}) {
        if (!this.state.isOfficer && this.staffOnlyModes.includes(mode)) {
            this.notification.add("You do not have permission to do that.", { type: "warning" });
            return;
        }
        this._pendingUploads = [];
        this.state.errors = {};
        this.state.busy = "";
        this.state.mode = mode;
        this.state.resId = resId;
        Object.assign(this.state, extra);
        return this.reload();
    }

    onSearch(value) {
        this.state.search = value;
        this.state.page = 1;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.reload(), 250);
    }

    onPage(page) {
        this.state.page = page;
        this.reload();
    }

    async notifyError(error) {
        const message = error?.data?.message || error?.message || "Action failed";
        this.notification.add(message, { type: "danger" });
    }

    async call(model, method, args = [], kwargs = {}) {
        try {
            return await this.orm.call(model, method, args, kwargs);
        } catch (error) {
            await this.notifyError(error);
            throw error;
        }
    }

    async loadKpis(modelName) {
        this.state.kpis = await this.orm.call(
            "community.communication.dashboard",
            "get_list_kpis",
            [modelName]
        );
    }

    openClient(tag, params = {}) {
        this.action.doAction({
            type: "ir.actions.client",
            tag,
            params,
            name: params.name || "Community",
            target: "current",
        }, { clearBreadcrumbs: true });
    }

    exportRows(filename, rows) {
        const csv = rows
            .map((row) => row.map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(","))
            .join("\n");
        const blob = new Blob([csv], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
    }

    domainIlike(field, extra = []) {
        const domain = [...extra];
        if (this.state.search) {
            domain.push([field, "ilike", this.state.search]);
        }
        return domain;
    }

    fieldClass(name) {
        return this.state.errors[name] ? "o_cc_input is-invalid" : "o_cc_input";
    }

    fieldError(name) {
        return this.state.errors[name] || "";
    }

    setErrors(errors) {
        this.state.errors = errors;
        return !Object.keys(errors).length;
    }

    async withBusy(label, fn) {
        if (this.state.busy) {
            return false;
        }
        this.state.busy = label;
        try {
            return await fn();
        } finally {
            this.state.busy = "";
        }
    }

    audienceVals(form = this.state.form) {
        const type = form.audience_type || "community";
        return {
            audience_type: type,
            building_ids: [[6, 0, type === "buildings" ? m2mIds(form.building_ids) : []]],
            audience_group_ids: [[6, 0, type === "groups" ? m2mIds(form.audience_group_ids) : []]],
        };
    }

    setAudienceType(type) {
        this.state.form.audience_type = type;
        if (type !== "buildings") {
            this.state.form.building_ids = [];
        }
        if (type !== "groups") {
            this.state.form.audience_group_ids = [];
        }
    }

    toggleFormId(field, id) {
        const selected = new Set(m2mIds(this.state.form[field]));
        if (selected.has(id)) {
            selected.delete(id);
        } else {
            selected.add(id);
        }
        this.state.form[field] = [...selected];
    }

    toggleBuilding(id) {
        this.toggleFormId("building_ids", id);
    }

    toggleGroup(id) {
        this.toggleFormId("audience_group_ids", id);
    }

    setBuildingQuery(value) {
        this.state.form.buildingQuery = value;
    }

    setGroupQuery(value) {
        this.state.form.groupQuery = value;
    }

    get pickerBuildings() {
        const query = (this.state.form.buildingQuery || "").toLowerCase();
        return this.buildingsFor(this.state.form.community_id).filter(
            (row) => !query || (row.name || "").toLowerCase().includes(query)
        );
    }

    get pickerGroups() {
        const query = (this.state.form.groupQuery || "").toLowerCase();
        return this.groupsFor(this.state.form.community_id).filter(
            (row) => !query || (row.name || "").toLowerCase().includes(query)
        );
    }

    audiencePreviewLabel() {
        const form = this.state.form || {};
        if (form.audience_type === "buildings") {
            const ids = new Set(m2mIds(form.building_ids));
            const names = this.buildingsFor(form.community_id)
                .filter((row) => ids.has(row.id))
                .map((row) => row.name);
            return names.length ? names.join(", ") : "Specific Buildings / Towers";
        }
        if (form.audience_type === "groups") {
            const ids = new Set(m2mIds(form.audience_group_ids));
            const names = this.groupsFor(form.community_id)
                .filter((row) => ids.has(row.id))
                .map((row) => row.name);
            return names.length ? names.join(", ") : "Specific Resident Groups";
        }
        return "Entire Community";
    }

    get attachmentList() {
        const saved = (this.state.extras.formAttachments || []).filter((file) =>
            m2mIds(this.state.form.attachment_ids).includes(file.id)
        );
        const pending = this.state.form.pendingFiles || [];
        return [...saved, ...pending];
    }

    async loadFormAttachments(ids) {
        const cleaned = m2mIds(ids);
        this.state.form.attachment_ids = cleaned;
        this.state.form.pendingFiles = [];
        this._pendingUploads = [];
        this.state.extras.formAttachments = cleaned.length
            ? await this.orm.searchRead(
                "ir.attachment",
                [["id", "in", cleaned]],
                ["name", "mimetype", "file_size"]
            )
            : [];
    }

    async onFilesSelected(fileList) {
        const files = Array.from(fileList || []);
        if (!files.length) {
            return;
        }
        const errors = { ...this.state.errors };
        delete errors.attachments;
        const pendingMeta = [...(this.state.form.pendingFiles || [])];
        this._pendingUploads = this._pendingUploads || [];
        for (const file of files) {
            const invalid = validateUploadFile(file);
            if (invalid) {
                errors.attachments = invalid;
                continue;
            }
            const datas = await fileToBase64(file);
            const key = `p-${Date.now()}-${Math.random().toString(16).slice(2)}`;
            const mimetype = guessMimetype(file.name, file.type);
            this._pendingUploads.push({ key, name: file.name, size: file.size, mimetype, datas });
            pendingMeta.push({ key, name: file.name, size: file.size, mimetype });
        }
        this.state.form.pendingFiles = pendingMeta;
        this.state.errors = errors;
    }

    removeAttachment(file) {
        if (file.id) {
            this.state.form.attachment_ids = m2mIds(this.state.form.attachment_ids).filter((id) => id !== file.id);
            this.state.extras.formAttachments = (this.state.extras.formAttachments || []).filter(
                (row) => row.id !== file.id
            );
            return;
        }
        this._pendingUploads = (this._pendingUploads || []).filter((row) => row.key !== file.key);
        this.state.form.pendingFiles = (this.state.form.pendingFiles || []).filter((row) => row.key !== file.key);
    }

    async persistAttachments(model, resId) {
        const pending = [...(this._pendingUploads || [])];
        const existing = m2mIds(this.state.form.attachment_ids);
        await this.call(model, "action_set_attachments", [resId, existing]);
        if (pending.length) {
            const created = await this.call(model, "action_upload_attachments", [resId, pending.map((file) => ({
                name: file.name,
                datas: file.datas,
                mimetype: file.mimetype,
            }))]);
            this.state.form.attachment_ids = [...existing, ...created];
        }
        this._pendingUploads = [];
        this.state.form.pendingFiles = [];
        return this.state.form.attachment_ids;
    }

    validateAudience(errors, form = this.state.form) {
        if (form.audience_type === "buildings" && !m2mIds(form.building_ids).length) {
            errors.audience = "Select at least one building.";
        }
        if (form.audience_type === "groups" && !m2mIds(form.audience_group_ids).length) {
            errors.audience = "Select at least one resident group.";
        }
        return errors;
    }

    validateSchedule(errors, form = this.state.form, { requireLater = false } = {}) {
        if (form.publish_mode === "later") {
            if (!form.date_publish) {
                errors.date_publish = "Set a publish date and time.";
            } else {
                const when = new Date(form.date_publish);
                if (Number.isNaN(when.getTime()) || when.getTime() <= Date.now()) {
                    errors.date_publish = "Scheduled publish date must be in the future.";
                }
            }
        } else if (requireLater && !form.date_publish) {
            errors.date_publish = "Set a publish date and time.";
        }
        if (form.date_publish && form.date_expiry) {
            const publish = new Date(form.date_publish);
            const expiry = new Date(form.date_expiry);
            if (!Number.isNaN(publish.getTime()) && !Number.isNaN(expiry.getTime()) && expiry < publish) {
                errors.date_expiry = "Expiry must be after the publish date.";
            }
        }
        return errors;
    }
}
