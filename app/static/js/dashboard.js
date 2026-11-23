// ========================================
// DevOps Monitoring Dashboard Controller
// ========================================

console.log("DevOps Monitoring Dashboard started");

let autoScrollEnabled = true;
let currentHistoryRange = 30;
let cpuChart = null;
let memChart = null;

// ----------------------------------------
// CHART.JS INITIALIZATION
// ----------------------------------------

function initCharts() {
    if (typeof Chart === "undefined") {
        console.warn("Chart.js not loaded yet, retrying...");
        return;
    }

    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                grid: { color: "rgba(255, 255, 255, 0.05)" },
                ticks: { color: "#94a3b8", maxTicksLimit: 8, font: { size: 10 } }
            },
            y: {
                grid: { color: "rgba(255, 255, 255, 0.05)" },
                ticks: { color: "#94a3b8", font: { size: 10 } },
                beginAtZero: true
            }
        }
    };

    const cpuCtx = document.getElementById("cpuChart")?.getContext("2d");
    if (cpuCtx && !cpuChart) {
        cpuChart = new Chart(cpuCtx, {
            type: "line",
            data: {
                labels: [],
                datasets: [{
                    label: "CPU Usage %",
                    data: [],
                    borderColor: "#38bdf8",
                    backgroundColor: "rgba(56, 189, 248, 0.15)",
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 1
                }]
            },
            options: chartDefaults
        });
    }

    const memCtx = document.getElementById("memChart")?.getContext("2d");
    if (memCtx && !memChart) {
        memChart = new Chart(memCtx, {
            type: "line",
            data: {
                labels: [],
                datasets: [{
                    label: "Memory Usage MB",
                    data: [],
                    borderColor: "#a855f7",
                    backgroundColor: "rgba(168, 85, 247, 0.15)",
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 1
                }]
            },
            options: chartDefaults
        });
    }
}


// ----------------------------------------
// FETCH PLATFORM CONFIGURATION
// ----------------------------------------

async function fetchPlatformConfig() {
    try {
        const response = await fetch("/api/config");
        if (!response.ok) return;

        const data = await response.json();
        if (data.status === "success" && data.grafana_url) {
            const grafanaLink = document.getElementById("grafanaLink");
            if (grafanaLink) {
                grafanaLink.href = data.grafana_url;
            }
        }
    } catch (err) {
        console.warn("Unable to fetch platform configuration:", err);
    }
}


// ----------------------------------------
// REFRESH SYSTEM METRICS
// ----------------------------------------

async function refreshDashboard() {
    const statusBadge = document.getElementById("statusBadge");

    try {
        const response = await fetch("/api/metrics");
        if (!response.ok) throw new Error("Metrics API returned " + response.status);

        const data = await response.json();
        if (data.status !== "success") throw new Error(data.message || "Metrics retrieval failed");

        document.getElementById("cpuValue").textContent = data.cpu_usage + "%";
        document.getElementById("cpuDetail").textContent = data.cpu_usage + "%";

        document.getElementById("memoryValue").textContent = data.memory_usage_mb + " MB";
        document.getElementById("memoryDetail").textContent = data.memory_usage_mb + " MB";

        document.getElementById("containerValue").textContent = data.containers;

        document.getElementById("systemStatus").textContent = "System Online";
        document.getElementById("healthStatus").textContent = "Prometheus connected";
        document.getElementById("lastUpdated").textContent = new Date().toLocaleTimeString();

        if (statusBadge) statusBadge.classList.remove("error");

    } catch (error) {
        console.error("Dashboard error:", error);

        document.getElementById("systemStatus").textContent = "Connection Error";
        document.getElementById("healthStatus").textContent = "Unable to connect to monitoring API";

        if (statusBadge) statusBadge.classList.add("error");
    }
}


// ----------------------------------------
// REFRESH HISTORICAL CHARTS
// ----------------------------------------

async function refreshCharts() {
    if (!cpuChart || !memChart) {
        initCharts();
        if (!cpuChart || !memChart) return;
    }

    try {
        const response = await fetch(`/api/metrics/history?minutes=${currentHistoryRange}&step=30s`);
        if (!response.ok) return;

        const data = await response.json();
        if (data.status !== "success") return;

        if (data.timestamps && data.timestamps.length > 0) {
            cpuChart.data.labels = data.timestamps;
            cpuChart.data.datasets[0].data = data.cpu;
            cpuChart.update();

            memChart.data.labels = data.timestamps;
            memChart.data.datasets[0].data = data.memory_mb;
            memChart.update();
        }
    } catch (error) {
        console.warn("Historical charts update error:", error);
    }
}


// ----------------------------------------
// REFRESH CONTAINER METRICS & STATUS
// ----------------------------------------

