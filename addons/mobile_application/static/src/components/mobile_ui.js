/** @odoo-module **/

import { Component } from "@odoo/owl";

export class MobileHeader extends Component {
    static template = "mobile_application.MobileHeader";
    static props = {
        title: String,
        subtitle: { type: String, optional: true },
        avatarUrl: { type: String, optional: true },
        unread: { type: Number, optional: true },
        showBack: { type: Boolean, optional: true },
        onBack: { type: Function, optional: true },
        onAlerts: { type: Function, optional: true },
    };
}

export class MobileBottomNav extends Component {
    static template = "mobile_application.MobileBottomNav";
    static components = {};
    static props = {
        active: String,
        role: String,
        modules: { type: Object, optional: true },
        onNavigate: Function,
    };

    get tabs() {
        const opsLabel = this.props.role === "security" ? "Operations" : "Bookings";
        const tabs = [
            { id: "home", label: "Home", icon: "fa-home" },
            { id: "services", label: "Services", icon: "fa-th-large" },
            { id: "bookings", label: opsLabel, icon: "fa-calendar" },
            { id: "alerts", label: "Alerts", icon: "fa-bell-o" },
            { id: "profile", label: "Profile", icon: "fa-user-o" },
        ];
        return tabs;
    }
}

export class MobileAppShell extends Component {
    static template = "mobile_application.MobileAppShell";
    static components = { MobileHeader, MobileBottomNav };
    static props = {
        title: String,
        subtitle: { type: String, optional: true },
        avatarUrl: { type: String, optional: true },
        unread: { type: Number, optional: true },
        activeTab: String,
        role: String,
        modules: { type: Object, optional: true },
        showBack: { type: Boolean, optional: true },
        hideNav: { type: Boolean, optional: true },
        onBack: { type: Function, optional: true },
        onAlerts: { type: Function, optional: true },
        onNavigate: Function,
        slots: { type: Object, optional: true },
    };
}

export class MobileCard extends Component {
    static template = "mobile_application.MobileCard";
    static props = {
        className: { type: String, optional: true },
        onClick: { type: Function, optional: true },
        slots: { type: Object, optional: true },
    };
}

export class MobileSectionHeader extends Component {
    static template = "mobile_application.MobileSectionHeader";
    static props = {
        title: String,
        actionLabel: { type: String, optional: true },
        onAction: { type: Function, optional: true },
    };
}

export class MobileEmptyState extends Component {
    static template = "mobile_application.MobileEmptyState";
    static props = {
        title: String,
        hint: { type: String, optional: true },
        icon: { type: String, optional: true },
    };
}

export class MobileStatusBadge extends Component {
    static template = "mobile_application.MobileStatusBadge";
    static props = {
        label: String,
        tone: { type: String, optional: true },
    };
}

export class MobileQuickAction extends Component {
    static template = "mobile_application.MobileQuickAction";
    static props = {
        label: String,
        icon: String,
        onClick: Function,
    };
}

export class MobileListCard extends Component {
    static template = "mobile_application.MobileListCard";
    static components = { MobileStatusBadge };
    static props = {
        title: String,
        subtitle: { type: String, optional: true },
        state: { type: String, optional: true },
        stateLabel: { type: String, optional: true },
        stateTone: { type: String, optional: true },
        onClick: { type: Function, optional: true },
    };
}

export class MobileLoadingState extends Component {
    static template = "mobile_application.MobileLoadingState";
}

export class MobileErrorState extends Component {
    static template = "mobile_application.MobileErrorState";
    static props = {
        title: String,
        message: String,
    };
}

export class MobileModal extends Component {
    static template = "mobile_application.MobileModal";
    static props = {
        onClose: Function,
        slots: { type: Object, optional: true },
    };
}

export const MOBILE_UI = {
    MobileAppShell,
    MobileHeader,
    MobileBottomNav,
    MobileCard,
    MobileSectionHeader,
    MobileEmptyState,
    MobileStatusBadge,
    MobileQuickAction,
    MobileListCard,
    MobileLoadingState,
    MobileErrorState,
    MobileModal,
};
