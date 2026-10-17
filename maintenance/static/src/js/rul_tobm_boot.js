/** @odoo-module **/

import { ensureRulTobmInlineStyles } from "../views/rul_tobm_dashboard/rul_tobm_inline_styles";

/** Register iframe client action + HTML field widget (side-effect imports). */
import "../views/rul_tobm_dashboard/rul_tobm_embed_action";
import "../views/rul_tobm_dashboard/rul_tobm_dashboard_html_field";

/** Inject mockup CSS as soon as backend assets load. */
ensureRulTobmInlineStyles();

function applyRulStylesIfPresent() {
    if (document.querySelector(".o_maint_rul_root")) {
        ensureRulTobmInlineStyles();
        document.documentElement.classList.add("o_maint_rul_lock_scroll");
        document.body.classList.add("o_maint_rul_fullscreen_body");
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyRulStylesIfPresent);
} else {
    applyRulStylesIfPresent();
}
