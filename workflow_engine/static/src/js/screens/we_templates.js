/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { extractError, formatDate, statusClass, userLabel } from "../we_utils";
import { MOCK_TEMPLATES } from "../we_mockup";

const FIELDS = [
    "id", "name", "description", "category", "state", "version",
    "required_modules", "usage_count", "owner_id", "active",
];

function emptyForm() {
    return {
        id: null,
        name: "",
        description: "",
        category: "",
        version: "1",
        required_modules: "",
        state: "draft",
    };
}

export class WeTemplates extends Component {
    static template = "workflow_engine.Templates";
    static props = {
        session: { type: Object },
        onNavigate: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            records: [],
            search: "",
            stateFilter: "",
            categoryFilter: "",
            moduleFilter: "",
            viewMode: "grid",
            drawerOpen: false,
            form: emptyForm(),
            preview: null,
            saving: false,
            busyPreview: false,
        });
        onWillStart(() => this.load());
    }

    get canManage() {
        return !!(this.props.session?.is_manager || this.props.session?.is_admin);
    }

    get stats() {
        if (!(this.state.records || []).length) {
            return MOCK_TEMPLATES.stats;
        }
        const recs = this.state.records || [];
        const most = recs.slice().sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0))[0];
        return {
            total: recs.length,
            active: recs.filter((r) => r.state === "active").length,
            draft: recs.filter((r) => r.state === "draft").length,
            mostUsed: most?.name || "—",
        };
    }

    get modules() {
        const set = new Set();
        for (const rec of this.state.records) {
            const raw = rec.required_modules || "";
            String(raw).split(",").map((s) => s.trim()).filter(Boolean).forEach((m) => set.add(m));
        }
        return [...set].sort();
    }

    get categories() {
        const set = new Set();
        for (const rec of this.state.records) {
            if (rec.category) {
                set.add(rec.category);
            }
        }
        return [...set].sort();
    }

    get filtered() {
        const recs = (this.state.records || []).length ? this.state.records : MOCK_TEMPLATES.records;
        const q = this.state.search.trim().toLowerCase();
        return recs.filter((rec) => {
            if (this.state.stateFilter && rec.state !== this.state.stateFilter) {
                return false;
            }
            if (this.state.categoryFilter && rec.category !== this.state.categoryFilter) {
                return false;
            }
            if (this.state.moduleFilter) {
                const mods = String(rec.required_modules || "");
                if (!mods.split(",").map((s) => s.trim()).includes(this.state.moduleFilter)) {
                    return false;
                }
            }
            if (!q) {
                return true;
            }
            return (
                (rec.name || "").toLowerCase().includes(q) ||
                (rec.category || "").toLowerCase().includes(q) ||
                (rec.description || "").toLowerCase().includes(q)
            );
        });
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const result = await this.orm.call("workflow.engine.ui.api", "list_templates", [[], 0, 200]);
            this.state.records = result.records || [];
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.loading = false;
        }
    }

    openCreate() {
        if (!this.canManage) {
            this.notification.add("You need manager access to create templates.", { type: "warning" });
            return;
        }
        this.state.form = emptyForm();
        this.state.preview = null;
        this.state.drawerOpen = true;
    }

    openEdit(rec) {
        if (!this.canManage) {
            return;
        }
        this.state.form = {
            id: rec.id,
            name: rec.name || "",
            description: rec.description || "",
            category: rec.category || "",
            version: rec.version || "1",
            required_modules: rec.required_modules || "",
            state: rec.state || "draft",
        };
        this.state.preview = null;
        this.state.drawerOpen = true;
    }

    closeDrawer() {
        this.state.drawerOpen = false;
        this.state.preview = null;
    }

    async preview(rec) {
        if (typeof rec?.id === "string") {
            this.state.preview = rec;
            this.state.form = emptyForm();
            this.state.drawerOpen = true;
            return;
        }
        this.state.busyPreview = true;
        try {
            this.state.preview = await this.orm.call(
                "workflow.engine.ui.api",
                "preview_template",
                [rec.id]
            );
            this.state.form = emptyForm();
            this.state.drawerOpen = true;
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.busyPreview = false;
        }
    }

    async save() {
        if (!this.canManage || this.state.saving) {
            return;
        }
        const f = this.state.form;
        if (!f.name.trim()) {
            this.notification.add("Name is required.", { type: "danger" });
            return;
        }
        this.state.saving = true;
        try {
            const vals = {
                name: f.name.trim(),
                description: f.description || false,
                category: f.category || false,
                version: f.version || "1",
                required_modules: f.required_modules || false,
            };
            await this.orm.call("workflow.engine.ui.api", "save_template", [f.id || false, vals]);
            this.state.drawerOpen = false;
            await this.load();
            this.notification.add(f.id ? "Template updated." : "Template created.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    async duplicate(rec) {
        if (!this.canManage) {
            return;
        }
        try {
            await this.orm.call("workflow.engine.ui.api", "duplicate_template", [rec.id]);
            await this.load();
            this.notification.add("Template duplicated.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        }
    }

    async activate(rec) {
        if (!this.canManage) {
            return;
        }
        try {
            await this.orm.call("workflow.engine.ui.api", "activate_template", [rec.id]);
            await this.load();
            this.notification.add("Template activated.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        }
    }

    async deactivate(rec) {
        if (!this.canManage) {
            return;
        }
        try {
            await this.orm.call("workflow.engine.ui.api", "deactivate_template", [rec.id]);
            await this.load();
            this.notification.add("Template deactivated.", { type: "success" });
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        }
    }

    async createWorkflow(rec) {
        if (!this.canManage || rec.state !== "active") {
            return;
        }
        try {
            await this.orm.call("workflow.engine.ui.api", "create_workflow_from_template", [rec.id, {}]);
            this.notification.add("Workflow created from template.", { type: "success" });
            if (typeof this.props.onNavigate === "function") {
                this.props.onNavigate("builder");
            }
        } catch (err) {
            this.notification.add(extractError(err), { type: "danger" });
        }
    }

    formatDate = formatDate;
    statusClass = statusClass;
    userLabel = userLabel;
}