async function refreshContainers() {
    try {
        const response = await fetch("/api/containers");
        if (!response.ok) throw new Error("Containers API returned " + response.status);

        const data = await response.json();
        if (data.status !== "success") throw new Error(data.message);

        const table = document.getElementById("containerTable");
        const countBadge = document.getElementById("containerCountBadge");
        const containerSelect = document.getElementById("logContainerSelect");

        table.innerHTML = "";

        if (!data.containers || data.containers.length === 0) {
            table.innerHTML = '<tr><td colspan="6">No containers found</td></tr>';
            if (countBadge) countBadge.textContent = "0 Monitored";
            return;
        }

        const runningCount = data.containers.filter(c => (c.status || "").toLowerCase().startsWith("running")).length;
        if (countBadge) countBadge.textContent = `${runningCount} Running / ${data.containers.length} Total`;

        // Sync container select dropdown
        const existingOptions = new Set(
            Array.from(containerSelect?.options || []).map(o => o.value)
        );

        data.containers.forEach(container => {
            // Populate select dropdown
            if (containerSelect && !existingOptions.has(container.name)) {
                const opt = document.createElement("option");
                opt.value = container.name;
                opt.textContent = container.name;
                containerSelect.appendChild(opt);
            }

            const row = document.createElement("tr");

            // Name
            const nameCell = document.createElement("td");
            nameCell.innerHTML = `<strong>${escapeHtml(container.name)}</strong>`;

            // Status Badge
            const statusCell = document.createElement("td");
            const statusText = container.status || "Running";
            const statusLower = statusText.toLowerCase();

            let badgeClass = "badge-running";
            if (statusLower.includes("exited") || statusLower.includes("stopped")) {
                badgeClass = "badge-stopped";
            } else if (statusLower.includes("restarting") || statusLower.includes("paused")) {
                badgeClass = "badge-warning";
            }
            statusCell.innerHTML = `<span class="badge ${badgeClass}">${escapeHtml(statusText)}</span>`;

            // Uptime
            const uptimeCell = document.createElement("td");
            uptimeCell.textContent = container.uptime || "Active";

            // CPU
            const cpuCell = document.createElement("td");
            cpuCell.textContent = container.cpu_usage + "%";

            // Memory
            const memoryCell = document.createElement("td");
            memoryCell.textContent = container.memory_usage_mb + " MB";

            // Actions
            const actionCell = document.createElement("td");
            const filterBtn = document.createElement("button");
            filterBtn.className = "btn btn-sm btn-secondary";
            filterBtn.textContent = "Filter Logs";
            filterBtn.onclick = () => filterLogsForContainer(container.name);
            actionCell.appendChild(filterBtn);

            row.append(nameCell, statusCell, uptimeCell, cpuCell, memoryCell, actionCell);
            table.appendChild(row);
        });

    } catch (error) {
        console.error("Container error:", error);
        document.getElementById("containerTable").innerHTML =
            '<tr><td colspan="6">Unable to load container data</td></tr>';
    }
}


// ----------------------------------------
// REFRESH LIVE DOCKER LOGS WITH FILTERS
// ----------------------------------------

async function refreshLogs() {
    try {
        const containerVal = document.getElementById("logContainerSelect")?.value || "";
        const levelVal = document.getElementById("logLevelSelect")?.value || "";
        const searchVal = document.getElementById("logSearchInput")?.value?.trim() || "";

        const params = new URLSearchParams();
        if (containerVal) params.append("container", containerVal);
        if (levelVal) params.append("level", levelVal);
        if (searchVal) params.append("search", searchVal);
        params.append("limit", "100");

        const response = await fetch(`/api/logs?${params.toString()}`);
        if (!response.ok) throw new Error("Logs API returned " + response.status);

        const data = await response.json();
        if (data.status !== "success") throw new Error(data.message);

        const logContainer = document.getElementById("logContainer");
        logContainer.innerHTML = "";

        if (!data.logs || data.logs.length === 0) {
            logContainer.innerHTML = '<p class="empty-state">No matching logs found for the selected criteria</p>';
            return;
        }

        data.logs.forEach(log => {
            const logEntry = document.createElement("p");
            const msgLower = (log.message || "").toLowerCase();

            if (msgLower.includes("error") || msgLower.includes("exception") || msgLower.includes("fail")) {
                logEntry.className = "log-error";
            } else if (msgLower.includes("warn")) {
                logEntry.className = "log-warn";
            } else if (msgLower.includes("info")) {
                logEntry.className = "log-info";
            }

            logEntry.textContent = `[${log.timestamp}] [${log.container}] ${log.message}`;
            logContainer.appendChild(logEntry);
        });

        if (autoScrollEnabled) {
            logContainer.scrollTop = 0;
        }

    } catch (error) {
        console.error("Log error:", error);
        document.getElementById("logContainer").innerHTML =
            '<p class="log-error">Unable to load Docker logs from Loki</p>';
    }
}


// ----------------------------------------
// REFRESH ALERTS
// ----------------------------------------

