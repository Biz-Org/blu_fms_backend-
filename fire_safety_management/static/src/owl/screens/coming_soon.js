import { Component } from "@odoo/owl";
import { FsAppShell } from "@fire_safety_management/owl/ui/fs_shell";

export class FsComingSoon extends Component {
    static template = "fire_safety_management.ComingSoon";
    static components = { FsAppShell };
    static props = ["*"];

    get navId() {
        return "dashboard";
    }

    get copy() {
        return { title: "Fire & Safety", hint: "This screen is scheduled for a later Phase 2 slice." };
    }
}
