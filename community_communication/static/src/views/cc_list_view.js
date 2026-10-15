import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { CcKpiHeader } from "@community_communication/components/kpi_header/kpi_header";

export class CcListRenderer extends ListRenderer {
    static template = "community_communication.ListRenderer";
    static components = { ...ListRenderer.components, CcKpiHeader };
}

export const ccListView = {
    ...listView,
    Renderer: CcListRenderer,
};

registry.category("views").add("cc_kpi_list", ccListView);
