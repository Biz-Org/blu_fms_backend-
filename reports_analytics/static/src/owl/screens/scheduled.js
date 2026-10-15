import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { RaScreen } from "@reports_analytics/owl/screens/ra_screen";

export class ScheduledScreen extends RaScreen {
    static template = "reports_analytics.Scheduled";

    setup() {
        super.setup();
        this.ui = useState({
            rows: [],
            reports: [],
            showModal: false,
            form: {
                report_id: false,
                recipient_ids: [],
                frequency: "weekly",
                weekday: "0",
                output_format: "pdf",
                hour: 8,
                active: true,
            },
        });
    }

    async load() {
        this.ui.rows = await this.orm.searchRead(
            "analytics.report.schedule",
            [],
            ["report_id", "frequency", "output_format", "next_run", "active", "recipient_ids"]
        );
        this.ui.reports = await this.orm.searchRead("analytics.report", [["active", "=", true]], ["name"]);
    }

    openModal() {
        this.ui.showModal = true;
    }

    closeModal() {
        this.ui.showModal = false;
    }

    async save() {
        const vals = {
            ...this.ui.form,
            report_id: parseInt(this.ui.form.report_id, 10),
            recipient_ids: this.ui.form.recipient_ids.map((id) => parseInt(id, 10)),
        };
        await this.orm.call("analytics.report.schedule", "action_create_from_ui", [vals]);
        this.ui.showModal = false;
        await this.reload();
    }

    toggleRecipient(id) {
        const selected = new Set(this.ui.form.recipient_ids);
        const key = String(id);
        if (selected.has(key)) {
            selected.delete(key);
        } else {
            selected.add(key);
        }
        this.ui.form.recipient_ids = [...selected];
    }
}

registry.category("actions").add("reports_analytics.action_scheduled", ScheduledScreen);