async function refreshAlerts() {
    try {
        const response = await fetch("/api/alerts");
        if (!response.ok) return;

        const data = await response.json();
        const alertValue = document.getElementById("alertValue");
        const alertSummary = document.getElementById("alertSummary");
        const alertCard = document.getElementById("alertCard");
        const alertsContainer = document.getElementById("alertsContainer");
        const badge = document.getElementById("alertsCountBadge");

        const count = data.count || 0;
        if (alertValue) alertValue.textContent = count;
        if (badge) badge.textContent = `${count} Firing`;

        if (count > 0) {
            if (alertCard) alertCard.classList.add("alert-active");
            if (alertSummary) alertSummary.textContent = `${count} active firing alert(s)`;

            if (alertsContainer && data.alerts) {
                alertsContainer.innerHTML = "";
                data.alerts.forEach(alert => {
                    const item = document.createElement("div");
                    item.className = `alert-item ${alert.state === 'firing' ? 'firing' : ''}`;
                    item.innerHTML = `
                        <div class="alert-info">
                            <div class="alert-title">🚨 ${escapeHtml(alert.name)} (${escapeHtml(alert.container)})</div>
                            <div class="alert-desc">${escapeHtml(alert.summary)}</div>
                        </div>
                        <div class="alert-meta">
                            <span class="badge ${alert.severity === 'critical' ? 'badge-stopped' : 'badge-warning'}">${escapeHtml(alert.severity)}</span>
                            <div>${escapeHtml(alert.active_at || 'Active now')}</div>
                        </div>
                    `;
                    alertsContainer.appendChild(item);
                });
            }
        } else {
            if (alertCard) alertCard.classList.remove("alert-active");
            if (alertSummary) alertSummary.textContent = "All systems normal";
            if (alertsContainer) {
                alertsContainer.innerHTML = '<p class="empty-state">✅ All systems normal — No active firing alerts</p>';
            }
        }
    } catch (err) {
        console.warn("Alerts fetch error:", err);
    }
}


// ----------------------------------------
// HELPER FUNCTIONS & EVENT LISTENERS
// ----------------------------------------

function filterLogsForContainer(containerName) {
    const select = document.getElementById("logContainerSelect");
    if (select) {
        select.value = containerName;
        refreshLogs();
        document.getElementById("section-logs")?.scrollIntoView({ behavior: "smooth" });
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function setupEventListeners() {
    // Filter controls
    document.getElementById("applyLogFilterBtn")?.addEventListener("click", refreshLogs);
    document.getElementById("logSearchInput")?.addEventListener("keyup", (e) => {
        if (e.key === "Enter") refreshLogs();
    });
    document.getElementById("logContainerSelect")?.addEventListener("change", refreshLogs);
    document.getElementById("logLevelSelect")?.addEventListener("change", refreshLogs);

    document.getElementById("resetLogFilterBtn")?.addEventListener("click", () => {
        const select = document.getElementById("logContainerSelect");
        const level = document.getElementById("logLevelSelect");
        const search = document.getElementById("logSearchInput");
        if (select) select.value = "";
        if (level) level.value = "";
        if (search) search.value = "";
        refreshLogs();
    });

    // Auto-scroll toggle
    const toggleScrollBtn = document.getElementById("toggleAutoScrollBtn");
    toggleScrollBtn?.addEventListener("click", () => {
        autoScrollEnabled = !autoScrollEnabled;
        toggleScrollBtn.textContent = `Auto-scroll: ${autoScrollEnabled ? 'ON' : 'OFF'}`;
        toggleScrollBtn.className = `btn btn-sm ${autoScrollEnabled ? 'btn-active' : 'btn-secondary'}`;
    });

    // Clear logs button
    document.getElementById("clearLogsBtn")?.addEventListener("click", () => {
        const logContainer = document.getElementById("logContainer");
        if (logContainer) logContainer.innerHTML = '<p class="empty-state">View cleared</p>';
    });

    // Chart time-range controls
    document.querySelectorAll(".time-btn").forEach(btn => {
        btn.addEventListener("click", function() {
            document.querySelectorAll(".time-btn").forEach(b => b.classList.remove("active"));
            this.classList.add("active");
            currentHistoryRange = parseInt(this.getAttribute("data-minutes"), 10) || 30;
            refreshCharts();
        });
    });

    // Sidebar smooth navigation
    document.querySelectorAll(".sidebar .menu").forEach(link => {
        link.addEventListener("click", function() {
            if (this.classList.contains("grafana-menu")) return;
            document.querySelectorAll(".sidebar .menu").forEach(m => m.classList.remove("active"));
            this.classList.add("active");
            const targetId = this.getAttribute("data-target");
            if (targetId) {
                document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth" });
            }
        });
    });
}


// ----------------------------------------
// UPDATE ENTIRE DASHBOARD CYCLE
// ----------------------------------------

async function updateDashboard() {
    await Promise.all([
        refreshDashboard(),
        refreshCharts(),
        refreshContainers(),
        refreshLogs(),
        refreshAlerts()
    ]);
}

// Initial Run
window.addEventListener("DOMContentLoaded", () => {
    initCharts();
    fetchPlatformConfig();
    setupEventListeners();
    updateDashboard();
    setInterval(updateDashboard, 5000);
});
