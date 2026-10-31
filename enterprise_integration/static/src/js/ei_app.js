/** @odoo-module **/

import { Component, onMounted, onPatched, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const SCREENS = [
    {
        id: "dashboard",
        label: "Dashboard",
        icon: "fa-th-large",
        title: "Enterprise Integration",
        subtitle: "Real-time overview of system connectivity and synchronization.",
        crumb: "Dashboard",
        searchPlaceholder: "Search integrations…",
    },
    {
        id: "api",
        label: "API & Webhooks",
        icon: "fa-plug",
        title: "API & Webhook Management",
        subtitle: "Manage Open API endpoints, webhooks, keys and delivery history.",
        crumb: "APIs & Webhooks",
        searchPlaceholder: "Search APIs, webhooks, keys…",
    },
    {
        id: "connectors",
        label: "Connectors",
        icon: "fa-sitemap",
        title: "Enterprise Connectors",
        subtitle: "Manage and monitor external system integrations.",
        crumb: "Connectors",
        searchPlaceholder: "Search connectors…",
    },
    {
        id: "sync",
        label: "Data Sync",
        icon: "fa-refresh",
        title: "Data Synchronization",
        subtitle: "Manage and monitor enterprise data flow across systems.",
        crumb: "Synchronization",
        searchPlaceholder: "Search sync jobs…",
    },
    {
        id: "master",
        label: "Master Data",
        icon: "fa-database",
        title: "Master Data Integration",
        subtitle: "Source-of-truth mappings and conflict resolution across entity types.",
        crumb: "Master Data",
        searchPlaceholder: "Search master mappings…",
    },
    {
        id: "monitoring",
        label: "Monitoring",
        icon: "fa-line-chart",
        title: "Integration Monitoring & Logs",
        subtitle: "Real-time performance and error tracking across all enterprise connections.",
        crumb: "Monitoring",
        searchPlaceholder: "Search logs by name or correlation…",
    },
];

const MASTER_TABS = [
    { id: "customer", label: "Customer" },
    { id: "supplier", label: "Supplier" },
    { id: "product", label: "Product" },
    { id: "employee", label: "Employee" },
    { id: "account", label: "Account" },
    { id: "site_location", label: "Site / Location" },
    { id: "department", label: "Department" },
];

/** Demo record counts (Stitch mockup) — used when ORM field is unavailable. */
const DEMO_MASTER_RECORD_COUNTS = {
    "B2B Customers": 12450,
    "Retail Customers": 45102,
    "Internal Accounts": 340,
    "Preferred Vendors": 820,
    "Catalog Products": 5600,
};

/** Demo sync jobs when DB has none — matches Data Sync mockup. */
const DEMO_SYNC_JOBS = [
    {
        id: -101,
        name: "Customer Sync",
        entity_name: "res.partner",
        source_system: "ERP",
        dest_system: "CRM",
        direction: "one_way",
        trigger: "realtime",
        frequency: "manual",
        conflict_policy: "source_wins",
        state: "active",
        active: true,
        last_success_at: null,
        last_run_state: "completed",
        _demo: true,
        _last_records: 842,
        _last_failed: 0,
        _progress: 0,
        _mapping_count: 24,
        _last_ago: "10 mins ago",
    },
    {
        id: -102,
        name: "Product Sync",
        entity_name: "product.template",
        source_system: "PIM",
        dest_system: "ERP",
        direction: "two_way",
        trigger: "scheduled",
        frequency: "hourly",
        conflict_policy: "source_wins",
        state: "active",
        active: true,
        last_success_at: null,
        last_run_state: "running",
        _demo: true,
        _last_records: 1204,
        _last_failed: 0,
        _progress: 78,
        _mapping_count: 31,
        _last_ago: "In progress",
    },
    {
        id: -103,
        name: "Payment Sync",
        entity_name: "account.payment",
        source_system: "ERP",
        dest_system: "Gateway",
        direction: "one_way",
        trigger: "scheduled",
        frequency: "daily",
        conflict_policy: "manual",
        state: "active",
        active: true,
        last_success_at: null,
        last_run_state: "partial",
        _demo: true,
        _last_records: 310,
        _last_failed: 12,
        _progress: 0,
        _mapping_count: 18,
        _last_ago: "1 hour ago",
    },
];

const DEMO_SYNC_RUNS = [
    {
        id: -201,
        name: "Sync job started manually by Admin",
        state: "running",
        create_date: null,
        records_processed: 0,
        records_failed: 0,
        error_message: "",
        _demo: true,
        _time: "10:42 AM",
    },
    {
        id: -202,
        name: "Customer Sync completed successfully",
        state: "completed",
        create_date: null,
        records_processed: 842,
        records_failed: 0,
        error_message: "842 records processed",
        _demo: true,
        _time: "10:41 AM",
    },
    {
        id: -203,
        name: "Failed to map field 'transaction_id' for 12 records",
        state: "failed",
        create_date: null,
        records_processed: 310,
        records_failed: 12,
        error_message: "Partial failure on Payment Sync",
        _demo: true,
        _time: "09:15 AM",
    },
];

/** Demo monitoring logs when DB has none — matches Monitoring mockup. */
const DEMO_MONITOR_LOGS = [
    {
        id: -301,
        name: "Production_Order_Sync",
        category: "sync",
        level: "failed",
        create_date: null,
        correlation_id: "req_8f72a1b9-4c3a-4b21-99ee-5d8a9c8b1234",
        operation: "POST /api/v1/erp/production-orders",
        source_system: "SAP ERP",
        duration_ms: 1204,
        error_message:
            "Connection timeout occurred while attempting to establish socket connection to SAP_PROD_BAPI. Remote host unreachable.",
        request_summary: `{
  "sync_id": "batch_992",
  "timestamp": "2023-10-27T10:42:14Z",
  "data_type": "production_order",
  "payload": [
    {
      "order_id": "PO-2023-9912",
      "plant": "PL01",
      "material": "MAT-PC-WALL-A"
    }
  ]
}`,
        response_summary: "HTTP/1.1 500 Internal Server Error\nContent-Type: application/json\nX-Request-Id: req_8f72a1b9",
        retryable: true,
        _demo: true,
        _time: "10:42:15 AM",
        _http_status: 500,
        _endpoint: "/api/v1/erp/production-orders",
        _method: "POST",
    },
    {
        id: -302,
        name: "Inventory_Level_Update",
        category: "api",
        level: "success",
        create_date: null,
        correlation_id: "req_a1b2c3d4",
        operation: "PUT /api/v1/wms/inventory",
        source_system: "WMS",
        duration_ms: 145,
        error_message: "",
        request_summary: '{\n  "sku": "MAT-PC-WALL-A",\n  "qty": 240\n}',
        response_summary: "HTTP/1.1 200 OK",
        retryable: false,
        _demo: true,
        _time: "10:41:02 AM",
        _http_status: 200,
        _endpoint: "/api/v1/wms/inventory",
        _method: "PUT",
    },
    {
        id: -303,
        name: "Customer_Webhook_Push",
        category: "webhook",
        level: "warning",
        create_date: null,
        correlation_id: "req_wh_9981",
        operation: "POST /hooks/crm/customer",
        source_system: "CRM",
        duration_ms: 890,
        error_message: "Delivery succeeded after 1 retry.",
        request_summary: '{\n  "partner_id": 4412,\n  "event": "updated"\n}',
        response_summary: "HTTP/1.1 202 Accepted",
        retryable: true,
        _demo: true,
        _time: "10:38:44 AM",
        _http_status: 202,
        _endpoint: "/hooks/crm/customer",
        _method: "POST",
    },
    {
        id: -304,
        name: "Bank_Statement_Fetch",
        category: "connector",
        level: "success",
        create_date: null,
        correlation_id: "req_bnk_441",
        operation: "GET statements",
        source_system: "Banking",
        duration_ms: 312,
        error_message: "",
        request_summary: '{\n  "account": "****4521",\n  "from": "2023-10-26"\n}',
        response_summary: "HTTP/1.1 200 OK — 18 statements",
        retryable: false,
        _demo: true,
        _time: "10:35:10 AM",
        _http_status: 200,
        _endpoint: "/connector/bank/statements",
        _method: "GET",
    },
    {
        id: -305,
        name: "Nightly_Master_Reconcile",
        category: "master_data",
        level: "success",
        create_date: null,
        correlation_id: "req_sched_77",
        operation: "reconcile",
        source_system: "Internal Scheduler",
        duration_ms: 4200,
        error_message: "",
        request_summary: '{\n  "entities": ["customer", "product"]\n}',
        response_summary: "Reconciled 1,204 mappings",
        retryable: false,
        _demo: true,
        _time: "10:30:00 AM",
        _http_status: 200,
        _endpoint: "/internal/master/reconcile",
        _method: "POST",
    },
];

const DEMO_MONITOR_KPIS = {
    total: 18842,
    success: 18214,
    failed: 628,
    successRate: 96.6,
    failRate: 3.4,
    avg: 284,
    avgTrend: -12,
    webhookFail: 18,
    syncFail: 12,
    connectorErr: 6,
    availability: 99.9,
};

/** Demo connectors when DB has none — matches Connectors mockup. */
const DEMO_CONNECTORS = [
    {
        id: -401,
        name: "ERP System",
        category: "erp",
        state: "connected",
        health_state: "healthy",
        is_mock: true,
        last_health_at: null,
        version: "2.1.4",
        auth_method: "oauth",
        base_url: "https://api.erp-system.internal/v2/",
        _demo: true,
        _last_ago: "2 mins ago",
        _system_type: "Odoo ERP",
        _health_level: 5,
        _category_label: "Enterprise Resource",
    },
    {
        id: -402,
        name: "CRM System",
        category: "crm",
        state: "connected",
        health_state: "healthy",
        is_mock: true,
        last_health_at: null,
        version: "1.8.0",
        auth_method: "oauth",
        base_url: "https://api.crm.example.com/v1/",
        _demo: true,
        _last_ago: "8 mins ago",
        _system_type: "Salesforce CRM",
        _health_level: 5,
        _category_label: "Customer Relation",
    },
    {
        id: -403,
        name: "Bank Gateway",
        category: "bank",
        state: "error",
        health_state: "down",
        is_mock: true,
        last_health_at: null,
        version: "3.0.1",
        auth_method: "certificate",
        base_url: "https://bank-gateway.internal/api/",
        _demo: true,
        _last_ago: "1 hr ago",
        _system_type: "Banking API",
        _health_level: 1,
        _category_label: "Banking",
    },
    {
        id: -404,
        name: "WhatsApp Business",
        category: "whatsapp",
        state: "connected",
        health_state: "healthy",
        is_mock: true,
        last_health_at: null,
        version: "2.0",
        auth_method: "api_key",
        base_url: "https://graph.facebook.com/v18.0/",
        _demo: true,
        _last_ago: "15 mins ago",
        _system_type: "Meta WhatsApp",
        _health_level: 4,
        _category_label: "Messaging",
    },
    {
        id: -405,
        name: "Legacy AS/400",
        category: "legacy",
        state: "disconnected",
        health_state: "degraded",
        is_mock: true,
        last_health_at: null,
        version: "1.0",
        auth_method: "basic",
        base_url: "sftp://legacy.internal/export/",
        _demo: true,
        _last_ago: "3 hrs ago",
        _system_type: "Legacy Host",
        _health_level: 2,
        _category_label: "Legacy",
    },
];

const DEMO_CONNECTOR_MAPPINGS = {
    [-401]: [
        { id: -501, source_field: "order_id", target_field: "Ext_Ref", name: "Order Ref" },
        { id: -502, source_field: "qty_planned", target_field: "Volume", name: "Quantity" },
        { id: -503, source_field: "plant_code", target_field: "Plant", name: "Plant" },
    ],
    [-402]: [
        { id: -504, source_field: "partner_id", target_field: "AccountId", name: "Account" },
        { id: -505, source_field: "email", target_field: "Email", name: "Email" },
    ],
    [-403]: [
        { id: -506, source_field: "payment_ref", target_field: "TxnId", name: "Txn" },
    ],
};

const DEMO_CONNECTOR_KPIS = {
    total: 32,
    connected: 24,
    connectedDelta: 2,
    disconnected: 3,
    error: 2,
    pending: 3,
};

/** Demo API endpoints when DB has none — matches APIs & Webhooks mockup. */
const DEMO_API_ENDPOINTS = [
    {
        id: -601,
        name: "Customer API",
        path: "/customers",
        method: "GET",
        auth_type: "oauth",
        state: "active",
        usage_count: 1240,
        version: "1.0",
        rate_limit: 100,
        _demo: true,
        _burst: 200,
        _scopes: ["read:customers", "write:customers"],
        _full_url: "https://api.precastmps.internal/ei/api/v1/customers",
    },
    {
        id: -602,
        name: "Order Create",
        path: "/orders",
        method: "POST",
        auth_type: "api_key",
        state: "active",
        usage_count: 842,
        version: "1.0",
        rate_limit: 60,
        _demo: true,
        _burst: 120,
        _scopes: ["write:orders"],
        _full_url: "https://api.precastmps.internal/ei/api/v1/orders",
    },
    {
        id: -603,
        name: "Inventory Sync",
        path: "/inventory/{sku}",
        method: "PUT",
        auth_type: "both",
        state: "active",
        usage_count: 510,
        version: "1.1",
        rate_limit: 120,
        _demo: true,
        _burst: 240,
        _scopes: ["read:inventory", "write:inventory"],
        _full_url: "https://api.precastmps.internal/ei/api/v1/inventory/{sku}",
    },
    {
        id: -604,
        name: "Legacy Partner Feed",
        path: "/partners/legacy",
        method: "GET",
        auth_type: "api_key",
        state: "deprecated",
        usage_count: 12,
        version: "0.9",
        rate_limit: 30,
        _demo: true,
        _burst: 60,
        _scopes: ["read:partners"],
        _full_url: "https://api.precastmps.internal/ei/api/v1/partners/legacy",
    },
];

const DEMO_API_WEBHOOKS = [
    {
        id: -611,
        name: "CRM Customer Push",
        code: "crm_customer_push",
        direction: "outbound",
        auth_type: "api_key",
        state: "active",
        _demo: true,
    },
    {
        id: -612,
        name: "WMS Stock Inbound",
        code: "wms_stock_in",
        direction: "inbound",
        auth_type: "oauth",
        state: "active",
        _demo: true,
    },
];

const DEMO_API_KEYS = [
    {
        id: -621,
        name: "Production Service Key",
        key_prefix: "ei_live_••••",
        state: "active",
        last_used_at: null,
        expiry_date: false,
        _demo: true,
        _last_ago: "2 mins ago",
    },
    {
        id: -622,
        name: "Staging Integration",
        key_prefix: "ei_test_••••",
        state: "active",
        last_used_at: null,
        expiry_date: "2026-12-31",
        _demo: true,
        _last_ago: "1 hr ago",
    },
];

const DEMO_API_DELIVERIES = [
    {
        id: -631,
        name: "CRM Customer Push #9912",
        status: "delivered",
        http_status: 200,
        correlation_id: "dlv_8f72a1",
        create_date: null,
        _demo: true,
        _when: "10:42 AM",
    },
    {
        id: -632,
        name: "WMS Stock Inbound #4401",
        status: "failed",
        http_status: 500,
        correlation_id: "dlv_a1b2c3",
        create_date: null,
        _demo: true,
        _when: "10:38 AM",
    },
];

const DEMO_API_KPIS = {
    activeEndpoints: 48,
    apiRequests: 12480,
    activeWebhooks: 26,
    delivered: 3218,
    failedEvents: 18,
    apiErrors: 12,
};

/** Demo dashboard payload when DB is empty — matches Enterprise Integration mockup. */
const DEMO_DASHBOARD = {
    kpis: {
        activeIntegrations: 24,
        connectedConnectors: 18,
        failedOps: 16,
        syncSuccess: 1842,
        syncPending: 64,
        syncConflicts: 28,
    },
    health: { healthy: 18, warning: 3, disconnected: 2, error: 1 },
    sync: { running: 6, failed: 28, pending: 64, conflicts: 28 },
    api: {
        requests: 12400,
        success: 12000,
        failed: 12,
        webhookDeliveries: 3200,
        webhookFailed: 4,
    },
    connectors: [
        {
            id: -701,
            name: "SAP ERP",
            category: "erp",
            state: "connected",
            health_state: "healthy",
            is_mock: true,
            last_health_at: null,
            _last_ago: "2 mins ago",
            _health_pct: 100,
        },
        {
            id: -702,
            name: "Salesforce",
            category: "crm",
            state: "connected",
            health_state: "healthy",
            is_mock: true,
            last_health_at: null,
            _last_ago: "5 mins ago",
            _health_pct: 96,
        },
        {
            id: -703,
            name: "Citibank API",
            category: "bank",
            state: "error",
            health_state: "down",
            is_mock: true,
            last_health_at: null,
            _last_ago: "1 hr ago",
            _health_pct: 22,
        },
        {
            id: -704,
            name: "WhatsApp Biz",
            category: "whatsapp",
            state: "connected",
            health_state: "degraded",
            is_mock: true,
            last_health_at: null,
            _last_ago: "12 mins ago",
            _health_pct: 68,
        },
    ],
    recentLogs: [
        {
            id: -711,
            name: "Customer Sync",
            category: "sync",
            level: "success",
            create_date: null,
            correlation_id: "act_9912",
            operation: "Scheduled Pull",
            source_system: "SAP ERP",
            retryable: false,
            _time: "10:42 AM",
            _records: "842/842",
        },
        {
            id: -712,
            name: "Payment Recon",
            category: "connector",
            level: "failed",
            create_date: null,
            correlation_id: "act_4401",
            operation: "Scheduled Pull",
            source_system: "Citibank API",
            retryable: true,
            _time: "10:15 AM",
            _records: "Timeout (504)",
            _records_danger: true,
        },
        {
            id: -713,
            name: "CRM Webhook Push",
            category: "webhook",
            level: "success",
            create_date: null,
            correlation_id: "act_8821",
            operation: "Event Delivery",
            source_system: "Salesforce",
            retryable: false,
            _time: "10:08 AM",
            _records: "24/24",
        },
        {
            id: -714,
            name: "Inventory Update",
            category: "api",
            level: "warning",
            create_date: null,
            correlation_id: "act_2209",
            operation: "API Request",
            source_system: "WMS",
            retryable: true,
            _time: "09:55 AM",
            _records: "118/120",
        },
    ],
};

const PIPELINE_STAGES = {
    external: {
        id: "external",
        label: "External system",
        screen: "connectors",
        hint: "Source systems / connectors",
    },
    api_webhook: {
        id: "api_webhook",
        label: "API/Webhook",
        screen: "api",
        hint: "Ingest via Open API or webhooks",
    },
    validate: {
        id: "validate",
        label: "Validate",
        screen: "monitoring",
        hint: "Payload validation (pipeline_validate)",
    },
    transform: {
        id: "transform",
        label: "Transform",
        screen: "sync",
        hint: "Field mapping + transforms",
    },
    sync: {
        id: "sync",
        label: "Sync",
        screen: "sync",
        hint: "Apply records to destination",
    },
    log: {
        id: "log",
        label: "Log",
        screen: "monitoring",
        hint: "ei.log audit trail",
    },
    monitor: {
        id: "monitor",
        label: "Monitor",
        screen: "monitoring",
        hint: "Health and failed operations",
    },
};

/** Exact diagram rows: External -> API/Webhook -> Validate -> Transform -> Sync -> Log -> Monitor */
const PIPELINE_ROWS = [
    [{ id: "external", arrow: true }],
    [{ id: "api_webhook", arrow: true }],
    [
        { id: "validate", arrow: true },
        { id: "transform", arrow: true },
    ],
    [
        { id: "sync", arrow: true },
        { id: "log", arrow: true },
        { id: "monitor", arrow: false },
    ],
];

function emptyKpis() {
    return {
        activeIntegrations: 0,
        connectedConnectors: 0,
        failedOps: 0,
        syncSuccess: 0,
        syncPending: 0,
        syncConflicts: 0,
    };
}

export class EiApp extends Component {
    static template = "enterprise_integration.App";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.rootRef = useRef("root");

        this.screens = SCREENS;
        this.masterTabs = MASTER_TABS;
        this.pipelineStages = PIPELINE_STAGES;
        this.pipelineRows = PIPELINE_ROWS;

        const initialScreen =
            this.props.action?.context?.ei_screen ||
            this.props.action?.params?.screen ||
            "dashboard";

        this.state = useState({
            screen: initialScreen,
            loading: true,
            error: null,
            search: "",
            apiTab: "apis",
            apiPanelSearch: "",
            connectorTab: "all",
            syncTab: "jobs",
            masterTab: "customer",
            masterStatusFilter: "all",
            selectedEndpointId: null,
            selectedConnectorId: null,
            selectedSyncId: null,
            selectedMappingId: null,
            selectedLogId: null,
            kpis: emptyKpis(),
            pipeline: {
                external: 0,
                api_webhook: 0,
                validate: 0,
                validateFailed: 0,
                transform: 0,
                transformFailed: 0,
                sync: 0,
                syncFailed: 0,
                log: 0,
                monitorFailed: 0,
            },
            health: { healthy: 0, warning: 0, disconnected: 0, error: 0 },
            sync: { running: 0, failed: 0, pending: 0, conflicts: 0 },
            api: {
                requests: 0,
                success: 0,
                failed: 0,
                webhookDeliveries: 0,
                webhookFailed: 0,
            },
            apiKpis: {
                activeEndpoints: 0,
                apiRequests: 0,
                activeWebhooks: 0,
                delivered: 0,
                failedEvents: 0,
                apiErrors: 0,
            },
            connectorKpis: {
                total: 0,
                connected: 0,
                connectedDelta: 0,
                disconnected: 0,
                error: 0,
                pending: 0,
            },
            syncKpis: {
                jobsTotal: 0,
                running: 0,
                completed: 0,
                failed: 0,
                pending: 0,
                processed: 0,
            },
            masterKpis: {
                entities: 0,
                synced: 0,
                pending: 0,
                conflicts: 0,
                failed: 0,
                lastSync: false,
            },
            monitorKpis: {
                total: 0,
                success: 0,
                failed: 0,
                successRate: 0,
                failRate: 0,
                avg: 0,
                avgTrend: 0,
                webhookFail: 0,
                syncFail: 0,
                connectorErr: 0,
                availability: 0,
            },
            connectors: [],
            recentLogs: [],
            endpoints: [],
            webhooks: [],
            apiKeys: [],
            deliveries: [],
            syncJobs: [],
            syncRuns: [],
            syncFailedRecords: 0,
            masterEntities: [],
            masterMappings: [],
            masterConflicts: [],
            monitorLogs: [],
            connectorMappings: [],
            filterSystem: "all",
            filterType: "all",
            filterSeverity: "all",
            monitorPayloadOpen: true,
            monitorHeadersOpen: false,
        });

        onWillStart(async () => {
            await this.loadData();
        });
        onMounted(() => this._applyFullScreenLayout());
        onPatched(() => {
            if (this._layoutRaf) {
                return;
            }
            this._layoutRaf = requestAnimationFrame(() => {
                this._layoutRaf = null;
                this._applyFullScreenLayout();
            });
        });
    }

    /**
     * Force the OWL root to fill Odoo's action manager side-by-side.
     * CSS alone can lose to Odoo wrappers; inline styles guarantee layout.
     */
    _applyFullScreenLayout() {
        const el = this.rootRef.el;
        if (!el) {
            return;
        }
        Object.assign(el.style, {
            display: "grid",
            gridTemplateColumns: "248px minmax(0, 1fr)",
            gridTemplateRows: "minmax(0, 1fr)",
            position: "absolute",
            inset: "0",
            width: "100%",
            height: "100%",
            margin: "0",
            overflow: "hidden",
            boxSizing: "border-box",
        });
        let node = el.parentElement;
        while (node && node !== document.body) {
            node.style.minHeight = "0";
            if (
                node.classList.contains("o_action_manager") ||
                node.classList.contains("o_content") ||
                node === el.parentElement
            ) {
                node.classList.add("ei-action-host");
                node.style.position = "relative";
                node.style.height = "100%";
                node.style.flex = "1 1 auto";
                node.style.overflow = "hidden";
            }
            if (node.classList.contains("o_action_manager")) {
                break;
            }
            node = node.parentElement;
        }
    }

    // -------------------------------------------------------------------------
    // Getters
    // -------------------------------------------------------------------------

    get current() {
        return this.screens.find((s) => s.id === this.state.screen) || this.screens[0];
    }

    get selectedEndpoint() {
        return this.state.endpoints.find((e) => e.id === this.state.selectedEndpointId) || null;
    }

    get selectedConnector() {
        return this.state.connectors.find((c) => c.id === this.state.selectedConnectorId) || null;
    }

    get selectedSyncJob() {
        return this.state.syncJobs.find((j) => j.id === this.state.selectedSyncId) || null;
    }

    get recentSyncRuns() {
        return (this.state.syncRuns || []).slice(0, 8);
    }

    get selectedMapping() {
        return this.state.masterMappings.find((m) => m.id === this.state.selectedMappingId) || null;
    }

    get selectedLog() {
        const pools = [this.state.monitorLogs, this.state.recentLogs];
        for (const pool of pools) {
            const found = pool.find((l) => l.id === this.state.selectedLogId);
            if (found) {
                return found;
            }
        }
        return null;
    }

    get filteredEndpoints() {
        let rows = this._filterBySearch(this.state.endpoints, ["name", "path", "method"]);
        const q = (this.state.apiPanelSearch || "").trim().toLowerCase();
        if (q) {
            rows = rows.filter((ep) =>
                ["name", "path", "method", "auth_type"].some((f) =>
                    String(ep[f] || "")
                        .toLowerCase()
                        .includes(q)
                )
            );
        }
        return rows;
    }

    get filteredWebhooks() {
        return this._filterBySearch(this.state.webhooks, ["name", "code", "direction"]);
    }

    get filteredApiKeys() {
        return this._filterBySearch(this.state.apiKeys, ["name", "key_prefix"]);
    }

    get filteredDeliveries() {
        return this._filterBySearch(this.state.deliveries, ["name", "correlation_id", "status"]);
    }

    get filteredConnectors() {
        let rows = this.state.connectors;
        if (this.state.connectorTab && this.state.connectorTab !== "all") {
            rows = rows.filter((c) => c.category === this.state.connectorTab);
        }
        return this._filterBySearch(rows, ["name", "category", "state"]);
    }

    get filteredSyncJobs() {
        let rows = this.state.syncJobs;
        if (this.state.syncTab === "running") {
            rows = rows.filter((j) => (j.last_run_state || j.state) === "running");
        } else if (this.state.syncTab === "failed") {
            rows = rows.filter(
                (j) =>
                    (j.last_run_state || "") === "failed" ||
                    (j.last_run_state || "") === "partial" ||
                    (j._last_failed || 0) > 0
            );
        } else if (this.state.syncTab === "jobs") {
            rows = rows.filter((j) => j.state === "active" || j.active);
        }
        return this._filterBySearch(rows, ["name", "entity_name", "source_system", "dest_system"]);
    }

    get filteredMasterMappings() {
        const code = this.state.masterTab;
        const entityIds = new Set(
            this.state.masterEntities.filter((e) => e.code === code).map((e) => e.id)
        );
        let rows = this.state.masterMappings;
        if (entityIds.size) {
            rows = rows.filter((m) => {
                const eid = Array.isArray(m.entity_id) ? m.entity_id[0] : m.entity_id;
                return entityIds.has(eid);
            });
        } else {
            rows = [];
        }
        if (this.state.masterStatusFilter && this.state.masterStatusFilter !== "all") {
            rows = rows.filter((m) => m.state === this.state.masterStatusFilter);
        }
        return this._filterBySearch(rows, ["name", "source_system", "owner", "state"]);
    }

    get filteredMonitorLogs() {
        let rows = this.state.monitorLogs;
        if (this.state.filterSystem && this.state.filterSystem !== "all") {
            rows = rows.filter((l) => (l.source_system || "") === this.state.filterSystem);
        }
        if (this.state.filterType && this.state.filterType !== "all") {
            rows = rows.filter((l) => l.category === this.state.filterType);
        }
        if (this.state.filterSeverity && this.state.filterSeverity !== "all") {
            rows = rows.filter((l) => l.level === this.state.filterSeverity);
        }
        return this._filterBySearch(rows, ["name", "correlation_id", "operation", "source_system"]);
    }

    get monitorSystems() {
        const set = new Set();
        for (const log of this.state.monitorLogs) {
            if (log.source_system) {
                set.add(log.source_system);
            }
        }
        return [...set].sort();
    }

    // -------------------------------------------------------------------------
    // Navigation / search / refresh
    // -------------------------------------------------------------------------

    async onNavClick(ev) {
        const screen = ev.currentTarget.dataset.screen;
        if (!screen || screen === this.state.screen) {
            return;
        }
        this.state.screen = screen;
        this.state.search = "";
        this.state.error = null;
        this.state.selectedEndpointId = null;
        this.state.selectedConnectorId = null;
        this.state.selectedSyncId = null;
        this.state.selectedMappingId = null;
        this.state.selectedLogId = null;
        this.state.connectorMappings = [];
        this.state.masterConflicts = [];
        await this.loadData();
    }

    async onPipelineClick(ev) {
        await this.onNavClick(ev);
    }

    pipelineStage(stageId) {
        return this.pipelineStages[stageId] || { label: stageId, screen: "dashboard", hint: "" };
    }

    pipelineCount(stageId) {
        const p = this.state.pipeline || {};
        const map = {
            external: p.external,
            api_webhook: p.api_webhook,
            validate: p.validate,
            transform: p.transform,
            sync: p.sync,
            log: p.log,
            monitor: p.monitorFailed,
        };
        return map[stageId] || 0;
    }

    stageTone(stageId) {
        const p = this.state.pipeline || {};
        if (stageId === "validate" && p.validateFailed) {
            return "danger";
        }
        if (stageId === "transform" && p.transformFailed) {
            return "danger";
        }
        if (stageId === "sync" && p.syncFailed) {
            return "danger";
        }
        if (stageId === "monitor" && p.monitorFailed) {
            return "warn";
        }
        if (this.pipelineCount(stageId) > 0) {
            return "ok";
        }
        return "idle";
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value || "";
    }

    async refresh() {
        await this.loadData();
    }

    openCreate() {
        const map = {
            dashboard: "enterprise_integration.action_ei_api_webhook_backend",
            api: "enterprise_integration.action_ei_api_webhook_backend",
            connectors: "enterprise_integration.action_ei_connectors_backend",
            sync: "enterprise_integration.action_ei_sync_backend",
            master: "enterprise_integration.action_ei_master_backend",
            monitoring: "enterprise_integration.action_ei_monitoring_backend",
        };
        const xmlid = map[this.state.screen] || map.dashboard;
        this.action.doAction(xmlid).catch(() => {
            const models = {
                dashboard: "ei.integration",
                api: "ei.api.endpoint",
                connectors: "ei.connector",
                sync: "ei.sync.job",
                master: "ei.master.mapping",
                monitoring: "ei.log",
            };
            this._openForm(models[this.state.screen] || "ei.integration");
        });
    }

    // -------------------------------------------------------------------------
    // Tabs
    // -------------------------------------------------------------------------

    setApiTab(ev) {
        this.state.apiTab = ev.currentTarget.dataset.tab || "apis";
        this.state.apiPanelSearch = "";
    }

    onApiPanelSearch(ev) {
        this.state.apiPanelSearch = ev.target.value || "";
    }

    async setConnectorTab(ev) {
        this.state.connectorTab = ev.currentTarget.dataset.tab || "all";
        this.state.selectedConnectorId = null;
        this.state.connectorMappings = [];
        const rows = this.filteredConnectors;
        if (rows.length) {
            await this.selectConnector({
                currentTarget: { dataset: { id: String(rows[0].id) } },
            });
        }
    }

    setSyncTab(ev) {
        this.state.syncTab = ev.currentTarget.dataset.tab || "jobs";
    }

    async setMasterTab(ev) {
        this.state.masterTab = ev.currentTarget.dataset.tab || "customer";
        this.state.masterStatusFilter = "all";
        await this._selectFirstMasterMapping();
    }

    onMasterStatusFilter(ev) {
        this.state.masterStatusFilter = ev.target.value || "all";
        this._selectFirstMasterMapping();
    }

    // -------------------------------------------------------------------------
    // Selection
    // -------------------------------------------------------------------------

    selectEndpoint(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        this.state.selectedEndpointId = Number.isFinite(id) ? id : null;
    }

    closeEndpointDetail() {
        this.state.selectedEndpointId = null;
    }

    async selectConnector(ev) {
        const raw = ev.currentTarget && ev.currentTarget.dataset
            ? ev.currentTarget.dataset.id
            : null;
        const id = Number(raw);
        this.state.selectedConnectorId = Number.isFinite(id) ? id : null;
        this.state.connectorMappings = [];
        if (!Number.isFinite(id)) {
            return;
        }
        if (id < 0) {
            this.state.connectorMappings = (DEMO_CONNECTOR_MAPPINGS[id] || []).map((m) => ({ ...m }));
            return;
        }
        try {
            this.state.connectorMappings = await this.orm.searchRead(
                "ei.connector.mapping",
                [["connector_id", "=", id]],
                ["source_field", "target_field", "name"],
                { limit: 40, order: "sequence, id" }
            );
        } catch (err) {
            this._notifyError(err, "Failed to load connector mappings.");
        }
    }

    closeConnectorDetail() {
        this.state.selectedConnectorId = null;
        this.state.connectorMappings = [];
    }

    selectSyncJob(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        this.state.selectedSyncId = id || null;
    }

    async selectMapping(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        this.state.selectedMappingId = id || null;
        this.state.masterConflicts = [];
        if (!id) {
            return;
        }
        try {
            this.state.masterConflicts = await this.orm.searchRead(
                "ei.master.conflict",
                [["mapping_id", "=", id], ["state", "=", "conflict"]],
                ["name", "left_payload", "right_payload", "state", "external_ref"],
                { limit: 20, order: "create_date desc" }
            );
        } catch (err) {
            this._notifyError(err, "Failed to load conflicts.");
        }
    }

    async _selectFirstMasterMapping() {
        const rows = this.filteredMasterMappings;
        if (!rows.length) {
            this.state.selectedMappingId = null;
            this.state.masterConflicts = [];
            return;
        }
        const current = rows.find((m) => m.id === this.state.selectedMappingId);
        const target = current || rows[0];
        await this.selectMapping({
            currentTarget: { dataset: { id: String(target.id) } },
        });
    }

    selectLog(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        this.state.selectedLogId = Number.isFinite(id) ? id : null;
        this.state.monitorPayloadOpen = true;
        this.state.monitorHeadersOpen = false;
    }

    closeLogDetail() {
        this.state.selectedLogId = null;
    }

    toggleMonitorPayload() {
        this.state.monitorPayloadOpen = !this.state.monitorPayloadOpen;
    }

    toggleMonitorHeaders() {
        this.state.monitorHeadersOpen = !this.state.monitorHeadersOpen;
    }

    // -------------------------------------------------------------------------
    // Open / actions
    // -------------------------------------------------------------------------

    onOpenEndpoint(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id) || this.state.selectedEndpointId;
        if (!id || id < 0) {
            this.notification.add("Demo API — create a real endpoint to edit.", { type: "info" });
            return;
        }
        this._openForm("ei.api.endpoint", id);
    }

    async onCopyEndpointUrl() {
        const ep = this.selectedEndpoint;
        if (!ep) {
            return;
        }
        const text = this.endpointFullUrl(ep);
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(text);
            } else {
                const ta = document.createElement("textarea");
                ta.value = text;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand("copy");
                document.body.removeChild(ta);
            }
            this.notification.add("Endpoint URL copied.", { type: "info" });
        } catch (err) {
            this._notifyError(err, "Copy failed.");
        }
    }

    endpointFullUrl(ep) {
        if (!ep) {
            return "";
        }
        if (ep._full_url) {
            return ep._full_url;
        }
        const path = String(ep.path || "");
        if (path.startsWith("http")) {
            return path;
        }
        const version = ep.version || "v1";
        const clean = path.startsWith("/") ? path : `/${path}`;
        return `/ei/api/${version}${clean}`;
    }

    endpointBurst(ep) {
        if (!ep) {
            return 0;
        }
        if (ep._burst != null) {
            return ep._burst;
        }
        return Math.max((Number(ep.rate_limit) || 0) * 2, 0);
    }

    endpointScopes(ep) {
        if (!ep) {
            return [];
        }
        if (Array.isArray(ep._scopes) && ep._scopes.length) {
            return ep._scopes;
        }
        const base = String(ep.name || "api")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "_")
            .replace(/^_|_$/g, "");
        if (!base) {
            return ["read:api"];
        }
        return [`read:${base}`, `write:${base}`];
    }

    endpointEnvLabel(ep) {
        if (!ep) {
            return "—";
        }
        if (ep.state === "active") {
            return "Production";
        }
        return this.statusLabel(ep.state);
    }

    onOpenConnector(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id) || this.state.selectedConnectorId;
        if (!id || id < 0) {
            this.notification.add("Demo connector — create a real connector to edit.", {
                type: "info",
            });
            return;
        }
        this._openForm("ei.connector", id);
    }

    onOpenSync(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id) || this.state.selectedSyncId;
        if (!id || id < 0) {
            this.notification.add("Demo sync job — create a real job to edit.", { type: "info" });
            return;
        }
        this._openForm("ei.sync.job", id);
    }

    onOpenMapping(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id) || this.state.selectedMappingId;
        if (id) {
            this._openForm("ei.master.mapping", id);
        }
    }

    onOpenLog(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id) || this.state.selectedLogId;
        if (!id || id < 0) {
            this.notification.add("Demo log — create real integration traffic to open records.", {
                type: "info",
            });
            return;
        }
        this._openForm("ei.log", id);
    }

    async onRetryLog(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id) || this.state.selectedLogId;
        if (!id || id < 0) {
            this.notification.add("Demo log — replay is available on real failed requests.", {
                type: "info",
            });
            return;
        }
        try {
            await this.orm.call("ei.log", "action_retry", [[id]]);
            this.notification.add("Retry queued.", { type: "success" });
            await this.loadData();
        } catch (err) {
            this._notifyError(err, "Retry failed.");
        }
    }

    async onRunSync(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id) || this.state.selectedSyncId;
        if (!id || id < 0) {
            this.notification.add("Demo sync job — create a real job to run.", { type: "info" });
            return;
        }
        try {
            const result = await this.orm.call("ei.sync.job", "action_run_now", [[id]]);
            if (result && result.type) {
                await this.action.doAction(result);
            } else {
                this.notification.add("Sync started.", { type: "success" });
                await this.loadData();
            }
        } catch (err) {
            this._notifyError(err, "Could not run sync job.");
        }
    }

    async onReconnectConnector(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id) || this.state.selectedConnectorId;
        if (!id || id < 0) {
            this.notification.add("Demo connector — reconnect runs on real connectors.", {
                type: "info",
            });
            return;
        }
        try {
            await this.orm.call("ei.connector", "action_reconnect", [[id]]);
            this.notification.add("Reconnect completed.", { type: "success" });
            await this.loadData();
        } catch (err) {
            this._notifyError(err, "Reconnect failed.");
        }
    }

    async onTestConnector(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id) || this.state.selectedConnectorId;
        if (!id || id < 0) {
            this.notification.add("Demo connector — connection test runs on real connectors.", {
                type: "info",
            });
            return;
        }
        try {
            const result = await this.orm.call("ei.connector", "action_test_connection", [[id]]);
            if (result && result.type) {
                await this.action.doAction(result);
            } else {
                this.notification.add("Connection test completed.", { type: "success" });
            }
            await this.loadData();
        } catch (err) {
            this._notifyError(err, "Connection test failed.");
        }
    }

    async onResolveConflict(ev) {
        ev.stopPropagation();
        const id = Number(ev.currentTarget.dataset.id);
        const side = ev.currentTarget.dataset.side || "external";
        if (!id) {
            return;
        }
        const resolution =
            side === "local" ? "Keep Local (PrecastMPS)" : "Keep External (MASTER)";
        try {
            await this.orm.write("ei.master.conflict", [id], {
                state: "resolved",
                resolution,
            });
            if (this.state.selectedMappingId) {
                await this.orm.write("ei.master.mapping", [this.state.selectedMappingId], {
                    state: "synced",
                    change_note: `Resolved conflict ${id}: ${resolution}`,
                });
            }
            this.notification.add("Conflict resolved.", { type: "success" });
            await this.selectMapping({ currentTarget: { dataset: { id: String(this.state.selectedMappingId) } } });
            await this.loadData();
        } catch (err) {
            this._notifyError(err, "Could not resolve conflict.");
        }
    }

    async onCopyLogId() {
        const log = this.selectedLog;
        if (!log) {
            return;
        }
        const text = String(log.correlation_id || log.id);
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(text);
            } else {
                const ta = document.createElement("textarea");
                ta.value = text;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand("copy");
                document.body.removeChild(ta);
            }
            this.notification.add("Copied to clipboard.", { type: "info" });
        } catch (err) {
            this._notifyError(err, "Copy failed.");
        }
    }

    onFilterChange(ev) {
        const key = ev.currentTarget.dataset.filter;
        if (!key) {
            return;
        }
        this.state[key] = ev.currentTarget.value || "all";
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    categoryLetter(category) {
        const map = { erp: "E", crm: "C", bank: "B", whatsapp: "W", legacy: "L" };
        return map[category] || (category || "?").charAt(0).toUpperCase();
    }

    categoryLabel(category) {
        const map = {
            erp: "ERP",
            crm: "CRM",
            bank: "Banking",
            whatsapp: "WhatsApp",
            legacy: "Legacy",
            api: "API",
            webhook: "Webhook",
            connector: "Connector",
            sync: "Sync",
            master_data: "Master",
            system: "System",
        };
        return map[category] || category || "—";
    }

    connectorCategoryLabel(conn) {
        if (!conn) {
            return "—";
        }
        if (conn._category_label) {
            return conn._category_label;
        }
        const map = {
            erp: "Enterprise Resource",
            crm: "Customer Relation",
            bank: "Banking",
            whatsapp: "Messaging",
            legacy: "Legacy",
        };
        return map[conn.category] || this.categoryLabel(conn.category);
    }

    connectorSystemType(conn) {
        if (!conn) {
            return "—";
        }
        if (conn._system_type) {
            return conn._system_type;
        }
        const map = {
            erp: "Odoo ERP",
            crm: "CRM Platform",
            bank: "Banking API",
            whatsapp: "WhatsApp Business",
            legacy: "Legacy Host",
        };
        return map[conn.category] || this.categoryLabel(conn.category);
    }

    connectorIcon(category) {
        const map = {
            erp: "fa-database",
            crm: "fa-desktop",
            bank: "fa-university",
            whatsapp: "fa-whatsapp",
            legacy: "fa-server",
        };
        return map[category] || "fa-plug";
    }

    connectorLastSync(conn) {
        if (!conn) {
            return "—";
        }
        if (conn._last_ago) {
            return conn._last_ago;
        }
        return this.formatRelative(conn.last_health_at);
    }

    formatRelative(value) {
        if (!value) {
            return "—";
        }
        try {
            const d = new Date(value);
            if (Number.isNaN(d.getTime())) {
                return this.formatWhen(value);
            }
            const diff = Math.max(0, Date.now() - d.getTime());
            const mins = Math.floor(diff / 60000);
            if (mins < 1) {
                return "Just now";
            }
            if (mins < 60) {
                return `${mins} min${mins === 1 ? "" : "s"} ago`;
            }
            const hrs = Math.floor(mins / 60);
            if (hrs < 24) {
                return `${hrs} hr${hrs === 1 ? "" : "s"} ago`;
            }
            const days = Math.floor(hrs / 24);
            return `${days} day${days === 1 ? "" : "s"} ago`;
        } catch {
            return this.formatWhen(value);
        }
    }

    healthLevel(conn) {
        if (!conn) {
            return 0;
        }
        if (conn._health_level != null) {
            return conn._health_level;
        }
        const tone = this.healthTone(conn.health_state, conn.state);
        if (tone === "ok") {
            return 5;
        }
        if (tone === "warn") {
            return 3;
        }
        return 1;
    }

    healthBars(conn) {
        const level = this.healthLevel(conn);
        return [1, 2, 3, 4, 5].map((i) => ({
            i,
            on: i <= level,
            tone: this.healthTone(conn && conn.health_state, conn && conn.state),
        }));
    }

    statusLabel(status) {
        const map = {
            synced: "In Sync",
            pending: "Pending",
            failed: "Failed",
            partial: "Partial Failure",
            partially_completed: "Partial Failure",
            updated: "Updated",
            archived: "Archived",
            conflict: "Conflict",
            active: "Active",
            inactive: "Inactive",
            connected: "Connected",
            disconnected: "Disconnected",
            error: "Error",
            deprecated: "Deprecated",
            restricted: "Restricted",
            delivered: "Delivered",
            inbound: "Inbound",
            outbound: "Outbound",
            running: "Syncing",
            syncing: "Syncing",
            completed: "Completed",
            delivered: "Delivered",
            retrying: "Retrying",
        };
        if (!status) {
            return "—";
        }
        if (map[status]) {
            return map[status];
        }
        return String(status)
            .split("_")
            .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
            .join(" ");
    }

    syncJobStatus(job) {
        if (!job) {
            return "draft";
        }
        const run = job.last_run_state || "";
        if (run === "running") {
            return "running";
        }
        if (run === "partial" || run === "partially_completed" || (job._last_failed > 0 && (run === "failed" || run === "completed"))) {
            return "partial";
        }
        if (run === "failed") {
            return "failed";
        }
        if (job.state === "active" || job.active) {
            return "active";
        }
        return run || job.state || "draft";
    }

    syncLastRunLabel(job) {
        if (!job) {
            return "—";
        }
        if (job._last_ago) {
            return job._last_ago;
        }
        return this.formatWhen(job.last_success_at);
    }

    syncLastRunMeta(job) {
        if (!job) {
            return "";
        }
        if (job._last_failed > 0) {
            return `${job._last_failed} failed records`;
        }
        if (job._last_records) {
            return `${this.formatCount(job._last_records)} records`;
        }
        return "";
    }

    syncProgress(job) {
        if (!job) {
            return 0;
        }
        if (job._progress) {
            return job._progress;
        }
        if ((job.last_run_state || "") === "running") {
            return 45 + ((Number(job.id) || 0) % 40);
        }
        return 0;
    }

    conflictPolicyLabel(policy) {
        const map = {
            source_wins: "Source Wins",
            destination_wins: "Destination Wins",
            manual: "Manual Review",
            skip: "Skip",
        };
        return map[policy] || this.statusLabel(policy) || "—";
    }

    mappingCountLabel(job) {
        const n = job && (job._mapping_count || 0);
        return `${n} Fields Mapped`;
    }

    activityTone(run) {
        const s = (run && run.state) || "";
        if (s === "completed" || s === "success") {
            return "success";
        }
        if (s === "failed" || s === "error") {
            return "danger";
        }
        return "info";
    }

    activityBody(run) {
        if (!run) {
            return "—";
        }
        if (run.error_message) {
            return run.error_message;
        }
        if (run.records_processed) {
            return `${this.formatCount(run.records_processed)} records processed`;
        }
        return this.statusLabel(run.state);
    }

    formatCompact(value) {
        const n = Number(value) || 0;
        if (n >= 1000000) {
            return `${(n / 1000000).toFixed(1).replace(/\.0$/, "")}M`;
        }
        if (n >= 1000) {
            return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`;
        }
        return n.toLocaleString();
    }

    connectorHealthPct(conn) {
        if (!conn) {
            return 0;
        }
        if (conn._health_pct != null) {
            return conn._health_pct;
        }
        const tone = this.healthTone(conn.health_state, conn.state);
        if (tone === "ok") {
            return 100;
        }
        if (tone === "warn") {
            return 55;
        }
        return 20;
    }

    connectorStatusClass(conn) {
        if (!conn) {
            return "unknown";
        }
        if (conn.state === "error" || conn.health_state === "down") {
            return "failed";
        }
        if (conn.health_state === "degraded") {
            return "warning";
        }
        if (conn.state === "disconnected" || conn.state === "disabled") {
            return "disconnected";
        }
        return conn.state || "unknown";
    }

    connectorStatusLabel(conn) {
        if (!conn) {
            return "—";
        }
        if (conn.health_state === "degraded" && conn.state === "connected") {
            return "Warning";
        }
        if (conn.state === "error") {
            return "Disconnected";
        }
        return this.statusLabel(conn.state);
    }

    healthBarStyle(conn) {
        return `width: ${this.connectorHealthPct(conn)}%`;
    }

    activityRecords(log) {
        if (!log) {
            return "—";
        }
        if (log._records) {
            return log._records;
        }
        if (log.error_message && (log.level === "failed" || log.level === "timeout")) {
            const msg = String(log.error_message);
            return msg.length > 28 ? `${msg.slice(0, 28)}…` : msg;
        }
        if (log.duration_ms) {
            return `${Number(log.duration_ms).toLocaleString()} ms`;
        }
        return "—";
    }

    activityRecordsDanger(log) {
        if (!log) {
            return false;
        }
        if (log._records_danger) {
            return true;
        }
        return log.level === "failed" || log.level === "timeout" || log.level === "rejected";
    }

    dashboardActivityTime(log) {
        if (!log) {
            return "—";
        }
        if (log._time) {
            return log._time;
        }
        return this.formatTime(log.create_date);
    }

    formatCount(value) {
        const n = Number(value) || 0;
        return n.toLocaleString();
    }

    sotDisplay(mapping) {
        if (!mapping) {
            return "—";
        }
        if (mapping.source_of_truth === "source") {
            return `${mapping.source_system} (External)`;
        }
        if (mapping.source_of_truth === "target") {
            return `${mapping.target_system} (Target)`;
        }
        if (mapping.source_of_truth === "precastmps") {
            return "PrecastMPS (Local)";
        }
        return this.sotLabel(mapping.source_of_truth);
    }

    masterActionIcon(mapping) {
        if (!mapping) {
            return "fa-ellipsis-v";
        }
        if (mapping.state === "pending" || mapping.conflict_count) {
            return "fa-exchange";
        }
        if (mapping.state === "failed") {
            return "fa-refresh";
        }
        return "fa-ellipsis-v";
    }

    levelLabel(level) {
        const map = {
            success: "Success",
            failed: "Failed",
            warning: "Warning",
            timeout: "Timeout",
            retrying: "Retrying",
            rejected: "Rejected",
        };
        return map[level] || this.statusLabel(level);
    }

    logStatusLabel(log) {
        if (!log) {
            return "—";
        }
        const base = this.levelLabel(log.level);
        if (log._http_status) {
            return `${base} (${log._http_status})`;
        }
        if (log.level === "failed" || log.level === "rejected") {
            return `${base} (500)`;
        }
        if (log.level === "success") {
            return `${base} (200)`;
        }
        if (log.level === "timeout") {
            return `${base} (408)`;
        }
        return base;
    }

    shortCorrelationId(log) {
        if (!log) {
            return "";
        }
        const id = String(log.correlation_id || log.id || "");
        if (id.length > 14) {
            return id.slice(0, 12);
        }
        return id;
    }

    logEndpoint(log) {
        if (!log) {
            return "—";
        }
        if (log._endpoint) {
            return log._endpoint;
        }
        const op = String(log.operation || "");
        const m = op.match(/(\/[^\s]+)/);
        return m ? m[1] : op || "—";
    }

    logMethod(log) {
        if (!log) {
            return "—";
        }
        if (log._method) {
            return log._method;
        }
        const op = String(log.operation || "");
        const m = op.match(/^(GET|POST|PUT|PATCH|DELETE)\b/i);
        return m ? m[1].toUpperCase() : "—";
    }

    logTime(log) {
        if (!log) {
            return "—";
        }
        if (log._time) {
            return log._time;
        }
        return this.formatTime(log.create_date);
    }

    durationLabel(ms) {
        const n = Number(ms) || 0;
        return `${n.toLocaleString()} ms`;
    }

    monitorShowingLabel() {
        const rows = this.filteredMonitorLogs;
        const total = this.state.monitorKpis.total || rows.length;
        if (!rows.length) {
            return "Showing 0 entries";
        }
        return `Showing 1 to ${rows.length} of ${Number(total).toLocaleString()} entries`;
    }

    authLabel(auth) {
        const map = {
            none: "None",
            api_key: "API Key",
            oauth: "OAuth 2.0",
            both: "API Key / OAuth",
            public: "Public",
            basic: "Basic",
            certificate: "Certificate",
            custom: "Custom",
        };
        return map[auth] || this.statusLabel(auth);
    }

    formatWhen(value) {
        if (!value) {
            return "—";
        }
        try {
            const d = new Date(value);
            if (Number.isNaN(d.getTime())) {
                return String(value);
            }
            return d.toLocaleString(undefined, {
                year: "numeric",
                month: "short",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
            });
        } catch {
            return String(value);
        }
    }

    formatTime(value) {
        if (!value) {
            return "—";
        }
        try {
            const d = new Date(value);
            if (Number.isNaN(d.getTime())) {
                return String(value);
            }
            return d.toLocaleTimeString(undefined, {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
            });
        } catch {
            return String(value);
        }
    }

    activityTime(run) {
        if (!run) {
            return "—";
        }
        if (run._time) {
            return run._time;
        }
        if (run.create_date) {
            return this.formatTime(run.create_date);
        }
        return "—";
    }

    barWidth(count) {
        const h = this.state.health || {};
        const total = Math.max(
            1,
            (h.healthy || 0) + (h.warning || 0) + (h.disconnected || 0) + (h.error || 0)
        );
        const n = Number(count) || 0;
        const pct = Math.min(100, Math.round((n / total) * 100));
        return `width: ${Math.max(pct, n ? 8 : 0)}%`;
    }

    healthTone(healthState, connState) {
        if (connState === "error" || healthState === "down") {
            return "bad";
        }
        if (connState === "disconnected" || connState === "disabled") {
            return "bad";
        }
        if (healthState === "degraded" || connState === "pending_configuration" || connState === "connecting") {
            return "warn";
        }
        if (healthState === "healthy" || connState === "connected") {
            return "ok";
        }
        return "warn";
    }

    scheduleLabel(job) {
        if (!job) {
            return "—";
        }
        if (job.trigger === "realtime") {
            return "Real-time";
        }
        if (job.trigger === "manual" || job.frequency === "manual") {
            return "Manual";
        }
        return this.statusLabel(job.frequency || job.trigger);
    }

    directionArrow(job) {
        return job && job.direction === "two_way" ? "↔" : "→";
    }

    sotLabel(sot) {
        const map = {
            source: "Source System",
            target: "Target System",
            precastmps: "PrecastMPS",
            manual: "Manual Decision",
        };
        return map[sot] || this.statusLabel(sot) || "—";
    }

    truncate(text, max = 180) {
        if (!text) {
            return "—";
        }
        const s = String(text);
        return s.length > max ? `${s.slice(0, max)}...` : s;
    }

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            await this._loadSharedKpis();
            const screen = this.state.screen;
            if (screen === "dashboard") {
                await this._loadDashboard();
            } else if (screen === "api") {
                await this._loadApi();
            } else if (screen === "connectors") {
                await this._loadConnectors();
            } else if (screen === "sync") {
                await this._loadSync();
            } else if (screen === "master") {
                await this._loadMaster();
            } else if (screen === "monitoring") {
                await this._loadMonitoring();
            }
        } catch (err) {
            this._notifyError(err, "Failed to load data.");
        } finally {
            this.state.loading = false;
        }
    }

    async _loadSharedKpis() {
        const [
            activeIntegrations,
            connectedConnectors,
            failedOps,
            syncSuccess,
            syncPending,
            syncConflicts,
            healthy,
            degraded,
            down,
            disconnected,
            apiSuccess,
            apiFailed,
            webhookSuccess,
            webhookFailed,
        ] = await Promise.all([
            this.orm.searchCount("ei.integration", [["state", "=", "active"]]),
            this.orm.searchCount("ei.connector", [["state", "=", "connected"]]),
            this.orm.searchCount("ei.log", [["level", "in", ["failed", "timeout", "rejected"]]]),
            this.orm.searchCount("ei.sync.run", [["state", "=", "completed"]]),
            this.orm.searchCount("ei.sync.run", [["state", "=", "pending"]]),
            this.orm.searchCount("ei.sync.run", [["records_conflict", ">", 0]]),
            this.orm.searchCount("ei.connector", [["health_state", "=", "healthy"]]),
            this.orm.searchCount("ei.connector", [["health_state", "=", "degraded"]]),
            this.orm.searchCount("ei.connector", [["health_state", "=", "down"]]),
            this.orm.searchCount("ei.connector", [["state", "in", ["disconnected", "disabled"]]]),
            this.orm.searchCount("ei.log", [["category", "=", "api"], ["level", "=", "success"]]),
            this.orm.searchCount("ei.log", [
                ["category", "=", "api"],
                ["level", "in", ["failed", "rejected", "timeout"]],
            ]),
            this.orm.searchCount("ei.log", [["category", "=", "webhook"], ["level", "=", "success"]]),
            this.orm.searchCount("ei.log", [
                ["category", "=", "webhook"],
                ["level", "in", ["failed", "retrying"]],
            ]),
        ]);

        this.state.kpis = {
            activeIntegrations,
            connectedConnectors,
            failedOps,
            syncSuccess,
            syncPending,
            syncConflicts,
        };
        this.state.health = {
            healthy,
            warning: degraded,
            disconnected,
            error: down,
        };
        this.state.sync = {
            running: await this.orm.searchCount("ei.sync.run", [["state", "=", "running"]]),
            failed: await this.orm.searchCount("ei.sync.run", [["state", "=", "failed"]]),
            pending: syncPending,
            conflicts: syncConflicts,
        };
        this.state.api = {
            requests: apiSuccess + apiFailed,
            success: apiSuccess,
            failed: apiFailed,
            webhookDeliveries: webhookSuccess,
            webhookFailed,
        };
    }

    async _loadDashboard() {
        const [
            recentLogs,
            connectors,
            external,
            apiWebhook,
            validateOk,
            validateFailed,
            transformOk,
            transformFailed,
            syncOk,
            syncFailed,
            logCount,
            monitorFailed,
        ] = await Promise.all([
            this.orm.searchRead(
                "ei.log",
                [],
                [
                    "name",
                    "category",
                    "level",
                    "create_date",
                    "correlation_id",
                    "operation",
                    "source_system",
                    "retryable",
                    "duration_ms",
                    "error_message",
                ],
                { limit: 12, order: "create_date desc" }
            ),
            this.orm.searchRead(
                "ei.connector",
                [],
                ["name", "category", "state", "health_state", "is_mock", "last_health_at"],
                { limit: 12, order: "write_date desc" }
            ),
            this.orm.searchCount("ei.connector", [["state", "=", "connected"]]),
            this.orm.searchCount("ei.log", [
                ["operation", "in", ["api_request", "webhook_incoming"]],
                ["level", "=", "success"],
            ]),
            this.orm.searchCount("ei.log", [
                ["operation", "=", "pipeline_validate"],
                ["level", "=", "success"],
            ]),
            this.orm.searchCount("ei.log", [
                ["operation", "=", "pipeline_validate"],
                ["level", "in", ["failed", "rejected"]],
            ]),
            this.orm.searchCount("ei.log", [
                ["operation", "=", "pipeline_transform"],
                ["level", "=", "success"],
            ]),
            this.orm.searchCount("ei.log", [
                ["operation", "=", "pipeline_transform"],
                ["level", "in", ["failed", "rejected"]],
            ]),
            this.orm.searchCount("ei.sync.run", [["state", "in", ["completed", "partially_completed"]]]),
            this.orm.searchCount("ei.sync.run", [["state", "=", "failed"]]),
            this.orm.searchCount("ei.log", []),
            this.orm.searchCount("ei.log", [["level", "in", ["failed", "timeout", "rejected"]]]),
        ]);

        if (!connectors.length && !recentLogs.length) {
            const demo = DEMO_DASHBOARD;
            this.state.kpis = { ...demo.kpis };
            this.state.health = { ...demo.health };
            this.state.sync = { ...demo.sync };
            this.state.api = { ...demo.api };
            this.state.connectors = demo.connectors.map((c) => ({ ...c }));
            this.state.recentLogs = demo.recentLogs.map((l) => ({ ...l }));
            this.state.pipeline = {
                external: demo.health.healthy,
                api_webhook: demo.api.requests,
                validate: 100,
                validateFailed: 0,
                transform: 100,
                transformFailed: 0,
                sync: demo.kpis.syncSuccess,
                syncFailed: demo.sync.failed,
                log: demo.api.requests,
                monitorFailed: demo.kpis.failedOps,
            };
            return;
        }

        this.state.recentLogs = recentLogs;
        this.state.connectors = connectors;
        this.state.pipeline = {
            external,
            api_webhook: apiWebhook,
            validate: validateOk,
            validateFailed,
            transform: transformOk,
            transformFailed,
            sync: syncOk,
            syncFailed,
            log: logCount,
            monitorFailed,
        };
    }

    async _loadApi() {
        const [
            activeEndpoints,
            activeWebhooks,
            delivered,
            failedEvents,
            apiErrors,
            endpoints,
            webhooks,
            apiKeys,
            deliveries,
        ] = await Promise.all([
            this.orm.searchCount("ei.api.endpoint", [["state", "=", "active"]]),
            this.orm.searchCount("ei.webhook", [["state", "=", "active"]]),
            this.orm.searchCount("ei.webhook.delivery", [["status", "=", "delivered"]]),
            this.orm.searchCount("ei.webhook.delivery", [["status", "in", ["failed", "retrying"]]]),
            this.orm.searchCount("ei.log", [
                ["category", "=", "api"],
                ["level", "in", ["failed", "rejected", "timeout"]],
            ]),
            this.orm.searchRead(
                "ei.api.endpoint",
                [],
                [
                    "name",
                    "path",
                    "method",
                    "auth_type",
                    "state",
                    "usage_count",
                    "version",
                    "rate_limit",
                ],
                { limit: 80, order: "name" }
            ),
            this.orm.searchRead(
                "ei.webhook",
                [],
                ["name", "code", "direction", "auth_type", "state"],
                { limit: 80, order: "name" }
            ),
            this.orm.searchRead(
                "ei.api.credential",
                [],
                ["name", "key_prefix", "state", "last_used_at", "expiry_date"],
                { limit: 80, order: "name" }
            ),
            this.orm.searchRead(
                "ei.webhook.delivery",
                [],
                ["name", "status", "http_status", "correlation_id", "create_date"],
                { limit: 80, order: "create_date desc" }
            ),
        ]);

        if (!endpoints.length && !webhooks.length) {
            this.state.apiKpis = { ...DEMO_API_KPIS };
            this.state.endpoints = DEMO_API_ENDPOINTS.map((e) => ({ ...e }));
            this.state.webhooks = DEMO_API_WEBHOOKS.map((w) => ({ ...w }));
            this.state.apiKeys = DEMO_API_KEYS.map((k) => ({ ...k }));
            this.state.deliveries = DEMO_API_DELIVERIES.map((d) => ({ ...d }));
            if (!this.state.selectedEndpointId) {
                this.state.selectedEndpointId = DEMO_API_ENDPOINTS[0].id;
            }
            return;
        }

        this.state.apiKpis = {
            activeEndpoints,
            apiRequests: this.state.api.requests || endpoints.reduce((s, e) => s + (e.usage_count || 0), 0),
            activeWebhooks,
            delivered,
            failedEvents,
            apiErrors,
        };
        this.state.endpoints = endpoints;
        this.state.webhooks = webhooks;
        this.state.apiKeys = apiKeys;
        this.state.deliveries = deliveries;
        if (!this.state.selectedEndpointId && endpoints.length) {
            this.state.selectedEndpointId = endpoints[0].id;
        }
    }

    async _loadConnectors() {
        const [total, connected, disconnected, error, pending, connectors] = await Promise.all([
            this.orm.searchCount("ei.connector", []),
            this.orm.searchCount("ei.connector", [["state", "=", "connected"]]),
            this.orm.searchCount("ei.connector", [["state", "in", ["disconnected", "disabled"]]]),
            this.orm.searchCount("ei.connector", [["state", "=", "error"]]),
            this.orm.searchCount("ei.connector", [["state", "=", "pending_configuration"]]),
            this.orm.searchRead(
                "ei.connector",
                [],
                [
                    "name",
                    "category",
                    "state",
                    "health_state",
                    "is_mock",
                    "last_health_at",
                    "version",
                    "auth_method",
                    "base_url",
                ],
                { limit: 100, order: "category, name" }
            ),
        ]);

        if (!connectors.length) {
            this.state.connectorKpis = { ...DEMO_CONNECTOR_KPIS };
            this.state.connectors = DEMO_CONNECTORS.map((c) => ({ ...c }));
            if (!this.state.selectedConnectorId) {
                this.state.selectedConnectorId = DEMO_CONNECTORS[0].id;
            }
            const sid = this.state.selectedConnectorId;
            this.state.connectorMappings = (DEMO_CONNECTOR_MAPPINGS[sid] || []).map((m) => ({
                ...m,
            }));
            return;
        }

        this.state.connectorKpis = {
            total,
            connected,
            connectedDelta: 0,
            disconnected,
            error,
            pending,
        };
        this.state.connectors = connectors;
        if (!this.state.selectedConnectorId && connectors.length) {
            this.state.selectedConnectorId = connectors[0].id;
        }
        if (this.state.selectedConnectorId && this.state.selectedConnectorId > 0) {
            this.state.connectorMappings = await this.orm.searchRead(
                "ei.connector.mapping",
                [["connector_id", "=", this.state.selectedConnectorId]],
                ["source_field", "target_field", "name"],
                { limit: 40, order: "sequence, id" }
            );
        }
    }

    async _loadSync() {
        const [
            jobsTotal,
            running,
            completed,
            failed,
            pending,
            syncJobs,
            syncRuns,
            syncFailedRecords,
        ] = await Promise.all([
            this.orm.searchCount("ei.sync.job", []),
            this.orm.searchCount("ei.sync.run", [["state", "=", "running"]]),
            this.orm.searchCount("ei.sync.run", [["state", "=", "completed"]]),
            this.orm.searchCount("ei.sync.run", [["state", "=", "failed"]]),
            this.orm.searchCount("ei.sync.run", [["state", "=", "pending"]]),
            this.orm.searchRead(
                "ei.sync.job",
                [],
                [
                    "name",
                    "entity_name",
                    "source_system",
                    "dest_system",
                    "direction",
                    "trigger",
                    "frequency",
                    "conflict_policy",
                    "state",
                    "active",
                    "last_success_at",
                    "last_run_state",
                ],
                { limit: 100, order: "name" }
            ),
            this.orm.searchRead(
                "ei.sync.run",
                [],
                [
                    "name",
                    "state",
                    "create_date",
                    "records_processed",
                    "records_failed",
                    "error_message",
                    "job_id",
                ],
                { limit: 40, order: "create_date desc" }
            ),
            this.orm.searchCount("ei.sync.record", [["state", "=", "failed"]]),
        ]);

        let jobs = syncJobs;
        let runs = syncRuns;
        let kpis = {
            jobsTotal,
            running,
            completed,
            failed,
            pending,
            processed: syncRuns.reduce((sum, r) => sum + (r.records_processed || 0), 0),
            failedRecords: syncFailedRecords,
        };

        if (!jobs.length) {
            jobs = DEMO_SYNC_JOBS.map((j) => ({ ...j }));
            runs = DEMO_SYNC_RUNS.map((r) => ({ ...r }));
            kpis = {
                jobsTotal: 42,
                running: 6,
                completed: 184,
                failed: 12,
                pending: 24,
                processed: 48284,
                failedRecords: 12,
            };
        } else {
            const jobIds = jobs.map((j) => j.id);
            let mappingRows = [];
            try {
                mappingRows = await this.orm.searchRead(
                    "ei.connector.mapping",
                    [["sync_job_id", "in", jobIds]],
                    ["sync_job_id"],
                    { limit: 2000 }
                );
            } catch (_err) {
                mappingRows = [];
            }
            const mapCount = {};
            for (const row of mappingRows) {
                const jid = Array.isArray(row.sync_job_id) ? row.sync_job_id[0] : row.sync_job_id;
                mapCount[jid] = (mapCount[jid] || 0) + 1;
            }
            const latestByJob = {};
            for (const run of runs) {
                const jid = Array.isArray(run.job_id) ? run.job_id[0] : run.job_id;
                if (jid && !latestByJob[jid]) {
                    latestByJob[jid] = run;
                }
            }
            jobs = jobs.map((job) => {
                const latest = latestByJob[job.id];
                const lastFailed = latest ? latest.records_failed || 0 : 0;
                let runState = job.last_run_state;
                if (lastFailed > 0 && runState === "completed") {
                    runState = "partial";
                } else if (lastFailed > 0 && runState === "failed") {
                    runState = "partial";
                }
                return {
                    ...job,
                    last_run_state: runState || job.last_run_state,
                    _last_records: latest ? latest.records_processed || 0 : 0,
                    _last_failed: lastFailed,
                    _mapping_count: mapCount[job.id] || 0,
                    _progress: (job.last_run_state || "") === "running" ? 45 + (job.id % 40) : 0,
                };
            });
        }

        this.state.syncKpis = kpis;
        this.state.syncJobs = jobs;
        this.state.syncRuns = runs;
        this.state.syncFailedRecords = kpis.failedRecords || syncFailedRecords;
        if (!this.state.selectedSyncId && jobs.length) {
            this.state.selectedSyncId = jobs[0].id;
        }
    }

    async _loadMaster() {
        const [
            entities,
            synced,
            pending,
            conflicts,
            failed,
            masterEntities,
            masterMappings,
        ] = await Promise.all([
            this.orm.searchCount("ei.master.entity", []),
            this.orm.searchCount("ei.master.mapping", [["state", "=", "synced"]]),
            this.orm.searchCount("ei.master.mapping", [["state", "=", "pending"]]),
            this.orm.searchCount("ei.master.conflict", [["state", "=", "conflict"]]),
            this.orm.searchCount("ei.master.mapping", [["state", "=", "failed"]]),
            this.orm.searchRead(
                "ei.master.entity",
                [],
                ["name", "code", "active", "mapping_count"],
                { limit: 50, order: "name" }
            ),
            this.orm.searchRead(
                "ei.master.mapping",
                [],
                [
                    "name",
                    "entity_id",
                    "source_system",
                    "target_system",
                    "source_of_truth",
                    "state",
                    "last_sync_at",
                    "conflict_count",
                    "owner",
                ],
                { limit: 120, order: "name" }
            ),
        ]);

        let lastSync = false;
        for (const m of masterMappings) {
            if (m.last_sync_at && (!lastSync || m.last_sync_at > lastSync)) {
                lastSync = m.last_sync_at;
            }
            // Prefer DB value when present; keep demo-friendly fallback by name.
            if (m.record_count === undefined || m.record_count === null || m.record_count === false) {
                m.record_count = DEMO_MASTER_RECORD_COUNTS[m.name] || 0;
            }
        }

        this.state.masterKpis = {
            entities,
            synced,
            pending,
            conflicts,
            failed,
            lastSync,
        };
        this.state.masterEntities = masterEntities;
        this.state.masterMappings = masterMappings;
        await this._selectFirstMasterMapping();
    }

    async _loadMonitoring() {
        const [
            total,
            success,
            failed,
            webhookFail,
            syncFail,
            connectorErr,
            monitorLogs,
        ] = await Promise.all([
            this.orm.searchCount("ei.log", []),
            this.orm.searchCount("ei.log", [["level", "=", "success"]]),
            this.orm.searchCount("ei.log", [["level", "in", ["failed", "timeout", "rejected"]]]),
            this.orm.searchCount("ei.log", [
                ["category", "=", "webhook"],
                ["level", "in", ["failed", "retrying"]],
            ]),
            this.orm.searchCount("ei.log", [
                ["category", "=", "sync"],
                ["level", "in", ["failed", "timeout"]],
            ]),
            this.orm.searchCount("ei.log", [
                ["category", "=", "connector"],
                ["level", "in", ["failed", "timeout", "rejected"]],
            ]),
            this.orm.searchRead(
                "ei.log",
                [],
                [
                    "name",
                    "category",
                    "level",
                    "create_date",
                    "correlation_id",
                    "operation",
                    "source_system",
                    "duration_ms",
                    "error_message",
                    "request_summary",
                    "response_summary",
                    "retryable",
                ],
                { limit: 120, order: "create_date desc" }
            ),
        ]);

        if (!monitorLogs.length) {
            this.state.monitorKpis = { ...DEMO_MONITOR_KPIS };
            this.state.monitorLogs = DEMO_MONITOR_LOGS.map((l) => ({ ...l }));
            if (!this.state.selectedLogId) {
                this.state.selectedLogId = DEMO_MONITOR_LOGS[0].id;
            }
            return;
        }

        const withDuration = monitorLogs.filter((l) => l.duration_ms);
        const avg = withDuration.length
            ? Math.round(
                  withDuration.reduce((s, l) => s + (l.duration_ms || 0), 0) / withDuration.length
              )
            : 0;
        const successRate = total ? Math.round((success / total) * 1000) / 10 : 0;
        const failRate = total ? Math.round((failed / total) * 1000) / 10 : 0;
        const availability = total
            ? Math.round(((total - failed) / total) * 1000) / 10
            : 100;

        this.state.monitorKpis = {
            total,
            success,
            failed,
            successRate,
            failRate,
            avg,
            avgTrend: -12,
            webhookFail,
            syncFail,
            connectorErr,
            availability,
        };
        this.state.monitorLogs = monitorLogs;
        if (!this.state.selectedLogId && monitorLogs.length) {
            this.state.selectedLogId = monitorLogs[0].id;
        }
    }

    // -------------------------------------------------------------------------
    // Internals
    // -------------------------------------------------------------------------

    _filterBySearch(rows, fields) {
        const q = (this.state.search || "").trim().toLowerCase();
        if (!q) {
            return rows;
        }
        return rows.filter((row) =>
            fields.some((f) => String(row[f] || "").toLowerCase().includes(q))
        );
    }

    _openForm(resModel, resId = null) {
        const action = {
            type: "ir.actions.act_window",
            res_model: resModel,
            views: [[false, "form"]],
            target: "current",
        };
        if (resId) {
            action.res_id = resId;
        }
        this.action.doAction(action);
    }

    _notifyError(err, fallback) {
        const message = (err && (err.data?.message || err.message)) || fallback;
        this.state.error = message;
        this.notification.add(message, { type: "danger" });
    }
}

registry.category("actions").add("ei_app", EiApp);
