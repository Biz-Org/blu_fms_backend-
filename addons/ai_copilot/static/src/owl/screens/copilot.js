import { Component, onPatched, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { AiAppShell } from "@ai_copilot/owl/ui/ai_shell";

const KIND_LABELS = {
    fms_data: "FMS data",
    knowledge: "Knowledge base",
    document: "Document",
    ai_summary: "AI summary",
    recommendation: "Recommendation",
    guidance: "Guidance",
};

export class AiCopilot extends Component {
    static template = "ai_copilot.Copilot";
    static components = { AiAppShell };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.thread = useRef("thread");
        this.state = useState({
            panel: "chat",
            loading: true,
            sending: false,
            error: "",
            navOpen: false,
            bootstrap: {
                suggestions: [],
                apps: [],
                provider: {},
                user_name: "",
                company_name: "",
                can_admin: false,
                context: {},
            },
            conversations: [],
            conversationId: false,
            messages: [],
            draft: "",
            facilitySearch: "",
            documents: [],
            docForm: { name: "", category: "sop", summary: "", body: "" },
            settings: {
                enabled: true,
                provider: "none",
                base_url: "https://api.openai.com/v1",
                model_name: "gpt-4o-mini",
                temperature: 0.2,
                api_key: "",
                api_key_set: false,
            },
            settingsMessage: "",
        });
        onWillStart(async () => {
            await this.boot();
        });
        onPatched(() => {
            const node = this.thread.el;
            if (node) {
                node.scrollTop = node.scrollHeight;
            }
        });
    }

    screenContext() {
        const ctx = this.props.action?.context || {};
        return {
            model: ctx.ai_model || "",
            res_id: ctx.ai_res_id || false,
            module: ctx.ai_module || "",
        };
    }

    async boot() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.bootstrap = await this.orm.call("ai.copilot.service", "get_bootstrap", [this.screenContext()]);
            this.state.conversations = await this.orm.call("ai.copilot.service", "list_conversations", []);
            if (this.state.bootstrap.can_admin) {
                const settings = await this.orm.call("ai.copilot.service", "get_settings", []);
                Object.assign(this.state.settings, settings, { api_key: "" });
            }
        } catch (error) {
            this.state.error = this.errorMessage(error);
        } finally {
            this.state.loading = false;
        }
    }

    errorMessage(error) {
        return error?.data?.message || error?.message || "Something went wrong.";
    }

    get suggestions() {
        return this.state.bootstrap.suggestions || [];
    }

    get providerReady() {
        return Boolean(this.state.bootstrap.provider?.configured);
    }

    get contextLabel() {
        const ctx = this.state.bootstrap.context || {};
        if (ctx.model) {
            return ctx.res_id ? `${ctx.model} #${ctx.res_id}` : ctx.model;
        }
        return "";
    }

    kindLabel(kind) {
        return KIND_LABELS[kind] || "FMS data";
    }

    setPanel(panel) {
        this.state.panel = panel;
        this.state.navOpen = false;
        if (panel === "history") {
            this.refreshHistory();
        }
        if (panel === "knowledge") {
            this.refreshDocuments();
        }
        if (panel === "support" && this.state.bootstrap.can_admin) {
            this.action.doAction("ai_copilot.action_ai_copilot_audit");
        }
    }

    toggleNav() {
        this.state.navOpen = !this.state.navOpen;
    }

    async openApp(app) {
        if (app?.action_id) {
            await this.action.doAction(app.action_id, { clearBreadcrumbs: true });
        }
    }

    async refreshHistory() {
        this.state.conversations = await this.orm.call("ai.copilot.service", "list_conversations", []);
    }

    async refreshDocuments() {
        this.state.documents = await this.orm.call("ai.copilot.service", "list_documents", []);
    }

    newChat() {
        this.state.panel = "chat";
        this.state.conversationId = false;
        this.state.messages = [];
        this.state.draft = "";
    }

    async openConversation(conversation) {
        const data = await this.orm.call("ai.copilot.service", "get_conversation", [conversation.id]);
        this.state.conversationId = data.id;
        this.state.messages = data.messages || [];
        this.state.panel = "chat";
    }

    useSuggestion(text) {
        this.state.draft = text;
        this.send();
    }

    onComposerKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.send();
        }
    }

    async send() {
        const question = (this.state.draft || "").trim();
        if (!question || this.state.sending) {
            return;
        }
        this.state.draft = "";
        this.state.sending = true;
        this.state.panel = "chat";
        try {
            const data = await this.orm.call("ai.copilot.service", "ask", [
                this.state.conversationId || false,
                question,
                this.screenContext(),
            ]);
            this.state.conversationId = data.id;
            this.state.messages = data.messages || [];
        } catch (error) {
            this.notification.add(this.errorMessage(error), { type: "danger" });
        } finally {
            this.state.sending = false;
        }
    }

    async retry() {
        const lastUser = [...this.state.messages].reverse().find((message) => message.role === "user");
        if (!lastUser) {
            return;
        }
        this.state.draft = lastUser.body;
        await this.send();
    }

    async feedback(message, value) {
        const next = message.feedback === value ? "none" : value;
        await this.orm.call("ai.copilot.service", "set_feedback", [message.id, next]);
        message.feedback = next;
    }

    async confirmProposal(message) {
        try {
            const result = await this.orm.call("ai.copilot.service", "confirm_action", [message.id]);
            this.state.messages = result.conversation?.messages || this.state.messages;
            this.notification.add("The record was created with your access rights.", { type: "success" });
        } catch (error) {
            this.notification.add(this.errorMessage(error), { type: "danger" });
        }
    }

    async cancelProposal(message) {
        const data = await this.orm.call("ai.copilot.service", "cancel_action", [message.id]);
        this.state.messages = data.messages || this.state.messages;
    }

    openRecord(model, resId) {
        if (!model || !resId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTable(table) {
        if (!table?.model || !table.ids?.length) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: table.title,
            res_model: table.model,
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", table.ids]],
            target: "current",
        });
    }

    requestAccess() {
        this.notification.add(
            "Ask an administrator to grant the AI Copilot role, or the access group for that FMS module.",
            { type: "warning" }
        );
    }

    async saveDocument() {
        try {
            await this.orm.call("ai.copilot.service", "save_document", [this.state.docForm]);
            this.state.docForm = { name: "", category: "sop", summary: "", body: "" };
            await this.refreshDocuments();
            this.notification.add("Knowledge document saved.", { type: "success" });
        } catch (error) {
            this.notification.add(this.errorMessage(error), { type: "danger" });
        }
    }

    async saveSettings() {
        this.state.settingsMessage = "";
        try {
            const values = { ...this.state.settings };
            if (!values.api_key) {
                delete values.api_key;
            }
            const saved = await this.orm.call("ai.copilot.service", "save_settings", [values]);
            Object.assign(this.state.settings, saved, { api_key: "" });
            this.state.bootstrap.provider = {
                ...(this.state.bootstrap.provider || {}),
                configured: saved.provider !== "none" && saved.enabled && saved.api_key_set,
                provider: saved.provider,
            };
            this.state.settingsMessage = "Settings saved. The API key stays on the server.";
        } catch (error) {
            this.state.settingsMessage = this.errorMessage(error);
        }
    }

    onSearchKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.searchFacilities();
        }
    }

    async searchFacilities() {
        const query = (this.state.facilitySearch || "").trim();
        if (!query) {
            return;
        }
        this.state.draft = query;
        this.state.panel = "chat";
        await this.send();
    }
}

registry.category("actions").add("ai_copilot.action_copilot", AiCopilot);
