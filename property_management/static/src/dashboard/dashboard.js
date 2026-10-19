/** @odoo-module **/

import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

const PAGE_SIZE = 10;

function emptyOccupancyFilters() {
    return {
        property: "all",
        building: "all",
        floor: "all",
        status: "all",
    };
}

function emptyDocumentUpload() {
    return {
        name: "",
        property_id: "",
        category: "legal",
        expiry_date: "",
        filename: "",
        data: "",
        size: 0,
    };
}

function emptyOwnershipEdit() {
    return {
        record_id: false,
        unit_id: false,
        unit_name: "",
        owner_name: "",
        owner_type: "primary",
        share: 100,
        effective_date: "",
        status: "active",
        cost: 0,
        deed: "",
    };
}

function emptyOwnershipTransfer() {
    return {
        unit_id: "",
        owner_name: "",
        owner_type: "primary",
        share: 100,
        effective_date: "",
        status: "pending",
    };
}

function emptyPropertyForm() {
    return {
        name: "",
        code: "",
        property_type: "",
        operational_status: "active",
        description: "",
        street: "",
        city: "",
        state_name: "",
        zip: "",
        country: "",
        planned_buildings: 1,
        planned_floors: 0,
        planned_units: 0,
        category: "class_a",
        id: null,
        documents: {
            property_reg: null,
            ownership: null,
            building: null,
            other: null,
        },
    };
}

const NAV = [
    { id: "overview", label: "Overview", icon: "fa-th-large" },
    { id: "properties", label: "Properties", icon: "fa-building" },
    { id: "buildings", label: "Buildings / Towers", icon: "fa-university" },
    { id: "floors", label: "Floors & Wings", icon: "fa-align-justify" },
    { id: "units", label: "Units", icon: "fa-th" },
    { id: "occupancy", label: "Occupancy", icon: "fa-pie-chart" },
    { id: "ownership", label: "Ownership", icon: "fa-id-badge" },
    { id: "tenancy", label: "Tenant History", icon: "fa-clock-o" },
    { id: "documents", label: "Documents", icon: "fa-folder-open-o" },
    { id: "status", label: "Unit Status", icon: "fa-flag" },
];

const UNIT_TABS = [
    { id: "overview", label: "Overview" },
    { id: "ownership", label: "Ownership" },
    { id: "tenants", label: "Tenants" },
    { id: "documents", label: "Documents" },
    { id: "history", label: "Status History" },
];

const BUILDING_TABS = [
    { id: "overview", label: "Overview" },
    { id: "floors", label: "Floors & Wings" },
    { id: "units", label: "Units" },
    { id: "occupancy", label: "Occupancy" },
    { id: "documents", label: "Documents" },
    { id: "history", label: "History" },
];

const DETAIL_TABS = [
    { id: "overview", label: "Overview" },
    { id: "buildings", label: "Buildings" },
    { id: "units", label: "Units" },
    { id: "occupancy", label: "Occupancy" },
    { id: "ownership", label: "Ownership" },
    { id: "documents", label: "Documents" },
    { id: "history", label: "History" },
];

function emptyUnitDetail() {
    return {
        unit: {
            id: null,
            name: "",
            property_id: null,
            property_name: "",
            building_id: null,
            building_name: "",
            floor_id: null,
            floor_label: "",
            wing: "",
            wing_label: "",
            location: "",
            address: "",
            map_url: "",
            map_open_url: "",
            op_status: "active",
            op_status_label: "Active",
            occupancy: "vacant",
            occupancy_label: "Vacant",
            status: "available",
        },
        kpis: {
            area: "—",
            config: "—",
            owner: "—",
            tenant: "—",
            occupancy: "vacant",
            occupancy_label: "Vacant",
        },
        info: {
            number: "",
            unit_type: "",
            config: "—",
            carpet: "—",
            built: "—",
            floor: "—",
            wing: "—",
            parking: "—",
        },
        owners: [],
        tenants: [],
        documents: [],
        history: [],
    };
}

function emptyStatusChange() {
    return {
        unit_id: null,
        unit_ids: [],
        unit_name: "",
        property_name: "",
        current_status: "",
        current_label: "",
        new_status: "vacant",
        effective_date: "",
        reason: "lease_abandonment",
        notes: "",
        has_lease: false,
        bulk: false,
    };
}

function emptyUnitAction() {
    return {
        mode: "",
        status: "occupied",
        name: "",
        date_start: "",
        share: 100,
    };
}

function emptyBuildingDetail() {
    return {
        building: {
            id: null,
            name: "",
            full_name: "",
            code: "",
            status: "active",
            status_label: "Active",
            property_id: null,
            property_name: "",
            location: "",
        },
        kpis: {
            floors: 0,
            wings: 0,
            units: 0,
            occupied: 0,
            vacant: 0,
            occupancy_pct: 0,
            vacant_pct: 0,
        },
        bands: [],
        activities: [],
        floors: [],
        units: [],
        unit_total: 0,
        documents: [],
    };
}

function emptyUnitForm() {
    return {
        id: null,
        name: "",
        property_id: "",
        building_id: "",
        floor_id: "",
        unit_type: "2 BHK",
        status: "available",
        area_sqft: 0,
    };
}

function emptyFloorForm() {
    return {
        mode: "floor",
        floor_id: null,
        building_id: "",
        name: "",
        floor_number: "",
        wing: "A",
    };
}

function emptyBuildingForm() {
    return {
        id: null,
        name: "",
        code: "",
        property_id: "",
        usage: "commercial",
        floors: 1,
    };
}

function emptyPropertyDetail() {
    return {
        property: {
            id: null,
            name: "",
            code: "",
            location: "",
            status: "active",
            status_label: "Active",
            type_label: "",
            year_built: "—",
            gla: "—",
            manager_name: "—",
            manager_initials: "PM",
            acquisition: "—",
        },
        kpis: {
            buildings: 0,
            floors: 0,
            units: 0,
            occupied: 0,
            vacant: 0,
            occupancy_pct: 0,
            vacant_pct: 0,
        },
        activities: [],
        hierarchy: { root: "", buildings: [] },
        buildings: [],
        units: [],
        unit_total: 0,
        owners: [],
        documents: [],
    };
}

const REPORTS = [
    { id: "property_reports", label: "Property Reports", icon: "fa-bar-chart", xmlId: "property_management.action_property_reports" },
    { id: "occupancy_reports", label: "Occupancy Reports", icon: "fa-line-chart", xmlId: "property_management.action_occupancy_reports" },
    { id: "ownership_reports", label: "Ownership Reports", icon: "fa-file-text-o", xmlId: "property_management.action_ownership_reports" },
];

