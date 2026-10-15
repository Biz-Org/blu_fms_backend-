import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { CcLivePreview } from "@community_communication/components/live_preview/live_preview";

export class CcPreviewFormController extends FormController {
    static template = "community_communication.PreviewFormView";
    static components = { ...FormController.components, CcLivePreview };
}

export const ccPreviewFormView = {
    ...formView,
    Controller: CcPreviewFormController,
};

registry.category("views").add("cc_preview_form", ccPreviewFormView);
