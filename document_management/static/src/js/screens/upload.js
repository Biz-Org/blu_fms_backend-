/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SHELL_PROPS, extractError, readFileAsPayload } from "../dm_utils";

export class UploadScreen extends Component {
    static template = "document_management.Upload";
    static props = SHELL_PROPS;

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: false,
            error: null,
            result: null,
            duplicate: null,
            form: this.emptyForm(),
            file: null,
            createNewVersion: false,
            tagDraft: "",
        });
        onWillStart(() => this.refresh());
    }

    emptyForm() {
        return {
            name: "",
            description: "",
            type_id: "",
            category_id: "",
            folder_id: "",
            department_label: "",
            access_level: "role_restricted",
            owner_id: this.props.session.uid || "",
            effective_date: "",
            expiry_date: "",
            expiry_notify: true,
            tags: "",
        };
    }

    get catalogs() {
        return this.props.session.catalogs || { types: [], categories: [], folders: [], tags: [] };
    }

    get users() {
        return this.props.session.users || [];
    }

    get isEmpty() {
        return false;
    }

    get tagItems() {
        return String(this.state.form.tags || "")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean);
    }

    onTagKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        this.addTag();
    }

    addTag() {
        const name = String(this.state.tagDraft || "").trim();
        if (!name) {
            return;
        }
        const items = this.tagItems;
        if (!items.some((item) => item.toLowerCase() === name.toLowerCase())) {
            items.push(name);
            this.state.form.tags = items.join(", ");
        }
        this.state.tagDraft = "";
    }

    removeTag(ev) {
        const name = ev.currentTarget.dataset.tag;
        this.state.form.tags = this.tagItems.filter((item) => item !== name).join(", ");
    }

    async refresh() {
        this.state.error = null;
        this.state.loading = false;
    }

    cancel() {
        this.state.form = this.emptyForm();
        this.state.file = null;
        this.state.duplicate = null;
        this.state.result = null;
        this.state.error = null;
        this.state.createNewVersion = false;
    }

    onFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        this.state.file = file || null;
        if (file && !this.state.form.name) {
            this.state.form.name = file.name.replace(/\.[^.]+$/, "");
        }
    }

    onDrop(ev) {
        ev.preventDefault();
        const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
        this.state.file = file || this.state.file;
        if (file && !this.state.form.name) {
            this.state.form.name = file.name.replace(/\.[^.]+$/, "");
        }
    }

    onDragOver(ev) {
        ev.preventDefault();
    }

    async resolveTags() {
        const names = String(this.state.form.tags || "")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean);
        const ids = [];
        for (const name of names) {
            const existing = (this.catalogs.tags || []).find((tag) => tag.name.toLowerCase() === name.toLowerCase());
            if (existing) {
                ids.push(existing.id);
            } else {
                const created = await this.orm.call("document.management.ui.api", "create_tag", [{ name }]);
                ids.push(created.id);
            }
        }
        return ids;
    }

    async vals() {
        const form = this.state.form;
        const vals = {
            name: form.name,
            description: form.description,
            access_level: form.access_level,
            department_label: form.department_label,
            expiry_notify: !!form.expiry_notify,
            create_new_version: this.state.createNewVersion,
        };
        if (form.type_id) {
            vals.type_id = Number(form.type_id);
        }
        if (form.category_id) {
            vals.category_id = Number(form.category_id);
        }
        if (form.folder_id) {
            vals.folder_id = Number(form.folder_id);
        }
        if (form.owner_id) {
            vals.owner_id = Number(form.owner_id);
        }
        if (form.effective_date) {
            vals.effective_date = form.effective_date;
        }
        if (form.expiry_date) {
            vals.expiry_date = form.expiry_date;
        }
        const tagIds = await this.resolveTags();
        if (tagIds.length) {
            vals.tag_ids = [[6, 0, tagIds]];
        }
        return vals;
    }

    async filePayload() {
        if (!this.state.file) {
            return {};
        }
        return readFileAsPayload(this.state.file);
    }

    async saveDraft() {
        await this.submit("create_draft", false);
    }

    async uploadDoc() {
        await this.submit("upload_document", true);
    }

    async submit(method, fileRequired) {
        this.state.error = null;
        this.state.result = null;
        this.state.duplicate = null;
        this.state.loading = true;
        try {
            const payload = await this.filePayload();
            if (fileRequired && !payload.datas) {
                throw new Error("A file is required.");
            }
            if (payload.filename) {
                const check = await this.orm.call("document.management.ui.api", "validate_upload", [
                    payload.filename,
                    payload.mimetype,
                    payload.size,
                    this.state.form.folder_id || false,
                    this.state.form.name,
                ]);
                if (!check.ok) {
                    throw new Error((check.errors || []).join(" "));
                }
            }
            const data = await this.orm.call("document.management.ui.api", method, [await this.vals(), payload]);
            if (data && data.duplicate) {
                this.state.duplicate = data;
            } else {
                this.state.result = data;
                if (this.props.refreshSession) {
                    await this.props.refreshSession();
                }
                if (this.props.navigate && data && data.id) {
                    this.props.navigate("details", { documentId: data.id });
                }
            }
        } catch (err) {
            this.state.error = extractError(err);
        } finally {
            this.state.loading = false;
        }
    }

    useNewVersion() {
        this.state.createNewVersion = true;
        this.state.duplicate = null;
        this.uploadDoc();
    }
}
