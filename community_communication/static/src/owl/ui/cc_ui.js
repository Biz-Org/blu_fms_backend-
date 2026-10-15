import { Component, useRef, useState } from "@odoo/owl";
import { fileIcon, formatFileSize, m2mIds, statusTone } from "@community_communication/owl/utils";
import { CcAppShell } from "@community_communication/owl/ui/cc_shell";

export class CcPageHeader extends Component {
    static template = "community_communication.CcPageHeader";
    static props = {
        title: String,
        subtitle: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
}

export class CcKpiCard extends Component {
    static template = "community_communication.CcKpiCard";
    static props = {
        label: String,
        value: { type: [Number, String] },
        icon: { type: String, optional: true },
        tone: { type: String, optional: true },
        onClick: { type: Function, optional: true },
    };
    onClick() {
        this.props.onClick?.();
    }
}

export class CcStatusBadge extends Component {
    static template = "community_communication.CcStatusBadge";
    static props = {
        state: { type: String, optional: true },
        label: { type: String, optional: true },
    };
    get tone() {
        return statusTone(this.props.state);
    }
    get text() {
        return this.props.label || (this.props.state || "").replace(/_/g, " ");
    }
}

export class CcSearchBar extends Component {
    static template = "community_communication.CcSearchBar";
    static props = {
        value: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        onChange: Function,
    };
    onInput(ev) {
        this.props.onChange(ev.target.value);
    }
}

export class CcTabs extends Component {
    static template = "community_communication.CcTabs";
    static props = {
        items: Array,
        active: { optional: true },
        onSelect: Function,
    };
}

export class CcEmptyState extends Component {
    static template = "community_communication.CcEmptyState";
    static props = {
        title: String,
        hint: { type: String, optional: true },
        actionLabel: { type: String, optional: true },
        onAction: { type: Function, optional: true },
    };
}

export class CcPagination extends Component {
    static template = "community_communication.CcPagination";
    static props = {
        page: Number,
        total: Number,
        pageSize: Number,
        onPage: Function,
    };
    get pages() {
        const count = Math.max(1, Math.ceil((this.props.total || 0) / (this.props.pageSize || 8)));
        return Array.from({ length: Math.min(count, 7) }, (_, i) => i + 1);
    }
    get from() {
        if (!this.props.total) {
            return 0;
        }
        return (this.props.page - 1) * this.props.pageSize + 1;
    }
    get to() {
        return Math.min(this.props.page * this.props.pageSize, this.props.total || 0);
    }
}

export class CcPreviewPanel extends Component {
    static template = "community_communication.CcPreviewPanel";
    static props = {
        kicker: { type: String, optional: true },
        title: { type: String, optional: true },
        body: { type: String, optional: true },
        meta: { type: String, optional: true },
        category: { type: String, optional: true },
        extra: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
}

export class CcFormSection extends Component {
    static template = "community_communication.CcFormSection";
    static props = {
        title: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
}

export class CcActionButton extends Component {
    static template = "community_communication.CcActionButton";
    static props = {
        label: String,
        variant: { type: String, optional: true },
        icon: { type: String, optional: true },
        disabled: { type: Boolean, optional: true },
        onClick: Function,
    };
}

export class CcConfirmDialog extends Component {
    static template = "community_communication.CcConfirmDialog";
    static props = {
        title: String,
        message: { type: String, optional: true },
        confirmLabel: { type: String, optional: true },
        onConfirm: Function,
        onCancel: Function,
    };
}

export class CcChart extends Component {
    static template = "community_communication.CcChart";
    static props = {
        points: { type: String, optional: true },
        color: { type: String, optional: true },
        height: { type: [Number, String], optional: true },
    };
}

export class CcFieldError extends Component {
    static template = "community_communication.CcFieldError";
    static props = {
        message: { type: String, optional: true },
    };
}

export class CcFileDropzone extends Component {
    static template = "community_communication.CcFileDropzone";
    static components = { CcFieldError };
    static props = {
        files: { type: Array, optional: true },
        error: { type: String, optional: true },
        uploading: { type: Boolean, optional: true },
        onAdd: Function,
        onRemove: Function,
        hint: { type: String, optional: true },
        multiple: { type: Boolean, optional: true },
        single: { type: Boolean, optional: true },
        accept: { type: String, optional: true },
    };
    setup() {
        this.inputRef = useRef("fileInput");
        this.state = useState({ over: false });
        this.formatFileSize = formatFileSize;
        this.fileIcon = fileIcon;
    }
    openPicker() {
        this.inputRef.el?.click();
    }
    onInput(ev) {
        const files = ev.target.files;
        if (files && files.length) {
            this.props.onAdd(files);
        }
        ev.target.value = "";
    }
    onDrop(ev) {
        ev.preventDefault();
        this.state.over = false;
        this.props.onAdd(ev.dataTransfer.files);
    }
    onDragOver(ev) {
        ev.preventDefault();
        this.state.over = true;
    }
    onDragLeave() {
        this.state.over = false;
    }
}

export class CcAudiencePicker extends Component {
    static template = "community_communication.CcAudiencePicker";
    static components = { CcFieldError };
    static props = {
        audienceType: String,
        onType: Function,
        buildings: Array,
        groups: Array,
        buildingIds: { type: Array, optional: true },
        groupIds: { type: Array, optional: true },
        buildingQuery: { type: String, optional: true },
        groupQuery: { type: String, optional: true },
        onBuildingQuery: Function,
        onGroupQuery: Function,
        onToggleBuilding: Function,
        onToggleGroup: Function,
        error: { type: String, optional: true },
        radioName: { type: String, optional: true },
    };
    get selectedBuildingIds() {
        return m2mIds(this.props.buildingIds);
    }
    get selectedGroupIds() {
        return m2mIds(this.props.groupIds);
    }
    get selectedBuildings() {
        const ids = new Set(this.selectedBuildingIds);
        return this.props.buildings.filter((row) => ids.has(row.id));
    }
    get selectedGroups() {
        const ids = new Set(this.selectedGroupIds);
        return this.props.groups.filter((row) => ids.has(row.id));
    }
    get visibleBuildings() {
        const query = (this.props.buildingQuery || "").toLowerCase();
        return this.props.buildings.filter(
            (row) => !query || (row.name || "").toLowerCase().includes(query)
        );
    }
    get visibleGroups() {
        const query = (this.props.groupQuery || "").toLowerCase();
        return this.props.groups.filter(
            (row) => !query || (row.name || "").toLowerCase().includes(query)
        );
    }
}

export const CC_COMPONENTS = {
    CcAppShell,
    CcPageHeader,
    CcKpiCard,
    CcStatusBadge,
    CcSearchBar,
    CcTabs,
    CcEmptyState,
    CcPagination,
    CcPreviewPanel,
    CcFormSection,
    CcActionButton,
    CcConfirmDialog,
    CcChart,
    CcFieldError,
    CcFileDropzone,
    CcAudiencePicker,
};
