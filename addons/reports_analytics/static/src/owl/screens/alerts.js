import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { RaScreen } from "@reports_analytics/owl/screens/ra_screen";

export class AlertsScreen extends RaScreen {
    static template = "reports_analytics.Alerts";

    setup() {
        super.setup();
        this.ui = useState({
            rows: [],
            kpis: [],
            showModal: false,
            severity: "",
            form: {
                name: "",
                alert_type: "threshold",
                severity: "info",
                module: "",
                kpi_id: false,
                condition: "gt",
                threshold: 0,
                recipient_ids: [],
                notify_in_app: true,
                notify_email: true,
                notify_sms: false,
                frequency: "once",
            },
        });
    }

    async load() {
        const records = await this.orm.searchRead("analytics.alert", this.domain(), ["name"]);
        this.ui.rows = [];
        for (const rec of records) {
            this.ui.rows.push(await this.orm.call("analytics.alert", "ui_row", [rec.id]));
        }
        this.ui.kpis = await this.orm.searchRead("analytics.kpi", [["active", "=", true]], ["name", "category"]);
    }

    domain() {
        const domain = [["active", "=", true]];
        if (this.ui.severity) {
            domain.push(["severity", "=", this.ui.severity]);
        }
        return domain;
    }

    openModal() {
        this.ui.showModal = true;
    }

    closeModal() {
        this.ui.showModal = false;
    }

    toggleRecipient(id) {
        const selected = new Set(this.ui.form.recipient_ids);
        if (selected.has(id)) {
            selected.delete(id);
        } else {
            selected.add(id);
        }
        this.ui.form.recipient_ids = [...selected];
    }

    async save() {
        await this.orm.call("analytics.alert", "action_create_from_ui", [{
            ...this.ui.form,
            kpi_id: this.ui.form.kpi_id ? parseInt(this.ui.form.kpi_id, 10) : false,
        }]);
        this.ui.showModal = false;
        await this.reload();
    }

    async acknowledge(row) {
        await this.orm.call("analytics.alert", "action_acknowledge", [row.id]);
        await this.reload();
    }
}

registry.category("actions").add("reports_analytics.action_alerts", AlertsScreen);