export class PropertyDashboard extends Component {
    static template = "property_management.Dashboard";
    static target = "fullscreen";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.user = useService("user");
        this.navItems = NAV;
        this.reportItems = REPORTS;
        this.detailTabs = DETAIL_TABS;
        this.buildingTabs = BUILDING_TABS;
        this.unitTabs = UNIT_TABS;
        this.pageSize = PAGE_SIZE;
        this.streetRef = useRef("street");
        this.state = useState({
            loading: true,
            page: "overview",
            search: "",
            typeFilter: "all",
            statusFilter: "all",
            locationFilter: "all",
            listPage: 1,
            showMoreFilters: false,
            menuId: null,
            saving: false,
            form: emptyPropertyForm(),
            hierarchy: [],
            hierarchySearch: "",
            hierarchyStatusFilter: "all",
            showHierarchyFilter: false,
            loadingHierarchy: false,
            expanded: {},
            detail: emptyPropertyDetail(),
            detailTab: "overview",
            detailMenu: false,
            loadingDetail: false,
            selectedBuildingId: null,
            selectedBandId: null,
            hierarchyZoom: 1,
            buildingsList: [],
            buildingProperties: [],
            buildingSearch: "",
            buildingPropertyFilter: "all",
            buildingStatusFilter: "all",
            buildingPage: 1,
            selectedBuildingIds: {},
            showBuildingForm: false,
            buildingForm: emptyBuildingForm(),
            loadingBuildings: false,
            buildingDetail: emptyBuildingDetail(),
            buildingTab: "overview",
            loadingBuildingDetail: false,
            buildingExpanded: {},
            buildingActivityFilter: "all",
            floorsWorkspace: { buildings: [], selected_id: null, building: { id: null, name: "" }, floors: [] },
            floorBuildingSearch: "",
            selectedFloorBuildingId: null,
            floorExpanded: {},
            loadingFloors: false,
            showFloorForm: false,
            floorForm: emptyFloorForm(),
            unitsList: [],
            unitProperties: [],
            unitBuildings: [],
            unitFloors: [],
            unitTypes: [],
            unitSearch: "",
            unitPropertyFilter: "all",
            unitBuildingFilter: "all",
            unitFloorFilter: "all",
            unitWingFilter: "all",
            unitTypeFilter: "all",
            unitOccupancyFilter: "all",
            unitOpStatusFilter: "all",
            unitPage: 1,
            selectedUnitIds: {},
            loadingUnits: false,
            showUnitForm: false,
            unitForm: emptyUnitForm(),
            unitDetail: emptyUnitDetail(),
            unitTab: "overview",
            loadingUnitDetail: false,
            showUnitAction: false,
            unitAction: emptyUnitAction(),
            occupancyUnits: [],
            reportProperties: [],
            reportStatus: {},
            reportOccupancyUnits: [],
            reportOwnership: [],
            reportOwnershipKpis: {},
            loadingReport: false,
            occupancyProperties: [],
            occupancyBuildings: [],
            occupancyFloors: [],
            occupancyMonths: [],
            occupancyTarget: 95,
            occDraft: emptyOccupancyFilters(),
            occApplied: emptyOccupancyFilters(),
            occSearch: "",
            occPage: 1,
            loadingOccupancy: false,
            ownershipRecords: [],
            ownershipUnits: [],
            ownershipProperties: [],
            ownershipKpis: {
                owners: 0,
                owners_delta: "+2.4%",
                units_owned: 0,
                properties: 0,
                joint: 0,
                recent: 0,
            },
            ownSearch: "",
            ownTab: "all",
            ownPropertyFilter: "all",
            ownStatusFilter: "all",
            ownPage: 1,
            selectedOwnershipId: null,
            showOwnershipFilters: false,
            showOwnershipTransfer: false,
            ownershipTransfer: emptyOwnershipTransfer(),
            showOwnershipEdit: false,
            ownershipEdit: emptyOwnershipEdit(),
            loadingOwnership: false,
            tenancyRecords: [],
            tenancyProperties: [],
            tenancyKpis: {
                total: 0,
                total_delta: "+2.4% vs last quarter",
                active: 0,
                active_delta: "+1.1% vs last quarter",
                avg_duration: 0,
                avg_hint: "Stable vs last quarter",
                moveouts: 0,
                moveouts_delta: "+5.2% vs last quarter (30 days)",
            },
            tenSearch: "",
            tenStatusFilter: "all",
            tenDateRange: "all",
            tenPropertyFilter: "all",
            tenPage: 1,
            selectedTenancyId: null,
            showTenancyNote: false,
            tenancyNote: "",
            showHelp: false,
            showTenancyFilters: false,
            loadingTenancy: false,
            documentRecords: [],
            documentProperties: [],
            docSearch: "",
            docCategory: "all",
            docPropertyFilter: "all",
            docStatusFilter: "all",
            docDateRange: "all",
            docPage: 1,
            selectedDocumentId: null,
            loadingDocuments: false,
            showDocumentUpload: false,
            documentUpload: emptyDocumentUpload(),
            showDocumentVersions: false,
            documentVersions: [],
            documentVersionName: "",
            showDocumentDelete: false,
            documentPendingDelete: null,
            showDocumentViewer: false,
            documentViewer: { name: "", url: "", kind: "" },
            statusRecords: [],
            statusProperties: [],
            statusKpis: { available: 0, occupied: 0, unoccupied: 0 },
            stSearch: "",
            stPropertyFilter: "all",
            stStatusFilter: "all",
            stDateRange: "all",
            stPage: 1,
            selectedStatusIds: {},
            showStatusFilters: false,
            loadingStatusBoard: false,
            showStatusChange: false,
            statusChange: emptyStatusChange(),
            data: {
                kpis: {
                    properties: 0,
                    properties_delta: "",
                    buildings: 0,
                    buildings_hint: "",
                    units: 0,
                    units_delta: "",
                    occupancy: 0,
                    occupancy_delta: "",
                },
                status: {
                    occupied: 0,
                    vacant: 0,
                    maintenance: 0,
                    reserved: 0,
                    available: 0,
                },
                trends: [],
                summary: [],
                activities: [],
                properties: [],
            },
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.data = await this.orm.call("property.property", "get_dashboard_data", []);
        this.state.loading = false;
    }

    formatNumber(value) {
        return Number(value || 0).toLocaleString("en-US");
    }

    get locations() {
        return [...new Set((this.state.data.properties || []).map((row) => row.location).filter(Boolean))].sort();
    }

    get filteredProperties() {
        const search = (this.state.search || "").trim().toLowerCase();
        return (this.state.data.properties || []).filter((row) => {
            if (search && !`${row.name} ${row.code}`.toLowerCase().includes(search)) {
                return false;
            }
            if (this.state.typeFilter !== "all" && row.type !== this.state.typeFilter) {
                return false;
            }
            if (this.state.statusFilter !== "all" && row.status !== this.state.statusFilter) {
                return false;
            }
            if (this.state.locationFilter !== "all" && row.location !== this.state.locationFilter) {
                return false;
            }
            return true;
        });
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.filteredProperties.length / PAGE_SIZE));
    }

    get pagedProperties() {
        const start = (this.state.listPage - 1) * PAGE_SIZE;
        return this.filteredProperties.slice(start, start + PAGE_SIZE);
    }

    get pageNumbers() {
        const count = this.pageCount;
        if (count <= 5) {
            return Array.from({ length: count }, (_, index) => index + 1);
        }
        const pages = [1];
        if (this.state.listPage > 3) {
            pages.push("...");
        }
        const start = Math.max(2, this.state.listPage - 1);
        const end = Math.min(count - 1, this.state.listPage + 1);
        for (let page = start; page <= end; page++) {
            pages.push(page);
        }
        if (this.state.listPage < count - 2) {
            pages.push("...");
        }
        pages.push(count);
        return pages;
    }

    get rangeLabel() {
        const total = this.filteredProperties.length;
        if (!total) {
            return "Showing 0 entries";
        }
        const start = (this.state.listPage - 1) * PAGE_SIZE + 1;
        const end = Math.min(total, this.state.listPage * PAGE_SIZE);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    get filteredBuildings() {
        const search = (this.state.buildingSearch || "").trim().toLowerCase();
        const propertyId = this.state.buildingPropertyFilter;
        const status = this.state.buildingStatusFilter;
        return (this.state.buildingsList || []).filter((row) => {
            if (search && !`${row.name} ${row.code}`.toLowerCase().includes(search)) {
                return false;
            }
            if (propertyId !== "all" && String(row.property_id) !== String(propertyId)) {
                return false;
            }
            if (status !== "all" && row.status !== status) {
                return false;
            }
            return true;
        });
    }

    get buildingPageCount() {
        return Math.max(1, Math.ceil(this.filteredBuildings.length / PAGE_SIZE));
    }

    get pagedBuildings() {
        const start = (this.state.buildingPage - 1) * PAGE_SIZE;
        return this.filteredBuildings.slice(start, start + PAGE_SIZE);
    }

    get buildingPageNumbers() {
        const count = this.buildingPageCount;
        const current = this.state.buildingPage;
        if (count <= 5) {
            return Array.from({ length: count }, (_, index) => index + 1);
        }
        const pages = [1];
        if (current > 3) {
            pages.push("...");
        }
        const start = Math.max(2, current - 1);
        const end = Math.min(count - 1, current + 1);
        for (let page = start; page <= end; page++) {
            pages.push(page);
        }
        if (current < count - 2) {
            pages.push("...");
        }
        pages.push(count);
        return pages;
    }

    get buildingRangeLabel() {
        const total = this.filteredBuildings.length;
        if (!total) {
            return "Showing 0 entries";
        }
        const start = (this.state.buildingPage - 1) * PAGE_SIZE + 1;
        const end = Math.min(total, this.state.buildingPage * PAGE_SIZE);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    get topSearchPlaceholder() {
        if (this.state.page === "occupancy") {
            return "Search units, tenants, or properties...";
        }
        if (this.state.page === "ownership") {
            return "Search ownership records, units...";
        }
        if (this.state.page === "tenancy") {
            return "Search tenants, units, or properties...";
        }
        if (this.state.page === "documents") {
            return "Search documents, files, or properties...";
        }
        if (this.state.page === "status") {
            return "Search units, properties, or status...";
        }
        if (this.state.page === "buildings" || this.state.page === "building-detail" || this.state.page === "floors" || this.state.page === "units" || this.state.page === "unit-detail") {
            return "Search buildings, units, tenants...";
        }
        return "Search...";
    }

    get topSearchValue() {
        return this.state.page === "buildings"
            ? this.state.buildingSearch
            : this.state.page === "floors"
                ? this.state.floorBuildingSearch
                : this.state.page === "occupancy"
                    ? this.state.occSearch
                    : this.state.page === "ownership"
                        ? this.state.ownSearch
                        : this.state.page === "tenancy"
                            ? this.state.tenSearch
                            : this.state.page === "documents"
                                ? this.state.docSearch
                                : this.state.page === "status"
                                    ? this.state.stSearch
                                    : this.state.page === "units" || this.state.page === "unit-detail"
                                        ? this.state.unitSearch
                                        : this.state.search;
    }

    get allPagedBuildingsSelected() {
        const rows = this.pagedBuildings;
        return Boolean(rows.length && rows.every((row) => this.state.selectedBuildingIds[row.id]));
    }

    get unitFilterBuildings() {
        const propertyId = this.state.unitPropertyFilter;
        const rows = this.state.unitBuildings || [];
        if (propertyId === "all") {
            return rows;
        }
        return rows.filter((row) => String(row.property_id) === String(propertyId));
    }

    get unitFilterFloors() {
        const buildingId = this.state.unitBuildingFilter;
        const rows = this.state.unitFloors || [];
        if (buildingId === "all") {
            return rows;
        }
        return rows.filter((row) => String(row.building_id) === String(buildingId));
    }

    get unitFilterWings() {
        const floors = this.unitFilterFloors;
        return [...new Set(floors.map((row) => row.wing).filter(Boolean))].sort();
    }

    get filteredUnits() {
        const search = (this.state.unitSearch || "").trim().toLowerCase();
        return (this.state.unitsList || []).filter((row) => {
            if (search && !`${row.name} ${row.property_name} ${row.building_name}`.toLowerCase().includes(search)) {
                return false;
            }
            if (this.state.unitPropertyFilter !== "all" && String(row.property_id) !== String(this.state.unitPropertyFilter)) {
                return false;
            }
            if (this.state.unitBuildingFilter !== "all" && String(row.building_id) !== String(this.state.unitBuildingFilter)) {
                return false;
            }
            if (this.state.unitFloorFilter !== "all" && String(row.floor_id) !== String(this.state.unitFloorFilter)) {
                return false;
            }
            if (this.state.unitWingFilter !== "all" && String(row.wing) !== String(this.state.unitWingFilter)) {
                return false;
            }
            if (this.state.unitTypeFilter !== "all" && row.config !== this.state.unitTypeFilter) {
                return false;
            }
            if (this.state.unitOccupancyFilter !== "all" && row.occupancy !== this.state.unitOccupancyFilter) {
                return false;
            }
            if (this.state.unitOpStatusFilter !== "all" && row.op_status !== this.state.unitOpStatusFilter) {
                return false;
            }
            return true;
        });
    }

    get unitPageCount() {
        return Math.max(1, Math.ceil(this.filteredUnits.length / PAGE_SIZE));
    }

    get pagedUnits() {
        const start = (this.state.unitPage - 1) * PAGE_SIZE;
        return this.filteredUnits.slice(start, start + PAGE_SIZE);
    }

    get unitPageNumbers() {
        const count = this.unitPageCount;
        const current = this.state.unitPage;
        if (count <= 5) {
            return Array.from({ length: count }, (_, index) => index + 1);
        }
        const pages = [1];
        if (current > 3) {
            pages.push("...");
        }
        const start = Math.max(2, current - 1);
        const end = Math.min(count - 1, current + 1);
        for (let page = start; page <= end; page++) {
            pages.push(page);
        }
        if (current < count - 2) {
            pages.push("...");
        }
        pages.push(count);
        return pages;
    }

    get unitRangeLabel() {
        const total = this.filteredUnits.length;
        if (!total) {
            return "Showing 0 entries";
        }
        const start = (this.state.unitPage - 1) * PAGE_SIZE + 1;
        const end = Math.min(total, this.state.unitPage * PAGE_SIZE);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    get allPagedUnitsSelected() {
        const rows = this.pagedUnits;
        return Boolean(rows.length && rows.every((row) => this.state.selectedUnitIds[row.id]));
    }

    get occupancyFilterBuildings() {
        const propertyId = this.state.occDraft.property;
        let rows = this.state.occupancyBuildings || [];
        if (propertyId !== "all") {
            rows = rows.filter((row) => String(row.property_id) === String(propertyId));
        }
        const unique = new Map();
        for (const row of rows) {
            const name = (row.name || "").trim();
            if (!name || unique.has(name)) {
                continue;
            }
            unique.set(name, { name });
        }
        return [...unique.values()].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    }

    occupancyBuildingIds(property, building) {
        let rows = this.state.occupancyBuildings || [];
        if (property && property !== "all") {
            rows = rows.filter((row) => String(row.property_id) === String(property));
        }
        if (building && building !== "all") {
            rows = rows.filter((row) => String(row.name) === String(building));
        }
        return rows.map((row) => String(row.id));
    }

    get occupancyFilterFloors() {
        const draft = this.state.occDraft;
        let rows = this.state.occupancyFloors || [];
        if (draft.building !== "all" || draft.property !== "all") {
            const buildingIds = new Set(this.occupancyBuildingIds(draft.property, draft.building));
            rows = rows.filter((row) => buildingIds.has(String(row.building_id)));
        }
        const unique = new Map();
        for (const row of rows) {
            const number = Number(row.number || 0);
            if (!number || unique.has(number)) {
                continue;
            }
            unique.set(number, {
                number,
                name: `Floor ${number}`,
            });
        }
        return [...unique.values()].sort((a, b) => a.number - b.number);
    }

    get occupancyScopedUnits() {
        const applied = this.state.occApplied;
        const floorNumberById = {};
        for (const floor of this.state.occupancyFloors || []) {
            floorNumberById[String(floor.id)] = floor.number;
        }
        const buildingIds = applied.building === "all"
            ? null
            : new Set(this.occupancyBuildingIds(applied.property, applied.building));
        return (this.state.occupancyUnits || []).filter((row) => {
            if (applied.property !== "all" && String(row.property_id) !== String(applied.property)) {
                return false;
            }
            if (buildingIds && !buildingIds.has(String(row.building_id))) {
                return false;
            }
            if (applied.floor !== "all") {
                const floorNumber = row.floor_number || floorNumberById[String(row.floor_id)];
                if (String(floorNumber) !== String(applied.floor)) {
                    return false;
                }
            }
            if (applied.status !== "all" && row.directory_status !== applied.status) {
                return false;
            }
            return true;
        });
    }

    occupancyMonthWindow() {
        const now = new Date();
        const months = [];
        for (let offset = 5; offset >= 0; offset--) {
            const date = new Date(now.getFullYear(), now.getMonth() - offset, 1);
            months.push({
                label: date.toLocaleString("en-US", { month: "short" }),
                year: date.getFullYear(),
                month: date.getMonth(),
                current: offset === 0,
            });
        }
        return months;
    }

    unitOccupiedInMonth(unit, year, month, isCurrent) {
        if (isCurrent) {
            return unit.directory_status === "occupied";
        }
        const ranges = unit.tenancies || [];
        if (!ranges.length) {
            return unit.directory_status === "occupied";
        }
        const start = new Date(year, month, 1);
        const end = new Date(year, month + 1, 0, 23, 59, 59);
        return ranges.some((range) => {
            if (!range.start) {
                return false;
            }
            const rangeStart = new Date(`${range.start}T00:00:00`);
            const rangeEnd = range.end ? new Date(`${range.end}T23:59:59`) : new Date(8640000000000000);
            return rangeStart <= end && rangeEnd >= start;
        });
    }

    occupancySeries() {
        const units = this.occupancyScopedUnits;
        const total = units.length;
        return this.occupancyMonthWindow().map((entry) => {
            const occupied = units.filter((unit) => this.unitOccupiedInMonth(unit, entry.year, entry.month, entry.current)).length;
            const pct = total ? Math.round((occupied / total) * 1000) / 10 : 0;
            return { ...entry, pct };
        });
    }

    get occupancyKpis() {
        const units = this.occupancyScopedUnits;
        const total = units.length;
        const occupied = units.filter((row) => row.directory_status === "occupied").length;
        const vacant = units.filter((row) => row.directory_status === "vacant").length;
        const reserved = units.filter((row) => row.directory_status === "reserved").length;
        const maintenance = units.filter((row) => row.directory_status === "maintenance").length;
        const series = this.occupancySeries();
        const pct = total ? Math.round((occupied / total) * 1000) / 10 : 0;
        const previous = series.length > 1 ? series[series.length - 2].pct : pct;
        const delta = Math.round((pct - previous) * 10) / 10;
        const sign = delta > 0 ? "+" : "";
        return {
            total,
            occupied,
            vacant,
            reserved,
            maintenance,
            occupancy_pct: pct,
            occupancy_display: pct.toFixed(1),
            occupancy_delta: `${sign}${delta.toFixed(1)}%`,
            delta_up: delta >= 0,
        };
    }

    get occupancyDirectory() {
        const search = (this.state.occSearch || "").trim().toLowerCase();
        return this.occupancyScopedUnits.filter((row) => {
            if (!search) {
                return true;
            }
            return `${row.name} ${row.property_name} ${row.tenant}`.toLowerCase().includes(search);
        });
    }

    get occPageCount() {
        return Math.max(1, Math.ceil(this.occupancyDirectory.length / PAGE_SIZE));
    }

    get pagedOccupancyUnits() {
        const start = (this.state.occPage - 1) * PAGE_SIZE;
        return this.occupancyDirectory.slice(start, start + PAGE_SIZE);
    }

    get occPageNumbers() {
        const count = this.occPageCount;
        const current = this.state.occPage;
        if (count <= 5) {
            return Array.from({ length: count }, (_, index) => index + 1);
        }
        const pages = [1];
        if (current > 3) {
            pages.push("...");
        }
        const start = Math.max(2, current - 1);
        const end = Math.min(count - 1, current + 1);
        for (let page = start; page <= end; page++) {
            pages.push(page);
        }
        if (current < count - 2) {
            pages.push("...");
        }
        pages.push(count);
        return pages;
    }

    get occRangeLabel() {
        const total = this.occupancyDirectory.length;
        if (!total) {
            return "Showing 0 entries";
        }
        const start = (this.state.occPage - 1) * PAGE_SIZE + 1;
        const end = Math.min(total, this.state.occPage * PAGE_SIZE);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    get occupancyChart() {
        const series = this.occupancySeries();
        const months = series.map((entry) => entry.label);
        const target = Number(this.state.occupancyTarget || 95);
        const actuals = series.map((entry) => entry.pct);
        const width = 640;
        const height = 220;
        const padL = 42;
        const padR = 16;
        const padT = 18;
        const padB = 36;
        const minY = Math.max(0, Math.min(target, ...actuals, 90) - 5);
        const maxY = 100;
        const span = Math.max(1, maxY - minY);
        const innerW = width - padL - padR;
        const innerH = height - padT - padB;
        const toX = (index) => padL + (months.length <= 1 ? innerW / 2 : (index * innerW) / (months.length - 1));
        const toY = (value) => padT + ((maxY - value) / span) * innerH;
        const dots = months.map((month, index) => ({
            month,
            x: toX(index),
            y: toY(actuals[index]),
            actual: actuals[index],
            labelY: height - 10,
        }));
        const tickCount = 4;
        const grid = [];
        for (let index = 0; index < tickCount; index++) {
            const value = maxY - (span * index) / (tickCount - 1);
            grid.push({ y: toY(value), labelY: toY(value) + 4, label: `${Math.round(value)}%` });
        }
        return {
            width,
            height,
            viewBox: `0 0 ${width} ${height}`,
            padL,
            padLabelX: padL - 8,
            innerRight: width - padR,
            targetY: toY(target),
            actualPoints: dots.map((dot) => `${dot.x},${dot.y}`).join(" "),
            dots,
            grid,
        };
    }

    get filteredOwnership() {
        const search = (this.state.ownSearch || "").trim().toLowerCase();
        return (this.state.ownershipRecords || []).filter((row) => {
            if (this.state.ownTab === "pending" && row.status !== "pending") {
                return false;
            }
            if (this.state.ownTab === "multi" && !row.multi) {
                return false;
            }
            if (this.state.ownPropertyFilter !== "all" && String(row.property_id) !== String(this.state.ownPropertyFilter)) {
                return false;
            }
            if (this.state.ownStatusFilter !== "all" && row.status !== this.state.ownStatusFilter) {
                return false;
            }
            if (search && !`${row.unit_name} ${row.owner_name} ${row.building_name} ${row.property_name}`.toLowerCase().includes(search)) {
                return false;
            }
            return true;
        });
    }

    get ownPageCount() {
        return Math.max(1, Math.ceil(this.filteredOwnership.length / PAGE_SIZE));
    }

    get pagedOwnership() {
        const start = (this.state.ownPage - 1) * PAGE_SIZE;
        return this.filteredOwnership.slice(start, start + PAGE_SIZE);
    }

    get ownPageNumbers() {
        const count = this.ownPageCount;
        const current = this.state.ownPage;
        if (count <= 5) {
            return Array.from({ length: count }, (_, index) => index + 1);
        }
        const pages = [1];
        if (current > 3) {
            pages.push("...");
        }
        const start = Math.max(2, current - 1);
        const end = Math.min(count - 1, current + 1);
        for (let page = start; page <= end; page++) {
            pages.push(page);
        }
        if (current < count - 2) {
            pages.push("...");
        }
        pages.push(count);
        return pages;
    }

    get ownRangeLabel() {
        const total = this.filteredOwnership.length;
        if (!total) {
            return "Showing 0 entries";
        }
        const start = (this.state.ownPage - 1) * PAGE_SIZE + 1;
        const end = Math.min(total, this.state.ownPage * PAGE_SIZE);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    get selectedOwnership() {
        const id = this.state.selectedOwnershipId;
        if (!id) {
            return null;
        }
        return (this.state.ownershipRecords || []).find((row) => row.id === id) || null;
    }

    get selectedOwnershipGroup() {
        const selected = this.selectedOwnership;
        if (!selected) {
            return [];
        }
        return (this.state.ownershipRecords || []).filter((row) => row.unit_id === selected.unit_id);
    }

    get ownershipRingStyle() {
        const share = Number(this.selectedOwnership?.share || 0);
        return `background: conic-gradient(var(--pm-accent) 0 ${share}%, #eef0ff ${share}% 100%);`;
    }

    get filteredTenancy() {
        const search = (this.state.tenSearch || "").trim().toLowerCase();
        const days = { "90": 90, "365": 365, "1095": 1095 }[this.state.tenDateRange];
        const cutoff = days ? Date.now() - days * 86400000 : null;
        return (this.state.tenancyRecords || []).filter((row) => {
            if (this.state.tenStatusFilter !== "all" && row.status !== this.state.tenStatusFilter) {
                return false;
            }
            if (this.state.tenPropertyFilter !== "all" && String(row.property_id) !== String(this.state.tenPropertyFilter)) {
                return false;
            }
            if (cutoff && row.move_in && new Date(row.move_in).getTime() < cutoff) {
                return false;
            }
            if (search && !`${row.tenant_name} ${row.unit_name} ${row.property_name} ${row.building_name}`.toLowerCase().includes(search)) {
                return false;
            }
            return true;
        });
    }

    get tenPageCount() {
        return Math.max(1, Math.ceil(this.filteredTenancy.length / PAGE_SIZE));
    }

    get pagedTenancy() {
        const start = (this.state.tenPage - 1) * PAGE_SIZE;
        return this.filteredTenancy.slice(start, start + PAGE_SIZE);
    }

    get tenPageNumbers() {
        const count = this.tenPageCount;
        const current = this.state.tenPage;
        if (count <= 5) {
            return Array.from({ length: count }, (_, index) => index + 1);
        }
        const pages = [1];
        if (current > 3) {
            pages.push("...");
        }
        const start = Math.max(2, current - 1);
        const end = Math.min(count - 1, current + 1);
        for (let page = start; page <= end; page++) {
            pages.push(page);
        }
        if (current < count - 2) {
            pages.push("...");
        }
        pages.push(count);
        return pages;
    }

    get tenRangeLabel() {
        const total = this.filteredTenancy.length;
        if (!total) {
            return "Showing 0 entries";
        }
        const start = (this.state.tenPage - 1) * PAGE_SIZE + 1;
        const end = Math.min(total, this.state.tenPage * PAGE_SIZE);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    get selectedTenancy() {
        const id = this.state.selectedTenancyId;
        if (!id) {
            return null;
        }
        return (this.state.tenancyRecords || []).find((row) => row.id === id) || null;
    }

    get filteredDocuments() {
        const search = (this.state.docSearch || "").trim().toLowerCase();
        const days = { "30": 30, "90": 90, "365": 365 }[this.state.docDateRange];
        const cutoff = days ? Date.now() - days * 86400000 : null;
        return (this.state.documentRecords || []).filter((row) => {
            if (this.state.docCategory !== "all" && row.category !== this.state.docCategory) {
                return false;
            }
            if (this.state.docPropertyFilter !== "all" && String(row.property_id) !== String(this.state.docPropertyFilter)) {
                return false;
            }
            if (this.state.docStatusFilter !== "all" && row.status !== this.state.docStatusFilter) {
                return false;
            }
            if (cutoff && row.date && new Date(row.date).getTime() < cutoff) {
                return false;
            }
            if (search && !`${row.name} ${row.filename} ${row.associated} ${row.uploader} ${row.category_label} ${row.id}`.toLowerCase().includes(search)) {
                return false;
            }
            return true;
        });
    }

    get docPageCount() {
        return Math.max(1, Math.ceil(this.filteredDocuments.length / PAGE_SIZE));
    }

    get pagedDocuments() {
        const start = (this.state.docPage - 1) * PAGE_SIZE;
        return this.filteredDocuments.slice(start, start + PAGE_SIZE);
    }

    get docPageNumbers() {
        const count = this.docPageCount;
        const current = this.state.docPage;
        if (count <= 5) {
            return Array.from({ length: count }, (_, index) => index + 1);
        }
        const pages = [1];
        if (current > 3) {
            pages.push("...");
        }
        const start = Math.max(2, current - 1);
        const end = Math.min(count - 1, current + 1);
        for (let page = start; page <= end; page++) {
            pages.push(page);
        }
        if (current < count - 2) {
            pages.push("...");
        }
        pages.push(count);
        return pages;
    }

    get docRangeLabel() {
        const total = this.filteredDocuments.length;
        if (!total) {
            return "Showing 0 entries";
        }
        const start = (this.state.docPage - 1) * PAGE_SIZE + 1;
        const end = Math.min(total, this.state.docPage * PAGE_SIZE);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    get selectedDocument() {
        const id = this.state.selectedDocumentId;
        if (!id) {
            return null;
        }
        return (this.state.documentRecords || []).find((row) => row.id === id) || null;
    }

    get filteredStatusBoard() {
        const search = (this.state.stSearch || "").trim().toLowerCase();
        const days = { "30": 30, "90": 90, "365": 365 }[this.state.stDateRange];
        const cutoff = days ? Date.now() - days * 86400000 : null;
        return (this.state.statusRecords || []).filter((row) => {
            if (this.state.stPropertyFilter !== "all" && String(row.property_id) !== String(this.state.stPropertyFilter)) {
                return false;
            }
            if (this.state.stStatusFilter !== "all" && row.board !== this.state.stStatusFilter) {
                return false;
            }
            if (cutoff && row.updated_on && new Date(row.updated_on).getTime() < cutoff) {
                return false;
            }
            if (search && !`${row.name} ${row.property_name} ${row.building_name} ${row.status_label} ${row.updated_by}`.toLowerCase().includes(search)) {
                return false;
            }
            return true;
        });
    }

    get stPageCount() {
        return Math.max(1, Math.ceil(this.filteredStatusBoard.length / PAGE_SIZE));
    }

    get pagedStatusBoard() {
        const start = (this.state.stPage - 1) * PAGE_SIZE;
        return this.filteredStatusBoard.slice(start, start + PAGE_SIZE);
    }

    get stPageNumbers() {
        const count = this.stPageCount;
        const current = this.state.stPage;
        if (count <= 5) {
            return Array.from({ length: count }, (_, index) => index + 1);
        }
        const pages = [1];
        if (current > 3) {
            pages.push("...");
        }
        const start = Math.max(2, current - 1);
        const end = Math.min(count - 1, current + 1);
        for (let page = start; page <= end; page++) {
            pages.push(page);
        }
        if (current < count - 2) {
            pages.push("...");
        }
        pages.push(count);
        return pages;
    }

    get stRangeLabel() {
        const total = this.filteredStatusBoard.length;
        if (!total) {
            return "Showing 0 entries";
        }
        const start = (this.state.stPage - 1) * PAGE_SIZE + 1;
        const end = Math.min(total, this.state.stPage * PAGE_SIZE);
        return `Showing ${start} to ${end} of ${total} entries`;
    }

    get allPagedStatusSelected() {
        const rows = this.pagedStatusBoard;
        return Boolean(rows.length && rows.every((row) => this.state.selectedStatusIds[row.id]));
    }

    get selectedStatusCount() {
        return Object.keys(this.state.selectedStatusIds).filter((id) => this.state.selectedStatusIds[id]).length;
    }

    get statusChangeConflict() {
        const form = this.state.statusChange;
        if (!form.has_lease) {
            return false;
        }
        return ["vacant", "available", "maintenance"].includes(form.new_status);
    }

    get unitFormBuildings() {
        const propertyId = this.state.unitForm.property_id;
        const rows = this.state.unitBuildings || [];
        if (!propertyId) {
            return rows;
        }
        return rows.filter((row) => String(row.property_id) === String(propertyId));
    }

    get unitFormFloors() {
        const buildingId = this.state.unitForm.building_id;
        const rows = this.state.unitFloors || [];
        if (!buildingId) {
            return rows;
        }
        return rows.filter((row) => String(row.building_id) === String(buildingId));
    }

    get unitTypeOptions() {
        const values = ["Studio", "2 BHK", "3 BHK", "Office", ...(this.state.unitTypes || [])];
        const current = this.state.unitForm.unit_type;
        if (current && current !== "—" && !values.includes(current)) {
            values.push(current);
        }
        return [...new Set(values.filter(Boolean))];
    }

    get donutStyle() {
        const status = this.state.data.status || {};
        const total =
            (status.occupied || 0) +
            (status.vacant || 0) +
            (status.maintenance || 0) +
            (status.reserved || 0) +
            (status.available || 0);
        if (!total) {
            return "background: conic-gradient(#e5e7eb 0 100%);";
        }
        const colors = {
            occupied: "#22c55e",
            vacant: "#111827",
            maintenance: "#ef4444",
            reserved: "#60a5fa",
            available: "#94a3b8",
        };
        let acc = 0;
        const parts = [];
        for (const key of ["occupied", "vacant", "maintenance", "reserved", "available"]) {
            const pct = ((status[key] || 0) / total) * 100;
            parts.push(`${colors[key]} ${acc}% ${acc + pct}%`);
            acc += pct;
        }
        return `background: conic-gradient(${parts.join(", ")});`;
    }

    get isCompactTop() {
        return ["ownership", "tenancy", "documents", "status"].includes(this.state.page);
    }

    isNavActive(item) {
        if (item.id === "properties") {
            return ["properties", "add-property", "hierarchy", "property-detail"].includes(this.state.page);
        }
        if (item.id === "buildings") {
            return ["buildings", "building-detail"].includes(this.state.page);
        }
        if (item.id === "floors") {
            return this.state.page === "floors";
        }
        if (item.id === "units") {
            return ["units", "unit-detail"].includes(this.state.page);
        }
        if (item.id === "occupancy") {
            return this.state.page === "occupancy";
        }
        if (item.id === "ownership") {
            return this.state.page === "ownership";
        }
        if (item.id === "tenancy") {
            return this.state.page === "tenancy";
        }
        return item.id === this.state.page;
    }

    onNav(item) {
        this.state.menuId = null;
        this.state.showOwnershipTransfer = false;
        this.state.showDocumentUpload = false;
        this.state.showStatusChange = false;
        if (item.id === "overview" || item.id === "properties") {
            this.state.page = item.id;
            this.state.showHierarchyFilter = false;
            this.state.detailMenu = false;
            this.state.showBuildingForm = false;
            this.state.showFloorForm = false;
            this.state.showUnitForm = false;
            return;
        }
        if (item.id === "buildings") {
            this.openBuildings();
            return;
        }
        if (item.id === "floors") {
            this.openFloors();
            return;
        }
        if (item.id === "units") {
            this.openUnits();
            return;
        }
        if (item.id === "occupancy") {
            this.openOccupancy();
            return;
        }
        if (item.id === "ownership") {
            this.openOwnership();
            return;
        }
        if (item.id === "tenancy") {
            this.openTenancy();
            return;
        }
        if (item.id === "documents") {
            this.openDocuments();
            return;
        }
        if (item.id === "status") {
            this.openStatusBoard();
            return;
        }
        if (item.id === "property_reports" || item.id === "occupancy_reports" || item.id === "ownership_reports") {
            this.openReport(item.id);
            return;
        }
        this.openSettings();
    }

    get userName() {
        return this.user?.name || "User";
    }

    get userInitials() {
        const parts = this.userName.split(/\s+/).filter(Boolean);
        return (parts.slice(0, 2).map((part) => part[0]).join("") || "U").toUpperCase();
    }

    openSettings() {
        this.state.menuId = null;
        this.state.page = "properties";
        this.state.showHierarchyFilter = false;
        this.state.detailMenu = false;
        this.state.showBuildingForm = false;
        this.state.showFloorForm = false;
        this.state.showUnitForm = false;
    }

    saveDownload(payload) {
        const binary = atob(payload.content || "");
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index++) {
            bytes[index] = binary.charCodeAt(index);
        }
        const blob = new Blob([bytes], { type: payload.mimetype || "application/pdf" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = payload.filename || "download.pdf";
        link.click();
        URL.revokeObjectURL(link.href);
    }

    onSearchInput(event) {
        this.state.search = event.target.value;
        this.state.listPage = 1;
    }

    onGlobalSearch(event) {
        if (this.state.page === "buildings") {
            this.onBuildingSearch(event);
            return;
        }
        if (this.state.page === "floors") {
            this.onFloorBuildingSearch(event);
            return;
        }
        if (this.state.page === "units") {
            this.onUnitSearch(event);
            return;
        }
        if (this.state.page === "occupancy") {
            this.onOccSearch(event);
            return;
        }
        if (this.state.page === "ownership") {
            this.onOwnSearch(event);
            return;
        }
        if (this.state.page === "tenancy") {
            this.onTenSearch(event);
            return;
        }
        if (this.state.page === "documents") {
            this.onDocSearch(event);
            return;
        }
        if (this.state.page === "status") {
            this.onStSearch(event);
            return;
        }
        this.onSearchInput(event);
    }

    onTypeFilter(event) {
        this.state.typeFilter = event.target.value;
        this.state.listPage = 1;
    }

    onStatusFilter(event) {
        this.state.statusFilter = event.target.value;
        this.state.listPage = 1;
    }

    onLocationFilter(event) {
        this.state.locationFilter = event.target.value;
        this.state.listPage = 1;
    }

    toggleMoreFilters() {
        this.state.showMoreFilters = !this.state.showMoreFilters;
    }

    setListPage(page) {
        if (page === "..." || page < 1 || page > this.pageCount) {
            return;
        }
        this.state.listPage = page;
    }

    toggleMenu(id, event) {
        event.stopPropagation();
        this.state.menuId = this.state.menuId === id ? null : id;
    }

    closeMenus() {
        this.state.menuId = null;
        this.state.detailMenu = false;
    }

    occupancyBarClass(value) {
        if (!value) {
            return "is-zero";
        }
        if (value >= 80) {
            return "is-high";
        }
        return "is-mid";
    }

    buildingStatusClass(status) {
        return {
            active: "is-healthy",
            maintenance: "is-maint-blue",
            construction: "is-construction",
        }[status] || "is-construction";
    }

    async openBuildings() {
        this.state.page = "buildings";
        this.state.showBuildingForm = false;
        this.state.detailMenu = false;
        this.state.menuId = null;
        this.state.loadingBuildings = true;
        try {
            const data = await this.orm.call("property.building", "get_buildings_data", []);
            this.state.buildingsList = data.buildings || [];
            this.state.buildingProperties = data.properties || [];
            if (this.state.buildingPage > this.buildingPageCount) {
                this.state.buildingPage = 1;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load buildings.", {
                title: "Buildings & Towers",
                type: "danger",
            });
        } finally {
            this.state.loadingBuildings = false;
        }
    }

    onBuildingSearch(event) {
        this.state.buildingSearch = event.target.value;
        this.state.buildingPage = 1;
    }

    onBuildingPropertyFilter(event) {
        this.state.buildingPropertyFilter = event.target.value;
        this.state.buildingPage = 1;
    }

    onBuildingStatusFilter(event) {
        this.state.buildingStatusFilter = event.target.value;
        this.state.buildingPage = 1;
    }

    setBuildingPage(page) {
        if (page === "..." || page < 1 || page > this.buildingPageCount) {
            return;
        }
        this.state.buildingPage = page;
    }

    toggleBuildingSelect(id, event) {
        event.stopPropagation();
        this.state.selectedBuildingIds[id] = !this.state.selectedBuildingIds[id];
    }

    toggleAllBuildings(event) {
        event.stopPropagation();
        const selectAll = !this.allPagedBuildingsSelected;
        for (const row of this.pagedBuildings) {
            this.state.selectedBuildingIds[row.id] = selectAll;
        }
    }

    openBuilding(id) {
        this.openBuildingDetail(id);
    }

    async openBuildingForm(id) {
        this.state.menuId = null;
        try {
            if (!this.state.buildingProperties.length) {
                const list = await this.orm.call("property.building", "get_buildings_data", []);
                this.state.buildingProperties = list.properties || [];
            }
            const data = await this.orm.call("property.building", "get_form_values", [id]);
            this.state.buildingForm = {
                ...emptyBuildingForm(),
                ...data,
                property_id: String(data.property_id || ""),
            };
            this.state.showBuildingForm = true;
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not open the building.", {
                title: "Edit Building",
                type: "danger",
            });
        }
    }

    async openBuildingDetail(id) {
        this.state.menuId = null;
        this.state.page = "building-detail";
        this.state.buildingTab = "overview";
        this.state.buildingActivityFilter = "all";
        this.state.loadingBuildingDetail = true;
        try {
            const data = await this.orm.call("property.building", "get_building_detail", [id]);
            this.state.buildingDetail = data;
            const expanded = {};
            for (const band of data.bands || []) {
                expanded[band.id] = true;
            }
            this.state.buildingExpanded = expanded;
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load building details.", {
                title: "Building Details",
                type: "danger",
            });
            this.state.page = "buildings";
        } finally {
            this.state.loadingBuildingDetail = false;
        }
    }

    setBuildingTab(tabId) {
        this.state.buildingTab = tabId;
    }

    toggleBuildingBand(id, event) {
        event.stopPropagation();
        this.state.buildingExpanded[id] = !this.state.buildingExpanded[id];
    }

    expandAllBuildingBands() {
        const expanded = {};
        for (const band of this.state.buildingDetail.bands || []) {
            expanded[band.id] = true;
        }
        this.state.buildingExpanded = expanded;
    }

    collapseAllBuildingBands() {
        this.state.buildingExpanded = {};
    }

    toggleAllBuildingBands() {
        if (this.allBuildingBandsExpanded) {
            this.collapseAllBuildingBands();
        } else {
            this.expandAllBuildingBands();
        }
    }

    cycleBuildingActivityFilter() {
        const order = ["all", "lease", "maintenance", "alert"];
        const index = order.indexOf(this.state.buildingActivityFilter);
        this.state.buildingActivityFilter = order[(index + 1) % order.length];
    }

    get filteredBuildingActivities() {
        const filter = this.state.buildingActivityFilter;
        const rows = this.state.buildingDetail.activities || [];
        if (filter === "all") {
            return rows;
        }
        return rows.filter((row) => row.type === filter);
    }

    get allBuildingBandsExpanded() {
        const bands = this.state.buildingDetail.bands || [];
        return Boolean(bands.length && bands.every((band) => this.state.buildingExpanded[band.id]));
    }

    newBuilding() {
        this.state.buildingForm = emptyBuildingForm();
        if (this.state.buildingPropertyFilter !== "all") {
            this.state.buildingForm.property_id = this.state.buildingPropertyFilter;
        }
        this.state.showBuildingForm = true;
        this.state.menuId = null;
    }

    cancelBuildingForm() {
        this.state.showBuildingForm = false;
        this.state.buildingForm = emptyBuildingForm();
    }

    async submitBuilding() {
        const form = this.state.buildingForm;
        if (!String(form.name || "").trim()) {
            this.notification.add("Building name is required.", { title: "Add Building", type: "warning" });
            return;
        }
        if (!form.property_id) {
            this.notification.add("Please select a property.", { title: "Add Building", type: "warning" });
            return;
        }
        const editing = Boolean(form.id);
        this.state.saving = true;
        try {
            const payload = {
                name: form.name,
                code: form.code,
                property_id: form.property_id,
                usage: form.usage,
                floors: form.floors,
            };
            if (editing) {
                await this.orm.call("property.building", "update_from_dashboard", [{ ...payload, id: form.id }]);
                this.notification.add("Building updated.", { type: "success" });
            } else {
                await this.orm.call("property.building", "create_from_dashboard", [payload]);
                this.notification.add("Building created.", { type: "success" });
            }
            this.state.showBuildingForm = false;
            this.state.buildingForm = emptyBuildingForm();
            if (this.state.page === "building-detail" && editing) {
                await this.openBuildingDetail(form.id);
            } else {
                await this.openBuildings();
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || (editing ? "Could not update the building." : "Could not create the building."), {
                title: editing ? "Edit Building" : "Add Building",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    get filteredFloorBuildings() {
        const query = (this.state.floorBuildingSearch || "").trim().toLowerCase();
        const rows = this.state.floorsWorkspace.buildings || [];
        if (!query) {
            return rows;
        }
        return rows.filter((row) =>
            [row.name, row.full_name, row.property_name].some((value) => (value || "").toLowerCase().includes(query))
        );
    }

    get floorFormTitle() {
        return {
            floor: "Add Floor",
            wing: "Add Wing",
            edit: "Edit Floor",
        }[this.state.floorForm.mode] || "Floor";
    }

    async openFloors(buildingId, expandFloorId) {
        this.state.page = "floors";
        this.state.showBuildingForm = false;
        this.state.showFloorForm = false;
        this.state.detailMenu = false;
        this.state.menuId = null;
        this.state.loadingFloors = true;
        const targetId = buildingId || this.state.selectedFloorBuildingId;
        try {
            const data = await this.orm.call("property.floor", "get_floors_workspace", [targetId || null]);
            this.state.floorsWorkspace = data;
            this.state.selectedFloorBuildingId = data.selected_id;
            const previous = { ...this.state.floorExpanded };
            const expanded = {};
            const floors = data.floors || [];
            for (const floor of floors) {
                if (previous[floor.id]) {
                    expanded[floor.id] = true;
                }
            }
            if (expandFloorId) {
                expanded[expandFloorId] = true;
            }
            if (!Object.keys(expanded).length && floors[0]) {
                expanded[floors[0].id] = true;
            }
            this.state.floorExpanded = expanded;
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load floors.", {
                title: "Floors & Wings",
                type: "danger",
            });
        } finally {
            this.state.loadingFloors = false;
        }
    }

    onFloorBuildingSearch(event) {
        this.state.floorBuildingSearch = event.target.value;
    }

    selectFloorBuilding(id) {
        this.openFloors(id);
    }

    toggleFloorRow(id, event) {
        event.stopPropagation();
        this.state.floorExpanded[id] = !this.state.floorExpanded[id];
    }

    newFloor() {
        const buildingId = this.state.selectedFloorBuildingId;
        if (!buildingId) {
            this.notification.add("Select a building first.", { title: "Add Floor", type: "warning" });
            return;
        }
        const numbers = (this.state.floorsWorkspace.floors || []).map((row) => row.number || 0);
        const nextNumber = (numbers.length ? Math.max(...numbers) : 0) + 1;
        this.state.floorForm = {
            ...emptyFloorForm(),
            mode: "floor",
            building_id: buildingId,
            name: `Floor ${nextNumber}`,
            floor_number: nextNumber,
            wing: "A",
        };
        this.state.showFloorForm = true;
    }

    newWing() {
        const buildingId = this.state.selectedFloorBuildingId;
        const floors = this.state.floorsWorkspace.floors || [];
        if (!buildingId || !floors.length) {
            this.notification.add("Add a floor before adding a wing.", { title: "Add Wing", type: "warning" });
            return;
        }
        const current = floors.find((row) => this.state.floorExpanded[row.id]) || floors[0];
        const used = new Set(current.record_wings || []);
        const nextWing = ["A", "B", "C", "D", "E"].find((letter) => !used.has(letter)) || "F";
        this.state.floorForm = {
            ...emptyFloorForm(),
            mode: "wing",
            building_id: buildingId,
            floor_number: current.number,
            name: current.name,
            wing: nextWing,
        };
        this.state.showFloorForm = true;
    }

    editFloor(row, event) {
        event.stopPropagation();
        this.state.floorForm = {
            ...emptyFloorForm(),
            mode: "edit",
            floor_id: row.floor_id,
            building_id: this.state.selectedFloorBuildingId,
            name: row.name,
            floor_number: row.number,
            wing: "A",
        };
        this.state.showFloorForm = true;
    }

    cancelFloorForm() {
        this.state.showFloorForm = false;
        this.state.floorForm = emptyFloorForm();
    }

    async submitFloorForm() {
        const form = this.state.floorForm;
        if (!form.building_id) {
            this.notification.add("Please select a building.", { title: "Floors & Wings", type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            if (form.mode === "edit") {
                await this.orm.call("property.floor", "update_from_dashboard", [form.floor_id, {
                    name: form.name,
                    floor_number: form.floor_number,
                }]);
                this.notification.add("Floor updated.", { type: "success" });
            } else {
                await this.orm.call("property.floor", "create_from_dashboard", [{
                    building_id: form.building_id,
                    name: form.name,
                    floor_number: form.floor_number,
                    wing: form.wing,
                }]);
                this.notification.add(form.mode === "wing" ? "Wing added." : "Floor added.", { type: "success" });
            }
            this.state.showFloorForm = false;
            this.state.floorForm = emptyFloorForm();
            await this.openFloors(form.building_id);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not save.", {
                title: "Floors & Wings",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    deleteFloor(row, event) {
        event.stopPropagation();
        const buildingId = this.state.selectedFloorBuildingId;
        this.dialog.add(ConfirmationDialog, {
            title: "Delete Floor",
            body: `Delete ${row.name} and its wings from this building?`,
            confirm: async () => {
                try {
                    await this.orm.call("property.floor", "delete_floor_group", [buildingId, row.number]);
                    this.notification.add("Floor deleted.", { type: "success" });
                    await this.openFloors(buildingId);
                } catch (error) {
                    this.notification.add(error?.data?.message || error?.message || "Could not delete the floor.", {
                        title: "Floors & Wings",
                        type: "danger",
                    });
                }
            },
        });
    }

    async openUnits() {
        this.state.page = "units";
        this.state.showBuildingForm = false;
        this.state.showFloorForm = false;
        this.state.showUnitForm = false;
        this.state.detailMenu = false;
        this.state.menuId = null;
        this.state.loadingUnits = true;
        try {
            const data = await this.orm.call("property.unit", "get_units_data", []);
            this.state.unitsList = data.units || [];
            this.state.unitProperties = data.properties || [];
            this.state.unitBuildings = data.buildings || [];
            this.state.unitFloors = data.floors || [];
            this.state.unitTypes = data.types || [];
            if (this.state.unitPage > this.unitPageCount) {
                this.state.unitPage = 1;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load units.", {
                title: "Units",
                type: "danger",
            });
        } finally {
            this.state.loadingUnits = false;
        }
    }

    async openOccupancy() {
        this.state.page = "occupancy";
        this.state.showBuildingForm = false;
        this.state.showFloorForm = false;
        this.state.showUnitForm = false;
        this.state.detailMenu = false;
        this.state.menuId = null;
        this.state.loadingOccupancy = true;
        try {
            const data = await this.orm.call("property.unit", "get_occupancy_data", []);
            this.state.occupancyUnits = data.units || [];
            this.state.occupancyProperties = data.properties || [];
            this.state.occupancyBuildings = data.buildings || [];
            this.state.occupancyFloors = data.floors || [];
            this.state.occupancyMonths = data.months || [];
            this.state.occupancyTarget = data.target || 95;
            if (this.state.occPage > this.occPageCount) {
                this.state.occPage = 1;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load occupancy.", {
                title: "Occupancy",
                type: "danger",
            });
        } finally {
            this.state.loadingOccupancy = false;
        }
    }

    onOccSearch(event) {
        this.state.occSearch = event.target.value;
        this.state.occPage = 1;
    }

    onOccDraftProperty(event) {
        this.state.occDraft.property = event.target.value;
        this.state.occDraft.building = "all";
        this.state.occDraft.floor = "all";
    }

    onOccDraftFloor(event) {
        this.state.occDraft.floor = event.target.value;
    }

    onOccDraftBuilding(event) {
        this.state.occDraft.building = event.target.value;
        this.state.occDraft.floor = "all";
    }

    onOccDraftStatus(event) {
        this.state.occDraft.status = event.target.value;
    }

    applyOccupancyFilters() {
        this.state.occApplied = { ...this.state.occDraft };
        this.state.occPage = 1;
    }

    resetOccupancyFilters() {
        const empty = emptyOccupancyFilters();
        this.state.occDraft = empty;
        this.state.occApplied = { ...empty };
        this.state.occPage = 1;
    }

    setOccPage(page) {
        if (page === "..." || page < 1 || page > this.occPageCount) {
            return;
        }
        this.state.occPage = page;
    }

    directoryStatusClass(status) {
        return {
            occupied: "is-occ-occupied",
            vacant: "is-occ-dir-vacant",
            reserved: "is-occ-reserved",
            maintenance: "is-occ-maint",
        }[status] || "is-occ-dir-vacant";
    }

    async openOwnership() {
        this.state.page = "ownership";
        this.state.showBuildingForm = false;
        this.state.showFloorForm = false;
        this.state.showUnitForm = false;
        this.state.showOwnershipTransfer = false;
        this.state.detailMenu = false;
        this.state.menuId = null;
        this.state.loadingOwnership = true;
        try {
            const data = await this.orm.call("property.owner", "get_ownership_data", []);
            this.state.ownershipRecords = data.records || [];
            this.state.ownershipUnits = data.units || [];
            this.state.ownershipProperties = data.properties || [];
            this.state.ownershipKpis = data.kpis || this.state.ownershipKpis;
            if (this.state.ownPage > this.ownPageCount) {
                this.state.ownPage = 1;
            }
            if (!this.selectedOwnership && this.pagedOwnership.length) {
                this.state.selectedOwnershipId = this.pagedOwnership[0].id;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load ownership.", {
                title: "Ownership",
                type: "danger",
            });
        } finally {
            this.state.loadingOwnership = false;
        }
    }

    onOwnSearch(event) {
        this.state.ownSearch = event.target.value;
        this.state.ownPage = 1;
    }

    setOwnTab(tab) {
        this.state.ownTab = tab;
        this.state.ownPage = 1;
    }

    onOwnPropertyFilter(event) {
        this.state.ownPropertyFilter = event.target.value;
        this.state.ownPage = 1;
    }

    onOwnStatusFilter(event) {
        this.state.ownStatusFilter = event.target.value;
        this.state.ownPage = 1;
    }

    toggleOwnershipFilters() {
        this.state.showOwnershipFilters = !this.state.showOwnershipFilters;
    }

    setOwnPage(page) {
        if (page === "..." || page < 1 || page > this.ownPageCount) {
            return;
        }
        this.state.ownPage = page;
    }

    selectOwnership(row) {
        this.state.selectedOwnershipId = row.id;
        this.state.menuId = null;
    }

    closeOwnershipDrawer() {
        this.state.selectedOwnershipId = null;
    }

    ownershipStatusClass(status) {
        return status === "pending" ? "is-own-pending" : "is-healthy";
    }

    openOwnershipTransfer(row) {
        const selected = row || this.selectedOwnership;
        this.state.ownershipTransfer = {
            ...emptyOwnershipTransfer(),
            unit_id: selected ? String(selected.unit_id) : "",
            owner_name: selected ? selected.owner_name : "",
            owner_type: selected ? selected.owner_type : "primary",
            share: selected ? selected.share : 100,
        };
        this.state.showOwnershipTransfer = true;
    }

    cancelOwnershipTransfer() {
        this.state.showOwnershipTransfer = false;
        this.state.ownershipTransfer = emptyOwnershipTransfer();
    }

    async submitOwnershipTransfer() {
        const form = this.state.ownershipTransfer;
        if (!form.unit_id) {
            this.notification.add("Please select a unit.", { title: "Record Transfer", type: "warning" });
            return;
        }
        if (!(form.owner_name || "").trim()) {
            this.notification.add("Owner name is required.", { title: "Record Transfer", type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("property.owner", "record_transfer", [{
                unit_id: form.unit_id,
                owner_name: form.owner_name,
                owner_type: form.owner_type,
                share: form.share,
                effective_date: form.effective_date || false,
                status: form.status,
            }]);
            this.notification.add("Ownership transfer recorded.", { type: "success" });
            this.state.showOwnershipTransfer = false;
            this.state.ownershipTransfer = emptyOwnershipTransfer();
            await this.openOwnership();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not record the transfer.", {
                title: "Record Transfer",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    openOwnershipProfile() {
        const selected = this.selectedOwnership;
        if (selected?.unit_id) {
            this.openUnitDetail(selected.unit_id);
        }
    }

    openOwnershipEdit() {
        const selected = this.selectedOwnership;
        if (!selected) {
            this.notification.add("Select an ownership record first.", { title: "Edit Ownership", type: "warning" });
            return;
        }
        this.state.ownershipEdit = {
            record_id: selected.record_id || false,
            unit_id: selected.unit_id,
            unit_name: selected.unit_name || "",
            owner_name: selected.owner_name && selected.owner_name !== "Unassigned" ? selected.owner_name : "",
            owner_type: selected.owner_type || "primary",
            share: selected.share || 0,
            effective_date: selected.effective || "",
            status: selected.status || "active",
            cost: selected.cost || 0,
            deed: selected.deed && selected.deed !== "—" ? selected.deed : "",
        };
        this.state.showOwnershipEdit = true;
    }

    cancelOwnershipEdit() {
        this.state.showOwnershipEdit = false;
        this.state.ownershipEdit = emptyOwnershipEdit();
    }

    async submitOwnershipEdit() {
        const form = this.state.ownershipEdit;
        if (!(form.owner_name || "").trim()) {
            this.notification.add("Owner name is required.", { title: "Edit Ownership", type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            const result = await this.orm.call("property.owner", "update_from_dashboard", [{
                record_id: form.record_id,
                unit_id: form.unit_id,
                owner_name: form.owner_name,
                owner_type: form.owner_type,
                share: form.share,
                effective_date: form.effective_date || false,
                status: form.status,
                cost: form.cost,
                deed: form.deed,
            }]);
            this.notification.add("Ownership updated.", { type: "success" });
            this.state.showOwnershipEdit = false;
            this.state.ownershipEdit = emptyOwnershipEdit();
            await this.openOwnership();
            if (result && result.selected_id) {
                this.state.selectedOwnershipId = result.selected_id;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not update ownership.", {
                title: "Edit Ownership",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    async openTenancy() {
        this.state.page = "tenancy";
        this.state.showBuildingForm = false;
        this.state.showFloorForm = false;
        this.state.showUnitForm = false;
        this.state.showOwnershipTransfer = false;
        this.state.detailMenu = false;
        this.state.menuId = null;
        this.state.loadingTenancy = true;
        try {
            const data = await this.orm.call("property.tenancy", "get_tenancy_data", []);
            this.state.tenancyRecords = data.records || [];
            this.state.tenancyProperties = data.properties || [];
            this.state.tenancyKpis = data.kpis || this.state.tenancyKpis;
            if (this.state.tenPage > this.tenPageCount) {
                this.state.tenPage = 1;
            }
            if (!this.selectedTenancy && this.pagedTenancy.length) {
                this.state.selectedTenancyId = this.pagedTenancy[0].id;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load tenant history.", {
                title: "Tenant History",
                type: "danger",
            });
        } finally {
            this.state.loadingTenancy = false;
        }
    }

    onTenSearch(event) {
        this.state.tenSearch = event.target.value;
        this.state.tenPage = 1;
    }

    onTenStatusFilter(event) {
        this.state.tenStatusFilter = event.target.value;
        this.state.tenPage = 1;
    }

    onTenDateRange(event) {
        this.state.tenDateRange = event.target.value;
        this.state.tenPage = 1;
    }

    onTenPropertyFilter(event) {
        this.setTenPropertyFilter(event.target.value);
    }

    setTenPropertyFilter(value) {
        this.state.tenPropertyFilter = value;
        this.state.tenPage = 1;
        this.state.showTenancyFilters = false;
    }

    toggleTenancyFilters() {
        this.state.showTenancyFilters = !this.state.showTenancyFilters;
    }

    setTenPage(page) {
        if (page === "..." || page < 1 || page > this.tenPageCount) {
            return;
        }
        this.state.tenPage = page;
    }

    selectTenancy(row) {
        this.state.selectedTenancyId = row.id;
        this.state.menuId = null;
    }

    closeTenancyDrawer() {
        this.state.selectedTenancyId = null;
    }

    tenancyStatusClass(status) {
        return {
            present: "is-healthy",
            ended: "is-own-pending",
            upcoming: "is-occ-reserved",
        }[status] || "is-op-active";
    }

    async openTenancyLease() {
        const selected = this.selectedTenancy;
        if (!selected) {
            return;
        }
        try {
            const payload = await this.orm.call("property.tenancy", "lease_file", [
                selected.record_id || false,
                selected.unit_id || false,
                selected.tenant_name || false,
                selected.move_in || false,
                selected.move_out || false,
            ]);
            this.saveDownload(payload);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not open the lease.", {
                title: "View Lease",
                type: "danger",
            });
        }
    }

    openTenancyMessage() {
        if (!this.selectedTenancy) {
            return;
        }
        this.state.tenancyNote = "";
        this.state.showTenancyNote = true;
    }

    cancelTenancyNote() {
        this.state.showTenancyNote = false;
        this.state.tenancyNote = "";
    }

    async sendTenancyNote() {
        const selected = this.selectedTenancy;
        const note = (this.state.tenancyNote || "").trim();
        if (!selected || !note) {
            this.notification.add("Enter a message.", { title: "Tenant History", type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("property.tenancy", "log_message", [
                selected.record_id || false,
                selected.unit_id || false,
                note,
            ]);
            const selectedId = selected.id;
            this.state.showTenancyNote = false;
            this.state.tenancyNote = "";
            this.notification.add("Message saved on the tenancy.", { type: "success" });
            await this.openTenancy();
            this.state.selectedTenancyId = selectedId;
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not save the message.", {
                title: "Tenant History",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    async openDocuments() {
        this.state.page = "documents";
        this.state.showBuildingForm = false;
        this.state.showFloorForm = false;
        this.state.showUnitForm = false;
        this.state.showOwnershipTransfer = false;
        this.state.showDocumentUpload = false;
        this.state.detailMenu = false;
        this.state.menuId = null;
        this.state.loadingDocuments = true;
        try {
            const data = await this.orm.call("property.document", "get_documents_data", []);
            this.state.documentRecords = data.records || [];
            this.state.documentProperties = data.properties || [];
            if (this.state.docPage > this.docPageCount) {
                this.state.docPage = 1;
            }
            if (!this.selectedDocument && this.pagedDocuments.length) {
                this.state.selectedDocumentId = this.pagedDocuments[0].id;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load documents.", {
                title: "Documents",
                type: "danger",
            });
        } finally {
            this.state.loadingDocuments = false;
        }
    }

    onDocSearch(event) {
        this.state.docSearch = event.target.value;
        this.state.docPage = 1;
    }

    onDocCategory(event) {
        this.state.docCategory = event.target.value;
        this.state.docPage = 1;
    }

    onDocPropertyFilter(event) {
        this.state.docPropertyFilter = event.target.value;
        this.state.docPage = 1;
    }

    onDocStatusFilter(event) {
        this.state.docStatusFilter = event.target.value;
        this.state.docPage = 1;
    }

    onDocDateRange(event) {
        this.state.docDateRange = event.target.value;
        this.state.docPage = 1;
    }

    resetDocumentFilters() {
        this.state.docSearch = "";
        this.state.docCategory = "all";
        this.state.docPropertyFilter = "all";
        this.state.docStatusFilter = "all";
        this.state.docDateRange = "all";
        this.state.docPage = 1;
    }

    setDocPage(page) {
        if (page === "..." || page < 1 || page > this.docPageCount) {
            return;
        }
        this.state.docPage = page;
    }

    selectDocument(row) {
        this.state.selectedDocumentId = row.id;
        this.state.menuId = null;
    }

    closeDocumentDrawer() {
        this.state.selectedDocumentId = null;
    }

    documentStatusClass(status) {
        return {
            active: "is-healthy",
            expired: "is-review",
            archived: "is-draft",
        }[status] || "is-op-active";
    }

    documentExpiryClass(row) {
        if (!row.expiry) {
            return "is-draft";
        }
        return row.status === "expired" ? "is-review" : "is-healthy";
    }

    openDocumentUpload() {
        this.state.documentUpload = emptyDocumentUpload();
        this.state.showDocumentUpload = true;
    }

    cancelDocumentUpload() {
        this.state.showDocumentUpload = false;
        this.state.documentUpload = emptyDocumentUpload();
    }

    onDocumentFile(event) {
        const file = event.target.files && event.target.files[0];
        if (!file) {
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const result = String(reader.result || "");
            const data = result.includes(",") ? result.split(",")[1] : result;
            this.state.documentUpload.filename = file.name;
            this.state.documentUpload.data = data;
            this.state.documentUpload.size = file.size;
            if (!this.state.documentUpload.name) {
                this.state.documentUpload.name = file.name;
            }
        };
        reader.readAsDataURL(file);
    }

    async submitDocumentUpload() {
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("property.document", "upload_document", [this.state.documentUpload]);
            this.state.showDocumentUpload = false;
            this.state.documentUpload = emptyDocumentUpload();
            this.notification.add("Document uploaded.", { title: "Documents", type: "success" });
            await this.openDocuments();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not upload the document.", {
                title: "Documents",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    fileBytes(data) {
        const binary = atob(data || "");
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index++) {
            bytes[index] = binary.charCodeAt(index);
        }
        return bytes;
    }

    previewType(filename) {
        const name = (filename || "").toLowerCase();
        if (name.endsWith(".pdf")) {
            return { kind: "pdf", type: "application/pdf" };
        }
        if (name.endsWith(".png")) {
            return { kind: "image", type: "image/png" };
        }
        if (name.endsWith(".jpg") || name.endsWith(".jpeg")) {
            return { kind: "image", type: "image/jpeg" };
        }
        if (name.endsWith(".gif")) {
            return { kind: "image", type: "image/gif" };
        }
        if (name.endsWith(".webp")) {
            return { kind: "image", type: "image/webp" };
        }
        return { kind: "other", type: "application/octet-stream" };
    }

    closeDocumentViewer() {
        if (this.state.documentViewer?.url) {
            URL.revokeObjectURL(this.state.documentViewer.url);
        }
        this.state.showDocumentViewer = false;
        this.state.documentViewer = { name: "", url: "", kind: "" };
    }

    async openDocumentViewer(row) {
        const target = row || this.selectedDocument;
        if (!target?.record_id) {
            this.notification.add("This document has no stored file to open.", {
                title: "Documents",
                type: "warning",
            });
            return;
        }
        try {
            const file = await this.orm.call("property.document", "get_file", [target.record_id]);
            const filename = file.filename || target.filename || target.name || "document";
            const info = this.previewType(filename);
            this.closeDocumentViewer();
            const url = info.kind === "other"
                ? ""
                : URL.createObjectURL(new Blob([this.fileBytes(file.data)], { type: info.type }));
            this.state.documentViewer = { name: filename, url, kind: info.kind };
            this.state.showDocumentViewer = true;
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not open the file.", {
                title: "Documents",
                type: "danger",
            });
        }
    }

    async downloadDocument(row) {
        const target = row || this.selectedDocument;
        if (!target?.record_id) {
            this.notification.add("This document has no stored file to download.", {
                title: "Documents",
                type: "warning",
            });
            return;
        }
        try {
            const file = await this.orm.call("property.document", "get_file", [target.record_id]);
            const blob = new Blob([this.fileBytes(file.data)]);
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = file.filename || target.filename || target.name || "document";
            link.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not download the file.", {
                title: "Documents",
                type: "danger",
            });
        }
    }

    async showDocumentVersions(row) {
        const target = row || this.selectedDocument;
        if (!target) {
            return;
        }
        this.state.menuId = null;
        this.state.documentVersionName = target.name || "Document";
        if (target.record_id) {
            try {
                this.state.documentVersions = await this.orm.call("property.document", "get_versions", [target.record_id]);
            } catch (error) {
                this.notification.add(error?.data?.message || error?.message || "Could not load version history.", {
                    title: "Version History",
                    type: "danger",
                });
                return;
            }
        } else {
            const labels = (target.versions || [target.version || "v1.0"]).filter(Boolean);
            this.state.documentVersions = labels.map((version) => ({
                version,
                filename: target.filename || target.name,
                size_label: target.size_label,
                uploader: target.uploader,
                date_label: target.date_label,
                current: version === (target.version || labels[0]),
            }));
        }
        this.state.showDocumentVersions = true;
    }

    closeDocumentVersions() {
        this.state.showDocumentVersions = false;
        this.state.documentVersions = [];
    }

    deleteDocument(row) {
        const target = row || this.selectedDocument;
        if (!target) {
            return;
        }
        this.state.menuId = null;
        this.state.documentPendingDelete = target;
        this.state.showDocumentDelete = true;
    }

    cancelDocumentDelete() {
        this.state.showDocumentDelete = false;
        this.state.documentPendingDelete = null;
    }

    async confirmDocumentDelete() {
        const row = this.state.documentPendingDelete;
        if (!row) {
            this.cancelDocumentDelete();
            return;
        }
        this.state.saving = true;
        try {
            if (row.record_id) {
                await this.orm.call("property.document", "unlink_document", [row.record_id]);
                await this.openDocuments();
            } else {
                this.state.documentRecords = (this.state.documentRecords || []).filter((item) => item.id !== row.id);
            }
            if (this.state.selectedDocumentId === row.id) {
                this.state.selectedDocumentId = null;
            }
            this.notification.add("Document deleted.", { title: "Documents", type: "success" });
            this.cancelDocumentDelete();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not delete the document.", {
                title: "Documents",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    async openReport(reportId) {
        this.state.page = reportId;
        this.state.menuId = null;
        this.state.showBuildingForm = false;
        this.state.showFloorForm = false;
        this.state.showUnitForm = false;
        this.state.showOwnershipTransfer = false;
        this.state.showOwnershipEdit = false;
        this.state.detailMenu = false;
        this.state.loadingReport = true;
        try {
            if (reportId === "property_reports") {
                const data = await this.orm.call("property.property", "get_dashboard_data", []);
                this.state.reportProperties = data.properties || [];
                this.state.reportStatus = data.status || {};
            } else if (reportId === "occupancy_reports") {
                const data = await this.orm.call("property.unit", "get_occupancy_data", []);
                this.state.reportOccupancyUnits = data.units || [];
            } else {
                const data = await this.orm.call("property.owner", "get_ownership_data", []);
                this.state.reportOwnership = data.records || [];
                this.state.reportOwnershipKpis = data.kpis || {};
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load the report.", {
                title: "Reports",
                type: "danger",
            });
        } finally {
            this.state.loadingReport = false;
        }
    }

    get reportTitle() {
        return {
            property_reports: "Property Reports",
            occupancy_reports: "Occupancy Reports",
            ownership_reports: "Ownership Reports",
        }[this.state.page] || "Reports";
    }

    get reportSubtitle() {
        return {
            property_reports: "Properties, buildings, units, and occupancy stored in the database.",
            occupancy_reports: "Live unit status and tenant occupancy.",
            ownership_reports: "Owners, shares, and effective dates stored on each unit.",
        }[this.state.page] || "";
    }

    get reportPropertyTotals() {
        const rows = this.state.reportProperties || [];
        return {
            buildings: rows.reduce((sum, row) => sum + (row.building_count || 0), 0),
            units: rows.reduce((sum, row) => sum + (row.unit_count || 0), 0),
        };
    }

    get reportOccupancyTotals() {
        const rows = this.state.reportOccupancyUnits || [];
        const occupied = rows.filter((row) => row.directory_status === "occupied").length;
        const vacant = rows.filter((row) => row.directory_status === "vacant").length;
        const reserved = rows.filter((row) => row.directory_status === "reserved").length;
        const maintenance = rows.filter((row) => row.directory_status === "maintenance").length;
        const total = rows.length;
        return {
            total,
            occupied,
            vacant,
            reserved,
            maintenance,
            pct: total ? Math.round((occupied / total) * 1000) / 10 : 0,
        };
    }

    async openStatusBoard() {
        this.state.page = "status";
        this.state.showBuildingForm = false;
        this.state.showFloorForm = false;
        this.state.showUnitForm = false;
        this.state.showOwnershipTransfer = false;
        this.state.showDocumentUpload = false;
        this.state.showStatusChange = false;
        this.state.detailMenu = false;
        this.state.menuId = null;
        this.state.loadingStatusBoard = true;
        try {
            const data = await this.orm.call("property.unit", "get_unit_status_data", []);
            this.state.statusRecords = data.records || [];
            this.state.statusProperties = data.properties || [];
            this.state.statusKpis = data.kpis || this.state.statusKpis;
            if (this.state.stPage > this.stPageCount) {
                this.state.stPage = 1;
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load unit status.", {
                title: "Unit Status",
                type: "danger",
            });
        } finally {
            this.state.loadingStatusBoard = false;
        }
    }

    onStSearch(event) {
        this.state.stSearch = event.target.value;
        this.state.stPage = 1;
    }

    onStDateRange(event) {
        this.state.stDateRange = event.target.value;
        this.state.stPage = 1;
    }

    onStStatusFilter(event) {
        this.state.stStatusFilter = event.target.value;
        this.state.stPage = 1;
    }

    setStPropertyFilter(value) {
        this.state.stPropertyFilter = value;
        this.state.stPage = 1;
        this.state.showStatusFilters = false;
    }

    toggleStatusFilters() {
        this.state.showStatusFilters = !this.state.showStatusFilters;
    }

    setStPage(page) {
        if (page === "..." || page < 1 || page > this.stPageCount) {
            return;
        }
        this.state.stPage = page;
    }

    toggleStatusRow(id, event) {
        event.stopPropagation();
        this.state.selectedStatusIds = {
            ...this.state.selectedStatusIds,
            [id]: !this.state.selectedStatusIds[id],
        };
    }

    toggleAllStatusRows() {
        const selectAll = !this.allPagedStatusSelected;
        const next = { ...this.state.selectedStatusIds };
        for (const row of this.pagedStatusBoard) {
            next[row.id] = selectAll;
        }
        this.state.selectedStatusIds = next;
    }

    boardStatusClass(board) {
        return {
            available: "is-st-available",
            occupied: "is-st-occupied",
            unoccupied: "is-st-unoccupied",
        }[board] || "is-st-occupied";
    }

    boardFromStatus(status) {
        if (status === "maintenance") {
            return "unoccupied";
        }
        if (status === "vacant" || status === "available") {
            return "available";
        }
        return "occupied";
    }

    openStatusChange(row, event) {
        if (event) {
            event.stopPropagation();
        }
        const today = new Date().toISOString().slice(0, 10);
        this.state.statusChange = {
            ...emptyStatusChange(),
            unit_id: row.id,
            unit_ids: [row.id],
            unit_name: row.name,
            property_name: row.property_name,
            current_status: row.status,
            current_label: row.status_label,
            new_status: row.has_lease ? "vacant" : "occupied",
            effective_date: today,
            has_lease: row.has_lease,
            bulk: false,
        };
        this.state.showStatusChange = true;
    }

    openBulkStatusChange() {
        const ids = Object.keys(this.state.selectedStatusIds)
            .filter((id) => this.state.selectedStatusIds[id])
            .map((id) => Number(id));
        if (!ids.length) {
            this.notification.add("Select at least one unit to update.", {
                title: "Bulk update",
                type: "warning",
            });
            return;
        }
        const rows = (this.state.statusRecords || []).filter((row) => ids.includes(row.id));
        const hasLease = rows.some((row) => row.has_lease);
        const today = new Date().toISOString().slice(0, 10);
        this.state.statusChange = {
            ...emptyStatusChange(),
            unit_id: null,
            unit_ids: ids,
            unit_name: `${ids.length} units`,
            property_name: "Selected units",
            current_status: "",
            current_label: "Mixed",
            new_status: "vacant",
            effective_date: today,
            has_lease: hasLease,
            bulk: true,
        };
        this.state.showStatusChange = true;
    }

    cancelStatusChange() {
        this.state.showStatusChange = false;
        this.state.statusChange = emptyStatusChange();
    }

    statusReasonLabel(code) {
        return {
            lease_abandonment: "Lease Abandonment",
            lease_ended: "Lease Ended",
            tenant_transfer: "Tenant Transfer",
            maintenance_required: "Maintenance Required",
            owner_request: "Owner Request",
            occupancy_update: "Occupancy Update",
            other: "Other",
        }[code] || code;
    }

    async submitStatusChange() {
        const form = this.state.statusChange;
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        const extra = {
            reason: this.statusReasonLabel(form.reason),
            notes: form.notes,
            effective_date: form.effective_date,
        };
        try {
            if (form.bulk) {
                const result = await this.orm.call("property.unit", "bulk_update_status", [form.unit_ids, form.new_status, extra]);
                this.notification.add(`Updated ${result.count || form.unit_ids.length} units.`, {
                    title: "Unit Status",
                    type: "success",
                });
                this.state.selectedStatusIds = {};
            } else {
                await this.orm.call("property.unit", "update_status", [form.unit_id, form.new_status, extra]);
                this.notification.add("Status updated.", { title: "Unit Status", type: "success" });
            }
            this.state.showStatusChange = false;
            this.state.statusChange = emptyStatusChange();
            await this.openStatusBoard();
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not update status.", {
                title: "Unit Status",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    onUnitSearch(event) {
        this.state.unitSearch = event.target.value;
        this.state.unitPage = 1;
    }

    onUnitPropertyFilter(event) {
        this.state.unitPropertyFilter = event.target.value;
        this.state.unitBuildingFilter = "all";
        this.state.unitFloorFilter = "all";
        this.state.unitWingFilter = "all";
        this.state.unitPage = 1;
    }

    onUnitBuildingFilter(event) {
        this.state.unitBuildingFilter = event.target.value;
        this.state.unitFloorFilter = "all";
        this.state.unitWingFilter = "all";
        this.state.unitPage = 1;
    }

    onUnitFloorFilter(event) {
        this.state.unitFloorFilter = event.target.value;
        this.state.unitPage = 1;
    }

    onUnitWingFilter(event) {
        this.state.unitWingFilter = event.target.value;
        this.state.unitPage = 1;
    }

    onUnitTypeFilter(event) {
        this.state.unitTypeFilter = event.target.value;
        this.state.unitPage = 1;
    }

    onUnitOccupancyFilter(event) {
        this.state.unitOccupancyFilter = event.target.value;
        this.state.unitPage = 1;
    }

    onUnitOpStatusFilter(event) {
        this.state.unitOpStatusFilter = event.target.value;
        this.state.unitPage = 1;
    }

    setUnitPage(page) {
        if (page === "..." || page < 1 || page > this.unitPageCount) {
            return;
        }
        this.state.unitPage = page;
    }

    toggleUnitSelect(id, event) {
        event.stopPropagation();
        this.state.selectedUnitIds[id] = !this.state.selectedUnitIds[id];
    }

    toggleAllUnits(event) {
        event.stopPropagation();
        const selectAll = !this.allPagedUnitsSelected;
        for (const row of this.pagedUnits) {
            this.state.selectedUnitIds[row.id] = selectAll;
        }
    }

    occupancyClass(occupancy) {
        return {
            occupied: "is-occ-occupied",
            vacant: "is-occ-vacant",
            reserved: "is-occ-reserved",
            maintenance: "is-occ-maint",
        }[occupancy] || "is-occ-vacant";
    }

    opStatusClass(status) {
        return {
            active: "is-op-active",
            maintenance: "is-op-maint",
            turnover: "is-op-turnover",
        }[status] || "is-op-active";
    }

    async ensureUnitCatalog() {
        if ((this.state.unitProperties || []).length && (this.state.unitsList || []).length) {
            return;
        }
        const data = await this.orm.call("property.unit", "get_units_data", []);
        this.state.unitsList = data.units || [];
        this.state.unitProperties = data.properties || [];
        this.state.unitBuildings = data.buildings || [];
        this.state.unitFloors = data.floors || [];
        this.state.unitTypes = data.types || [];
    }

    async openUnitForm(id) {
        this.state.menuId = null;
        try {
            await this.ensureUnitCatalog();
            const row = (this.state.unitsList || []).find((unit) => unit.id === id);
            if (!row) {
                this.notification.add("Unit not found.", { title: "Edit Unit", type: "warning" });
                return;
            }
            const config = row.config && row.config !== "—" ? row.config : "2 BHK";
            this.state.unitForm = {
                id: row.id,
                name: row.name || "",
                property_id: row.property_id ? String(row.property_id) : "",
                building_id: row.building_id ? String(row.building_id) : "",
                floor_id: row.floor_id ? String(row.floor_id) : "",
                unit_type: config,
                status: row.status || "available",
                area_sqft: row.area_sqft || 0,
            };
            this.state.showUnitForm = true;
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not open the unit.", {
                title: "Edit Unit",
                type: "danger",
            });
        }
    }

    async openUnitDetail(id) {
        this.state.menuId = null;
        const keepTab = this.state.page === "unit-detail" ? this.state.unitTab : "overview";
        this.state.page = "unit-detail";
        this.state.unitTab = keepTab;
        this.state.showUnitAction = false;
        this.state.loadingUnitDetail = true;
        try {
            const data = await this.orm.call("property.unit", "get_unit_detail", [id]);
            this.state.unitDetail = data;
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load unit details.", {
                title: "Unit Details",
                type: "danger",
            });
            this.state.page = "units";
        } finally {
            this.state.loadingUnitDetail = false;
        }
    }

    setUnitTab(tabId) {
        this.state.unitTab = tabId;
    }

    get unitActionTitle() {
        return {
            status: "Change Status",
            tenant: "Add Tenant",
            owner: "Add Owner",
        }[this.state.unitAction.mode] || "Unit";
    }

    openUnitAction(mode) {
        const unit = this.state.unitDetail.unit;
        this.state.unitAction = {
            ...emptyUnitAction(),
            mode,
            status: unit.status || "occupied",
        };
        this.state.showUnitAction = true;
    }

    cancelUnitAction() {
        this.state.showUnitAction = false;
        this.state.unitAction = emptyUnitAction();
    }

    async submitUnitAction() {
        const unitId = this.state.unitDetail.unit.id;
        const form = this.state.unitAction;
        this.state.saving = true;
        try {
            if (form.mode === "status") {
                await this.orm.call("property.unit", "update_status", [unitId, form.status]);
                this.notification.add("Status updated.", { type: "success" });
            } else if (form.mode === "tenant") {
                if (!String(form.name || "").trim()) {
                    this.notification.add("Tenant name is required.", { title: "Add Tenant", type: "warning" });
                    this.state.saving = false;
                    return;
                }
                await this.orm.call("property.unit", "add_tenant", [unitId, {
                    name: form.name,
                    date_start: form.date_start || false,
                }]);
                this.notification.add("Tenant added.", { type: "success" });
            } else if (form.mode === "owner") {
                if (!String(form.name || "").trim()) {
                    this.notification.add("Owner name is required.", { title: "Add Owner", type: "warning" });
                    this.state.saving = false;
                    return;
                }
                await this.orm.call("property.unit", "add_owner", [unitId, {
                    name: form.name,
                    share: form.share,
                }]);
                this.notification.add("Owner assigned.", { type: "success" });
            }
            this.state.showUnitAction = false;
            this.state.unitAction = emptyUnitAction();
            await this.openUnitDetail(unitId);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not save.", {
                title: "Unit Details",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    newUnit() {
        this.state.unitForm = emptyUnitForm();
        if (this.state.unitPropertyFilter !== "all") {
            this.state.unitForm.property_id = this.state.unitPropertyFilter;
        }
        this.state.showUnitForm = true;
        this.state.menuId = null;
    }

    cancelUnitForm() {
        this.state.showUnitForm = false;
        this.state.unitForm = emptyUnitForm();
    }

    onUnitFormProperty(event) {
        this.state.unitForm.property_id = event.target.value;
        this.state.unitForm.building_id = "";
        this.state.unitForm.floor_id = "";
    }

    onUnitFormBuilding(event) {
        this.state.unitForm.building_id = event.target.value;
        this.state.unitForm.floor_id = "";
    }

    async submitUnit() {
        const form = this.state.unitForm;
        if (!String(form.name || "").trim()) {
            this.notification.add("Unit name is required.", { title: "Add Unit", type: "warning" });
            return;
        }
        if (!form.property_id) {
            this.notification.add("Please select a property.", { title: "Add Unit", type: "warning" });
            return;
        }
        const payload = {
            name: form.name,
            property_id: form.property_id,
            building_id: form.building_id,
            floor_id: form.floor_id,
            unit_type: form.unit_type,
            status: form.status,
            area_sqft: form.area_sqft || 0,
        };
        const editing = Boolean(form.id);
        this.state.saving = true;
        try {
            if (editing) {
                await this.orm.call("property.unit", "update_from_dashboard", [{
                    ...payload,
                    id: form.id,
                }]);
                this.notification.add("Unit updated.", { type: "success" });
            } else {
                await this.orm.call("property.unit", "create_from_dashboard", [payload]);
                this.notification.add("Unit created.", { type: "success" });
            }
            const page = this.state.page;
            const unitId = form.id;
            this.state.showUnitForm = false;
            this.state.unitForm = emptyUnitForm();
            const data = await this.orm.call("property.unit", "get_units_data", []);
            this.state.unitsList = data.units || [];
            this.state.unitProperties = data.properties || [];
            this.state.unitBuildings = data.buildings || [];
            this.state.unitFloors = data.floors || [];
            this.state.unitTypes = data.types || [];
            if (page === "unit-detail" && unitId) {
                await this.openUnitDetail(unitId);
            } else if (page === "occupancy") {
                await this.openOccupancy();
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || (editing ? "Could not update the unit." : "Could not create the unit."), {
                title: editing ? "Edit Unit" : "Add Unit",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    async openPropertyForm(id) {
        this.state.menuId = null;
        this.state.detailMenu = false;
        try {
            const data = await this.orm.call("property.property", "get_form_values", [id]);
            this.state.form = {
                ...emptyPropertyForm(),
                ...data,
            };
            this.state.page = "add-property";
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not open the property.", {
                title: "Edit Property",
                type: "danger",
            });
        }
    }

    openProperty(id) {
        this.openPropertyDetail(id);
    }

    async openPropertyDetail(id) {
        this.state.menuId = null;
        this.state.detailMenu = false;
        this.state.page = "property-detail";
        this.state.detailTab = "overview";
        this.state.hierarchyZoom = 1;
        this.state.loadingDetail = true;
        try {
            const data = await this.orm.call("property.property", "get_property_detail", [id]);
            this.state.detail = data;
            const firstBuilding = (data.hierarchy && data.hierarchy.buildings && data.hierarchy.buildings[0]) || null;
            this.state.selectedBuildingId = firstBuilding ? firstBuilding.id : null;
            const bands = firstBuilding && firstBuilding.bands ? firstBuilding.bands : [];
            const mid = bands[Math.min(1, Math.max(0, bands.length - 1))] || bands[0];
            this.state.selectedBandId = mid ? mid.id : null;
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load property details.", {
                title: "Property Details",
                type: "danger",
            });
            this.state.page = "properties";
        } finally {
            this.state.loadingDetail = false;
        }
    }

    setDetailTab(tabId) {
        this.state.detailTab = tabId;
        this.state.detailMenu = false;
    }

    toggleDetailMenu(event) {
        event.stopPropagation();
        this.state.detailMenu = !this.state.detailMenu;
    }

    selectDetailBuilding(buildingId) {
        this.state.selectedBuildingId = buildingId;
        const building = (this.state.detail.hierarchy.buildings || []).find((item) => item.id === buildingId);
        const bands = building && building.bands ? building.bands : [];
        const current = bands.find((band) => band.id === this.state.selectedBandId);
        this.state.selectedBandId = current ? current.id : (bands[0] && bands[0].id) || null;
    }

    selectDetailBand(bandId, event) {
        event.stopPropagation();
        this.state.selectedBandId = bandId;
    }

    zoomHierarchy(delta) {
        this.state.hierarchyZoom = Math.min(1.4, Math.max(0.7, Math.round((this.state.hierarchyZoom + delta) * 10) / 10));
    }

    get selectedDetailBuilding() {
        const buildings = this.state.detail.hierarchy.buildings || [];
        return buildings.find((item) => item.id === this.state.selectedBuildingId) || buildings[0] || null;
    }

    get selectedDetailBand() {
        const building = this.selectedDetailBuilding;
        const bands = (building && building.bands) || [];
        return bands.find((item) => item.id === this.state.selectedBandId) || null;
    }

    newProperty() {
        this.state.form = emptyPropertyForm();
        this.state.page = "add-property";
    }

    cancelAdd() {
        this.state.form = emptyPropertyForm();
        this.state.page = "properties";
    }

    focusAddress() {
        this.streetRef.el?.focus();
    }

    get mapCaption() {
        const parts = [
            this.state.form.street,
            this.state.form.city,
            this.state.form.state_name,
            this.state.form.country,
        ].filter(Boolean);
        return parts.join(", ") || "Add an address to preview location";
    }

    onDocFile(docType, event) {
        const file = event.target.files && event.target.files[0];
        if (!file) {
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const result = String(reader.result || "");
            const data = result.includes(",") ? result.split(",")[1] : result;
            this.state.form.documents[docType] = { name: file.name, data };
        };
        reader.readAsDataURL(file);
    }

    async submitProperty(isDraft) {
        if (this.state.saving) {
            return;
        }
        const form = this.state.form;
        if (!isDraft) {
            const missing = [];
            if (!String(form.name || "").trim()) {
                missing.push("Property Name");
            }
            if (!String(form.code || "").trim()) {
                missing.push("Property Code");
            }
            if (!form.property_type) {
                missing.push("Property Type");
            }
            if (!String(form.street || "").trim()) {
                missing.push("Address Line 1");
            }
            if (!String(form.city || "").trim()) {
                missing.push("City");
            }
            if (!String(form.state_name || "").trim()) {
                missing.push("State / Province");
            }
            if (!String(form.zip || "").trim()) {
                missing.push("Postal Code");
            }
            if (!form.country) {
                missing.push("Country");
            }
            if (missing.length) {
                this.notification.add("Please fill required fields: " + missing.join(", "), {
                    title: "Add Property",
                    type: "warning",
                });
                return;
            }
        } else if (!String(form.name || "").trim()) {
            this.notification.add("Property Name is required.", {
                title: "Add Property",
                type: "warning",
            });
            return;
        }
        this.state.saving = true;
        try {
            const documents = Object.entries(form.documents)
                .filter(([, file]) => file && file.data)
                .map(([type, file]) => ({ type, name: file.name, data: file.data }));
            const payload = {
                name: form.name,
                code: form.code,
                property_type: form.property_type,
                operational_status: form.operational_status,
                description: form.description,
                street: form.street,
                city: form.city,
                state_name: form.state_name,
                zip: form.zip,
                country: form.country,
                planned_buildings: form.planned_buildings,
                planned_floors: form.planned_floors,
                planned_units: form.planned_units,
                category: form.category,
                is_draft: isDraft,
                documents,
            };
            const editing = Boolean(form.id);
            if (editing) {
                await this.orm.call("property.property", "update_from_dashboard", [{ ...payload, id: form.id }]);
            } else {
                await this.orm.call("property.property", "create_from_dashboard", [payload]);
            }
            this.notification.add(isDraft ? "Property saved as draft." : (editing ? "Property updated." : "Property created."), {
                type: "success",
            });
            this.state.form = emptyPropertyForm();
            this.state.hierarchy = [];
            await this.load();
            this.state.page = "properties";
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not save the property.", {
                title: "Add Property",
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    exportCsv() {
        let rows;
        let filename = "property_summary.csv";
        if (this.state.page === "buildings") {
            rows = [["Building", "Code", "Property", "Floors", "Units", "Occupied %", "Status"]];
            for (const row of this.filteredBuildings) {
                rows.push([row.name, row.code, row.property_name, row.floors, row.units, `${row.occupancy}%`, row.status_label]);
            }
            filename = "buildings.csv";
        } else if (this.state.page === "units") {
            rows = [["Unit", "Property", "Building", "Floor/Wing", "Config", "Owner", "Occupancy", "Status"]];
            for (const row of this.filteredUnits) {
                rows.push([row.name, row.property_name, row.building_name, row.floor_wing, row.config, row.owner_name, row.occupancy_label, row.op_status_label]);
            }
            filename = "units.csv";
        } else if (this.state.page === "occupancy") {
            rows = [["Unit", "Property", "Tenant", "Status"]];
            for (const row of this.occupancyDirectory) {
                rows.push([row.name, row.property_name, row.tenant, row.directory_label]);
            }
            filename = "occupancy_report.csv";
        } else if (this.state.page === "ownership") {
            rows = [["Unit", "Building", "Owner", "Type", "Share", "Effective", "Status"]];
            for (const row of this.filteredOwnership) {
                rows.push([row.unit_name, row.building_name, row.owner_name, row.owner_type_label, `${row.share}%`, row.effective_label, row.status_label]);
            }
            filename = "ownership_directory.csv";
        } else if (this.state.page === "tenancy") {
            rows = [["Tenant", "Unit", "Property", "Move In", "Move Out", "Duration", "Status"]];
            for (const row of this.filteredTenancy) {
                rows.push([row.tenant_name, row.unit_name, row.property_name, row.move_in_label, row.move_out_label, row.duration, row.status_label]);
            }
            filename = "tenant_history.csv";
        } else if (this.state.page === "documents") {
            rows = [["Document", "Type", "Associated With", "Uploaded By", "Date", "Version", "Expiry", "Status"]];
            for (const row of this.filteredDocuments) {
                rows.push([row.name, row.category_label, row.associated, row.uploader, row.date_label, row.version, row.expiry_label, row.status_label]);
            }
            filename = "documents.csv";
        } else if (this.state.page === "status") {
            rows = [["Unit", "Property", "Status", "Updated By", "Updated"]];
            for (const row of this.filteredStatusBoard) {
                rows.push([row.name, row.property_name, row.status_label, row.updated_by, row.updated_label]);
            }
            filename = "unit_status.csv";
        } else if (this.state.page === "property_reports") {
            rows = [["Property", "Type", "Location", "Buildings", "Units", "Occupancy", "Status"]];
            for (const row of this.state.reportProperties || []) {
                rows.push([row.name, row.type_label, row.location, row.building_count, row.unit_count, `${row.occupancy}%`, row.status_label]);
            }
            filename = "property_reports.csv";
        } else if (this.state.page === "occupancy_reports") {
            rows = [["Unit", "Property", "Tenant", "Status"]];
            for (const row of this.state.reportOccupancyUnits || []) {
                rows.push([row.name, row.property_name, row.tenant, row.directory_label]);
            }
            filename = "occupancy_reports.csv";
        } else if (this.state.page === "ownership_reports") {
            rows = [["Unit", "Property", "Owner", "Type", "Share", "Effective", "Status"]];
            for (const row of this.state.reportOwnership || []) {
                rows.push([row.unit_name, row.property_name, row.owner_name, row.owner_type_label, `${row.share}%`, row.effective_label, row.status_label]);
            }
            filename = "ownership_reports.csv";
        } else if (this.state.page === "properties") {
            rows = [["Name", "ID", "Type", "Location", "Buildings", "Units", "Occupancy", "Status"]];
            for (const row of this.filteredProperties) {
                rows.push([
                    row.name,
                    row.code,
                    row.type_label,
                    row.location,
                    row.building_count,
                    row.unit_count,
                    `${row.occupancy}%`,
                    row.status_label,
                ]);
            }
            filename = "properties.csv";
        } else {
            rows = [["Name", "Total Units", "Occupied", "Vacant", "Status"]];
            for (const row of this.state.data.summary || []) {
                rows.push([row.name, row.unit_count, row.occupied_count, row.vacant_count, row.health_label]);
            }
        }
        const blob = new Blob([rows.map((line) => line.join(",")).join("\n")], {
            type: "text/csv;charset=utf-8;",
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
    }

    openHelp() {
        this.state.showHelp = true;
    }

    closeHelp() {
        this.state.showHelp = false;
    }

    hierarchyIcon(type) {
        return {
            property: "fa-building",
            building: "fa-university",
            floor: "fa-th-large",
            unit: "fa-home",
        }[type] || "fa-building";
    }

    hierarchyStatusClass(status) {
        return {
            active: "is-h-active",
            full: "is-h-full",
            occupied: "is-h-occupied",
            maintenance: "is-h-maint",
            vacant: "is-h-vacant",
            reserved: "is-h-reserved",
            available: "is-h-vacant",
            draft: "is-draft",
        }[status] || "is-h-vacant";
    }

    _nodeMatches(node, query, status) {
        const textOk = !query || `${node.name} ${node.code}`.toLowerCase().includes(query);
        const statusOk = status === "all" || node.status === status;
        return textOk && statusOk;
    }

    _pruneHierarchy(nodes, query, status) {
        const result = [];
        for (const node of nodes || []) {
            const children = this._pruneHierarchy(node.children || [], query, status);
            if (this._nodeMatches(node, query, status) || children.length) {
                result.push({ ...node, children });
            }
        }
        return result;
    }

    _flattenHierarchy(nodes, depth, forceExpand) {
        const rows = [];
        for (const node of nodes || []) {
            const hasChildren = Boolean(node.children && node.children.length);
            const isExpanded = forceExpand || Boolean(this.state.expanded[node.id]);
            rows.push({ ...node, depth, hasChildren, isExpanded });
            if (hasChildren && isExpanded) {
                rows.push(...this._flattenHierarchy(node.children, depth + 1, forceExpand));
            }
        }
        return rows;
    }

    get filteredHierarchy() {
        const query = (this.state.hierarchySearch || "").trim().toLowerCase();
        const status = this.state.hierarchyStatusFilter || "all";
        return this._pruneHierarchy(this.state.hierarchy || [], query, status);
    }

    get visibleHierarchyRows() {
        const query = (this.state.hierarchySearch || "").trim();
        const forceExpand = Boolean(query) || this.state.hierarchyStatusFilter !== "all";
        return this._flattenHierarchy(this.filteredHierarchy, 0, forceExpand);
    }

    collectExpandableIds(nodes, acc = {}) {
        for (const node of nodes || []) {
            if (node.children && node.children.length) {
                acc[node.id] = true;
                this.collectExpandableIds(node.children, acc);
            }
        }
        return acc;
    }

    async openHierarchy(propertyId) {
        this.state.page = "hierarchy";
        this.state.hierarchySearch = "";
        this.state.hierarchyStatusFilter = "all";
        this.state.showHierarchyFilter = false;
        this.state.menuId = null;
        this.state.loadingHierarchy = true;
        this.state.hierarchy = [];
        this.state.expanded = {};
        try {
            const data = await this.orm.call("property.property", "get_hierarchy_data", []);
            const tree = data.hierarchy || [];
            this.state.hierarchy = tree;
            const expanded = {};
            const focus = propertyId
                ? tree.find((node) => node.resId === propertyId && node.type === "property")
                : tree[0];
            if (focus) {
                expanded[focus.id] = true;
                if (focus.children && focus.children[0]) {
                    expanded[focus.children[0].id] = true;
                }
            }
            this.state.expanded = expanded;
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || "Could not load the hierarchy.", {
                title: "Hierarchy Explorer",
                type: "danger",
            });
        } finally {
            this.state.loadingHierarchy = false;
        }
    }

    onHierarchySearch(event) {
        this.state.hierarchySearch = event.target.value;
    }

    toggleHierarchyFilter() {
        this.state.showHierarchyFilter = !this.state.showHierarchyFilter;
    }

    setHierarchyStatusFilter(status) {
        this.state.hierarchyStatusFilter = status;
        this.state.showHierarchyFilter = false;
    }

    toggleExpand(id, event) {
        event.stopPropagation();
        this.state.expanded[id] = !this.state.expanded[id];
    }

    expandAllHierarchy() {
        this.state.expanded = this.collectExpandableIds(this.filteredHierarchy);
    }

    collapseAllHierarchy() {
        this.state.expanded = {};
    }

    openHierarchyNode(row) {
        if (!row?.resId) {
            return;
        }
        if (row.type === "property") {
            this.openPropertyDetail(row.resId);
            return;
        }
        if (row.type === "building") {
            this.openBuildingDetail(row.resId);
            return;
        }
        if (row.type === "unit") {
            this.openUnitDetail(row.resId);
            return;
        }
        if (row.type === "floor") {
            this.openFloors(row.parentId, row.resId);
        }
    }
}

registry.category("actions").add("property_management.dashboard", PropertyDashboard);
