/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * Chart.js plugin: reference mockup annotations (bands, threshold lines, labels).
 */
export const rulTobmAnnotationsPlugin = {
    id: "rulTobmAnnotations",
    beforeDatasetsDraw(chart, _args, opts) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea || !scales.x || !scales.y) {
            return;
        }
        const xScale = scales.x;
        const yScale = scales.y;
        const failureLife = opts.failureLifePct ?? 75;
        const maintStart = opts.maintenanceStart ?? 85;
        const failureRul = opts.failureRulPct ?? 25;
        const tobmX = opts.tobmLineX ?? 70;

        const xTobmShade = xScale.getPixelForValue(failureLife);
        const xMaint = xScale.getPixelForValue(maintStart);
        const yFail = yScale.getPixelForValue(failureRul);

        ctx.save();
        ctx.fillStyle = "rgba(255, 247, 237, 0.92)";
        ctx.fillRect(xTobmShade, chartArea.top, xMaint - xTobmShade, chartArea.bottom - chartArea.top);
        ctx.fillStyle = "rgba(239, 246, 255, 0.95)";
        ctx.fillRect(xMaint, chartArea.top, chartArea.right - xMaint, chartArea.bottom - chartArea.top);
        ctx.restore();
    },
    afterDatasetsDraw(chart, _args, opts) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea || !scales.x || !scales.y) {
            return;
        }
        const xScale = scales.x;
        const yScale = scales.y;
        const failureRul = opts.failureRulPct ?? 25;
        const maintStart = opts.maintenanceStart ?? 85;
        const tobmX = opts.tobmLineX ?? 70;
        const tobmY = opts.tobmPointY ?? 25;
        const labels = opts.labels || {};

        const yFail = yScale.getPixelForValue(failureRul);
        const xTobm = xScale.getPixelForValue(tobmX);
        const xMaint = xScale.getPixelForValue(maintStart);
        const yTobm = yScale.getPixelForValue(tobmY);

        const drawVLine = (x, color) => {
            ctx.save();
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.5;
            ctx.setLineDash([5, 4]);
            ctx.beginPath();
            ctx.moveTo(x, chartArea.top);
            ctx.lineTo(x, chartArea.bottom);
            ctx.stroke();
            ctx.restore();
        };

        ctx.save();
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(chartArea.left, yFail);
        ctx.lineTo(chartArea.right, yFail);
        ctx.stroke();
        ctx.setLineDash([]);

        drawVLine(xTobm, "#f97316");
        drawVLine(xMaint, "#2563eb");

        ctx.font = "700 10px system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
        ctx.fillStyle = "#dc2626";
        ctx.textAlign = "start";
        ctx.fillText(labels.failure || _t("Failure Threshold (25%)"), chartArea.left + 6, yFail - 8);

        ctx.fillStyle = "#c2410c";
        ctx.textAlign = "center";
        ctx.fillText(labels.tobm || _t("75% TOBM Point"), xTobm, yTobm - 14);

        ctx.fillStyle = "#1d4ed8";
        ctx.textAlign = "start";
        ctx.fillText(labels.maintenance || _t("85% Maintenance Start"), xMaint + 6, chartArea.top + 16);

        ctx.beginPath();
        ctx.arc(xTobm, yTobm, 7, 0, Math.PI * 2);
        ctx.fillStyle = "#f97316";
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.restore();
    },
};

/**
 * Build Chart.js config for the RUL lifecycle line chart.
 * @param {Object} chartData from maintenance.rul.tobm.dashboard payload
 */
export function buildRulTobmChartConfig(chartData) {
    const points = chartData?.points || [];
    const labels = chartData?.labels || {};
    return {
        type: "line",
        data: {
            datasets: [
                {
                    label: _t("RUL Remaining (%)"),
                    data: points,
                    parsing: false,
                    borderColor: "#2563eb",
                    backgroundColor: "#2563eb",
                    borderWidth: 2.5,
                    tension: 0.35,
                    pointRadius: points.map((p) => (p.x % 10 === 0 ? 4 : 0)),
                    pointHoverRadius: 6,
                    pointBackgroundColor: "#2563eb",
                    pointBorderColor: "#ffffff",
                    pointBorderWidth: 1.5,
                    fill: false,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            layout: { padding: { top: 8, right: 8, bottom: 4, left: 4 } },
            scales: {
                x: {
                    type: "linear",
                    min: 0,
                    max: 100,
                    grid: { color: "#e8edf3" },
                    ticks: {
                        stepSize: 10,
                        color: "#64748b",
                        font: { size: 10 },
                        callback: (v) => `${v}%`,
                    },
                    title: {
                        display: true,
                        text: labels.x_axis || _t("Lifecycle Progress (%)"),
                        color: "#475569",
                        font: { size: 11, weight: "600" },
                    },
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: "#e8edf3" },
                    ticks: {
                        stepSize: 25,
                        color: "#64748b",
                        font: { size: 10 },
                        callback: (v) => `${v}%`,
                    },
                    title: {
                        display: true,
                        text: labels.y_axis || _t("RUL Remaining (%)"),
                        color: "#475569",
                        font: { size: 11, weight: "600" },
                    },
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) =>
                            `${_t("RUL")}: ${ctx.parsed.y}% @ ${ctx.parsed.x}% ${_t("lifecycle")}`,
                    },
                },
                rulTobmAnnotations: {
                    failureLifePct: chartData.failure_life_pct,
                    failureRulPct: chartData.failure_rul_pct,
                    maintenanceStart: chartData.maintenance_start,
                    tobmLineX: chartData.tobm_line_x,
                    tobmPointY: chartData.tobm_point_y,
                    labels,
                },
            },
        },
        plugins: [rulTobmAnnotationsPlugin],
    };
}
