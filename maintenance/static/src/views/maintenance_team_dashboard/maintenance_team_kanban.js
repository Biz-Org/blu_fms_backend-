/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";

export class MaintenanceTeamKanbanController extends KanbanController {
    static template = "maintenance.TeamKanbanView";

    get createTeamLabel() {
        return _t("+ Create New Team");
    }
}

export const maintenanceTeamKanbanView = {
    ...kanbanView,
    Controller: MaintenanceTeamKanbanController,
};

registry.category("views").add("maintenance_team_dashboard_kanban", maintenanceTeamKanbanView);
