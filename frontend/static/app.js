/**
 * PolarGrid AI - Dashboard JavaScript
 * Handles data fetching, chart rendering, and UI interactions
 */

// ===== CONFIGURATION =====
const UPDATE_INTERVAL = 30000; // 30 seconds

// Detect API base URL dynamically
const API_BASE = window.location.origin;
console.log('PolarGrid AI - API Base:', API_BASE);

// ===== CHART DEFAULTS =====
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Segoe UI', -apple-system, sans-serif";
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.padding = 20;

// ===== GLOBAL CHART INSTANCES =====
let charts = {};

// ===== COLOR PALETTE =====
const COLORS = {
    blue: '#00d4ff',
    cyan: '#06b6d4',
    purple: '#8b5cf6',
    green: '#10b981',
    orange: '#f59e0b',
    red: '#ef4444',
    solar: '#fbbf24',
    wind: '#06b6d4',
    battery: '#8b5cf6',
    generator: '#ef4444',
    demand: '#00d4ff',
    muted: '#475569'
};

// ===== UTILITY FUNCTIONS =====
function formatNumber(num, decimals = 0) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toFixed(decimals);
}

function animateValue(element, start, end, duration, suffix = '') {
    const startTime = performance.now();
    const update = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease out cubic
        const current = start + (end - start) * eased;
        element.textContent = formatNumber(current, suffix === '%' ? 1 : 0) + suffix;
        if (progress < 1) requestAnimationFrame(update);
    };
    requestAnimationFrame(update);
}

// ===== API FUNCTIONS =====
async function fetchDashboardData(station) {
    try {
        const url = `/api/dashboard?station=${encodeURIComponent(station)}&hours_ahead=168`;
        console.log('Fetching:', url);
        const response = await fetch(url);
        if (!response.ok) {
            console.error('API Error:', response.status, response.statusText);
            const errorText = await response.text();
            console.error('Error details:', errorText);
            throw new Error(`API returned ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Dashboard fetch error:', error);
        showError('Failed to load dashboard data. Check console for details.');
        return null;
    }
}

async function fetchModelPerformance() {
    try {
        const response = await fetch('/api/model-performance');
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Model performance fetch error:', error);
        return null;
    }
}

async function fetchWeatherImpact() {
    try {
        const response = await fetch('/api/weather-impact');
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Weather impact fetch error:', error);
        return null;
    }
}

async function fetchAnnualSummary(station) {
    try {
        const url = `/api/annual-summary?station=${encodeURIComponent(station)}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Annual summary fetch error:', error);
        return null;
    }
}

function showError(message) {
    console.error('Dashboard Error:', message);
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.innerHTML = `
            <div class="loading-logo" style="color: var(--accent-red);">️ Error</div>
            <p style="color: var(--text-secondary); margin-top: 1rem;">${message}</p>
            <p style="color: var(--text-muted); margin-top: 0.5rem; font-size: 0.8rem;">
                Make sure the server is running: python backend/main.py
            </p>
        `;
        overlay.classList.remove('hidden');
    }
}

// ===== CHART CREATION FUNCTIONS =====
function createDemandForecastChart(data) {
    const ctx = document.getElementById('demandForecastChart');
    if (!ctx) return;

    if (charts.demand) charts.demand.destroy();

    // Combine recent data and forecast
    const recentLabels = data.recent_data.timestamps;
    const forecastLabels = data.forecast.timestamps;
    const allLabels = [...recentLabels, ...forecastLabels];

    const recentDemand = data.recent_data.demand;
    const predictedDemand = data.forecast.demand_predicted;
    const ciLower = data.forecast.ci_lower;
    const ciUpper = data.forecast.ci_upper;
    const actualForecast = data.forecast.demand_actual;

    charts.demand = new Chart(ctx, {
        type: 'line',
        data: {
            labels: allLabels,
            datasets: [
                {
                    label: 'Actual Load (Recent)',
                    data: [...recentDemand, ...Array(forecastLabels.length).fill(null)],
                    borderColor: COLORS.blue,
                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    pointRadius: 0,
                    fill: false
                },
                {
                    label: 'AI Prediction (Forecast)',
                    data: [...Array(recentLabels.length).fill(null), ...predictedDemand],
                    borderColor: COLORS.purple,
                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.3,
                    pointRadius: 0,
                    fill: false
                },
                {
                    label: '95% Confidence (Upper)',
                    data: [...Array(recentLabels.length).fill(null), ...ciUpper],
                    borderColor: 'transparent',
                    backgroundColor: 'rgba(139, 92, 246, 0.08)',
                    borderWidth: 0,
                    pointRadius: 0,
                    fill: '+1',
                    tension: 0.3
                },
                {
                    label: '95% Confidence (Lower)',
                    data: [...Array(recentLabels.length).fill(null), ...ciLower],
                    borderColor: 'transparent',
                    backgroundColor: 'transparent',
                    borderWidth: 0,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.3
                },
                {
                    label: 'True Demand (Validation)',
                    data: [...Array(recentLabels.length).fill(null), ...actualForecast],
                    borderColor: COLORS.green,
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    tension: 0.3,
                    pointRadius: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { font: { size: 11 } } },
                tooltip: {
                    backgroundColor: 'rgba(26, 34, 53, 0.95)',
                    borderColor: COLORS.border,
                    borderWidth: 1,
                    titleColor: COLORS.blue,
                    bodyColor: '#f1f5f9',
                    padding: 12,
                    callbacks: {
                        label: function(ctx) {
                            if (ctx.parsed.y === null) return null;
                            return `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)} kW`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 12, font: { size: 10 } },
                    grid: { color: 'rgba(42, 58, 92, 0.3)' }
                },
                y: {
                    title: { display: true, text: 'Power (kW)' },
                    grid: { color: 'rgba(42, 58, 92, 0.3)' },
                    beginAtZero: false
                }
            }
        }
    });
}

function createRenewableForecastChart(data) {
    const ctx = document.getElementById('renewableForecastChart');
    if (!ctx) return;

    if (charts.renewable) charts.renewable.destroy();

    const forecastLabels = data.forecast.timestamps;
    const solarPredicted = data.forecast.solar_predicted;
    const windPredicted = data.forecast.wind_predicted;
    const temperature = data.forecast.temperature;

    charts.renewable = new Chart(ctx, {
        type: 'line',
        data: {
            labels: forecastLabels,
            datasets: [
                {
                    label: 'Solar Generation (Predicted)',
                    data: solarPredicted,
                    borderColor: COLORS.solar,
                    backgroundColor: 'rgba(251, 191, 36, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    pointRadius: 0,
                    fill: true,
                    yAxisID: 'y'
                },
                {
                    label: 'Wind Generation (Predicted)',
                    data: windPredicted,
                    borderColor: COLORS.wind,
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    pointRadius: 0,
                    fill: true,
                    yAxisID: 'y'
                },
                {
                    label: 'Temperature (°C)',
                    data: temperature,
                    borderColor: COLORS.red,
                    backgroundColor: 'transparent',
                    borderWidth: 1,
                    borderDash: [3, 3],
                    tension: 0.4,
                    pointRadius: 0,
                    fill: false,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { font: { size: 11 } } },
                tooltip: {
                    backgroundColor: 'rgba(26, 34, 53, 0.95)',
                    padding: 12
                }
            },
            scales: {
                x: { ticks: { maxTicksLimit: 12, font: { size: 10 } }, grid: { color: 'rgba(42, 58, 92, 0.3)' } },
                y: {
                    title: { display: true, text: 'Power (kW)' },
                    grid: { color: 'rgba(42, 58, 92, 0.3)' },
                    beginAtZero: true
                },
                y1: {
                    position: 'right',
                    title: { display: true, text: 'Temperature (°C)' },
                    grid: { drawOnChartArea: false }
                }
            }
        }
    });
}

function createDispatchChart(data) {
    const ctx = document.getElementById('dispatchChart');
    if (!ctx) return;

    if (charts.dispatch) charts.dispatch.destroy();

    const dispatch = data.dispatch;
    const labels = dispatch.timestamps.slice(0, 168);

    charts.dispatch = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Demand',
                    data: dispatch.demand,
                    backgroundColor: 'rgba(0, 212, 255, 0.3)',
                    borderColor: COLORS.demand,
                    borderWidth: 1,
                    order: 4
                },
                {
                    label: 'Solar',
                    data: dispatch.solar,
                    backgroundColor: 'rgba(251, 191, 36, 0.7)',
                    borderColor: COLORS.solar,
                    borderWidth: 0,
                    order: 3
                },
                {
                    label: 'Wind',
                    data: dispatch.wind,
                    backgroundColor: 'rgba(6, 182, 212, 0.7)',
                    borderColor: COLORS.wind,
                    borderWidth: 0,
                    order: 2
                },
                {
                    label: 'Generator',
                    data: dispatch.generator,
                    backgroundColor: 'rgba(239, 68, 68, 0.7)',
                    borderColor: COLORS.generator,
                    borderWidth: 0,
                    order: 1
                },
                {
                    label: 'Battery SoC (%)',
                    data: dispatch.soc,
                    type: 'line',
                    borderColor: COLORS.purple,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    tension: 0.3,
                    pointRadius: 0,
                    yAxisID: 'y1',
                    order: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { font: { size: 11 } } },
                tooltip: { backgroundColor: 'rgba(26, 34, 53, 0.95)', padding: 12 }
            },
            scales: {
                x: {
                    stacked: true,
                    ticks: { maxTicksLimit: 12, font: { size: 10 } },
                    grid: { color: 'rgba(42, 58, 92, 0.3)' }
                },
                y: {
                    stacked: true,
                    title: { display: true, text: 'Power (kW)' },
                    grid: { color: 'rgba(42, 58, 92, 0.3)' },
                    beginAtZero: true
                },
                y1: {
                    position: 'right',
                    title: { display: true, text: 'Battery SoC (%)' },
                    grid: { drawOnChartArea: false },
                    min: 0,
                    max: 100
                }
            }
        }
    });
}

function createWeatherDemandChart(data) {
    const ctx = document.getElementById('weatherDemandChart');
    if (!ctx) return;

    if (charts.weatherDemand) charts.weatherDemand.destroy();

    const months = data.monthly_trends.months;
    const temp = data.monthly_trends.temperature;
    const demand = data.monthly_trends.avg_demand;

    charts.weatherDemand = new Chart(ctx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [
                {
                    label: 'Temperature (°C)',
                    data: temp,
                    borderColor: COLORS.red,
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                    yAxisID: 'y'
                },
                {
                    label: 'Avg Demand (kW)',
                    data: demand,
                    borderColor: COLORS.blue,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top' },
                tooltip: { backgroundColor: 'rgba(26, 34, 53, 0.95)', padding: 12 }
            },
            scales: {
                x: { ticks: { font: { size: 10 }, maxRotation: 45 }, grid: { color: 'rgba(42, 58, 92, 0.3)' } },
                y: { title: { display: true, text: 'Temperature (°C)' }, grid: { color: 'rgba(42, 58, 92, 0.3)' } },
                y1: { position: 'right', title: { display: true, text: 'Demand (kW)' }, grid: { drawOnChartArea: false } }
            }
        }
    });
}

function createSolarMonthlyChart(data) {
    const ctx = document.getElementById('solarMonthlyChart');
    if (!ctx) return;

    if (charts.solarMonthly) charts.solarMonthly.destroy();

    const months = data.monthly_trends.months;
    const solar = data.monthly_trends.solar_generation;
    const wind = data.monthly_trends.wind_generation;

    charts.solarMonthly = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: months,
            datasets: [
                {
                    label: 'Solar Generation (kWh)',
                    data: solar,
                    backgroundColor: 'rgba(251, 191, 36, 0.7)',
                    borderColor: COLORS.solar,
                    borderWidth: 1
                },
                {
                    label: 'Wind Generation (kWh)',
                    data: wind,
                    backgroundColor: 'rgba(6, 182, 212, 0.7)',
                    borderColor: COLORS.wind,
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top' },
                tooltip: { backgroundColor: 'rgba(26, 34, 53, 0.95)', padding: 12 }
            },
            scales: {
                x: { ticks: { font: { size: 10 }, maxRotation: 45 }, grid: { color: 'rgba(42, 58, 92, 0.3)' } },
                y: { title: { display: true, text: 'Generation (kWh)' }, grid: { color: 'rgba(42, 58, 92, 0.3)' }, beginAtZero: true }
            }
        }
    });
}

function createMonthlyTrendsChart(data) {
    const ctx = document.getElementById('monthlyTrendsChart');
    if (!ctx) return;

    if (charts.monthlyTrends) charts.monthlyTrends.destroy();

    const months = data.monthly_trends.months;
    const diesel = data.monthly_trends.diesel_consumption;

    charts.monthlyTrends = new Chart(ctx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [
                {
                    label: 'Diesel Consumption (Liters)',
                    data: diesel,
                    borderColor: COLORS.orange,
                    backgroundColor: 'rgba(245, 158, 11, 0.15)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top' },
                tooltip: { backgroundColor: 'rgba(26, 34, 53, 0.95)', padding: 12 }
            },
            scales: {
                x: { ticks: { font: { size: 10 }, maxRotation: 45 }, grid: { color: 'rgba(42, 58, 92, 0.3)' } },
                y: { title: { display: true, text: 'Diesel (Liters)' }, grid: { color: 'rgba(42, 58, 92, 0.3)' }, beginAtZero: true }
            }
        }
    });
}

function createFeatureImportanceChart(data) {
    const ctx = document.getElementById('featureImportanceChart');
    if (!ctx) return;

    if (charts.featureImportance) charts.featureImportance.destroy();

    const features = data.feature_importance;
    const labels = features.map(f => f.feature.replace(/_/g, ' '));
    const importance = features.map(f => f.importance);

    charts.featureImportance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Importance Score',
                data: importance,
                backgroundColor: 'rgba(0, 212, 255, 0.6)',
                borderColor: COLORS.blue,
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { backgroundColor: 'rgba(26, 34, 53, 0.95)', padding: 12 }
            },
            scales: {
                x: { title: { display: true, text: 'Feature Importance' }, grid: { color: 'rgba(42, 58, 92, 0.3)' } },
                y: { ticks: { font: { size: 10 } }, grid: { color: 'rgba(42, 58, 92, 0.3)' } }
            }
        }
    });
}

function createModelPerformanceChart(data) {
    const ctx = document.getElementById('modelPerformanceChart');
    if (!ctx) return;

    if (charts.modelPerformance) charts.modelPerformance.destroy();

    const models = ['XGBoost', 'Random Forest', 'Gradient Boosting', 'Ensemble'];
    const maeValues = [
        data.load_forecasting.xgboost.mae,
        data.load_forecasting.random_forest.mae,
        data.load_forecasting.gradient_boosting.mae,
        data.load_forecasting.ensemble.mae
    ];
    const r2Values = [
        data.load_forecasting.xgboost.r2,
        data.load_forecasting.random_forest.r2,
        data.load_forecasting.gradient_boosting.r2,
        data.load_forecasting.ensemble.r2
    ];

    charts.modelPerformance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: models,
            datasets: [
                {
                    label: 'MAE (kW) — Lower is Better',
                    data: maeValues,
                    backgroundColor: 'rgba(139, 92, 246, 0.6)',
                    borderColor: COLORS.purple,
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'R² Score — Higher is Better',
                    data: r2Values,
                    backgroundColor: 'rgba(16, 185, 129, 0.6)',
                    borderColor: COLORS.green,
                    borderWidth: 1,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top' },
                tooltip: { backgroundColor: 'rgba(26, 34, 53, 0.95)', padding: 12 }
            },
            scales: {
                x: { grid: { color: 'rgba(42, 58, 92, 0.3)' } },
                y: { title: { display: true, text: 'MAE (kW)' }, grid: { color: 'rgba(42, 58, 92, 0.3)' }, beginAtZero: true },
                y1: { position: 'right', title: { display: true, text: 'R²' }, grid: { drawOnChartArea: false }, min: 0, max: 1.1 }
            }
        }
    });
}

// ===== UI UPDATE FUNCTIONS =====
function updateKPIs(data) {
    const recent = data.recent_data;
    const n = recent.demand.length;

    // Current values (last hour)
    const currentDemand = recent.demand[n - 1];
    const currentSolar = recent.solar[n - 1];
    const currentWind = recent.wind[n - 1];
    const currentBattery = recent.battery_soc[n - 1];
    const currentGenerator = recent.generator[n - 1];

    // 24h diesel consumption
    const diesel24h = recent.diesel.slice(-24).reduce((a, b) => a + b, 0);

    animateValue(document.getElementById('kpiDemand'), 0, currentDemand, 1000, ' kW');
    animateValue(document.getElementById('kpiSolar'), 0, currentSolar, 1000, ' kW');
    animateValue(document.getElementById('kpiWind'), 0, currentWind, 1000, ' kW');
    animateValue(document.getElementById('kpiBattery'), 0, currentBattery, 1000, '%');
    animateValue(document.getElementById('kpiGenerator'), 0, currentGenerator, 1000, ' kW');
    animateValue(document.getElementById('kpiDiesel'), 0, diesel24h, 1000, ' L');

    // Changes
    const demandChange = ((currentDemand - recent.demand[n - 2]) / recent.demand[n - 2] * 100).toFixed(1);
    document.getElementById('kpiDemandChange').textContent = `${demandChange > 0 ? '+' : ''}${demandChange}% vs 1h ago`;
    document.getElementById('kpiDemandChange').className = `kpi-change ${demandChange > 0 ? 'negative' : 'positive'}`;

    // Timestamp
    document.getElementById('updateTimestamp').textContent = `Updated: ${new Date().toLocaleTimeString('en-IN')}`;
}

function updateInsights(data) {
    const container = document.getElementById('insightsContainer');
    if (!container) return;

    container.innerHTML = '';
    if (data.insights && data.insights.length > 0) {
        data.insights.forEach(insight => {
            const div = document.createElement('div');
            div.className = 'insight-item';
            div.textContent = insight;
            container.appendChild(div);
        });
    }
}

function updateSummaryKPIs(data) {
    const summary = data.summary;
    if (!summary) return;

    document.getElementById('sumCostSavings').textContent = `₹${formatNumber(summary.cost_savings_rs)}`;
    document.getElementById('sumFuelSavings').textContent = `${formatNumber(summary.fuel_savings_liters)} L`;
    document.getElementById('sumCO2').textContent = `${formatNumber(summary.co2_reduction_kg)} kg`;
    document.getElementById('sumRenewable').textContent = `${summary.renewable_share}%`;
}

function updateAnnualKPIs(data) {
    const metrics = data.annual_metrics;
    if (!metrics) return;

    document.getElementById('annualDemand').textContent = `${(metrics.total_demand_kwh / 1000).toFixed(1)} MWh`;
    document.getElementById('annualSolar').textContent = `${(metrics.solar_generation_kwh / 1000).toFixed(1)} MWh`;
    document.getElementById('annualWind').textContent = `${(metrics.wind_generation_kwh / 1000).toFixed(1)} MWh`;
    document.getElementById('annualDiesel').textContent = `${(metrics.diesel_consumption_liters / 1000).toFixed(1)} kL`;
    document.getElementById('annualCO2').textContent = `${metrics.co2_emissions_tonnes} t`;
    document.getElementById('annualCost').textContent = `₹${(metrics.diesel_cost_rs / 100000).toFixed(1)} L`;
}

function updateResupplyPlan(data) {
    const container = document.getElementById('resupplyTimeline');
    if (!container || !data.resupply_plan) return;

    container.innerHTML = '';
    data.resupply_plan.resupply_events.forEach(event => {
        const div = document.createElement('div');
        div.className = 'resupply-event';
        div.innerHTML = `
            <div class="event-month">${event.month_name}</div>
            <div class="event-amount">${formatNumber(event.fuel_liters)} L</div>
            <div class="event-label">${event.window}</div>
            <div class="event-rationale">${event.rationale}</div>
        `;
        container.appendChild(div);
    });
}

function updateWeatherInsights(data) {
    const container = document.getElementById('weatherInsightsContainer');
    if (!container) return;

    container.innerHTML = '';
    if (data.insights) {
        data.insights.forEach(insight => {
            const div = document.createElement('div');
            div.className = 'insight-item';
            div.textContent = insight;
            container.appendChild(div);
        });
    }

    // Add correlation info
    if (data.correlations) {
        const corrDiv = document.createElement('div');
        corrDiv.className = 'insight-item';
        corrDiv.innerHTML = `<strong>Correlations:</strong> Temp→Demand: ${data.correlations.temperature_vs_demand} | Wind→Gen: ${data.correlations.wind_speed_vs_generation} | Solar: ${data.correlations.irradiance_vs_solar_gen}`;
        container.appendChild(corrDiv);
    }
}

function updateImpactInsights(data) {
    const container = document.getElementById('impactInsightsContainer');
    if (!container || !data.impact_vs_traditional) return;

    container.innerHTML = '';
    const impact = data.impact_vs_traditional;
    const items = [
        `⛽ ${formatNumber(impact.fuel_saved_liters)} liters diesel saved annually vs. diesel-only baseline`,
        `💰 ₹${formatNumber(impact.cost_saved_rs)} saved per year in fuel costs`,
        `🌍 ${impact.co2_avoided_tonnes} tonnes CO₂ emissions avoided annually`,
        `📊 ${data.kpis.renewable_penetration} renewable energy penetration achieved through AI optimization`
    ];
    items.forEach(text => {
        const div = document.createElement('div');
        div.className = 'insight-item';
        div.textContent = text;
        container.appendChild(div);
    });
}

function updateArchitectureInfo(data) {
    const container = document.getElementById('architectureInfo');
    if (!container) return;

    container.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
            <div>
                <h4 style="color: var(--accent-blue); margin-bottom: 0.5rem;">ML Architecture</h4>
                <p><strong>Load Forecasting:</strong> Hybrid Ensemble Model</p>
                <ul style="margin-left: 1.5rem; margin-top: 0.3rem;">
                    <li>XGBoost (weight: 45%) — handles non-linear patterns</li>
                    <li>Random Forest (weight: 25%) — robust to outliers</li>
                    <li>Gradient Boosting (weight: 30%) — sequential learning</li>
                </ul>
                <p style="margin-top: 0.5rem;"><strong>Features:</strong> ${data.load_forecasting.sample_size || 'N/A'} training samples</p>
                <p><strong>Test MAE:</strong> ${data.load_forecasting.ensemble.mae.toFixed(2)} kW | R²: ${data.load_forecasting.ensemble.r2.toFixed(4)}</p>
            </div>
            <div>
                <h4 style="color: var(--accent-purple); margin-bottom: 0.5rem;">Optimization Engine</h4>
                <p><strong>Method:</strong> Hybrid MILP + Rule-based RL</p>
                <ul style="margin-left: 1.5rem; margin-top: 0.3rem;">
                    <li>Operating modes: Normal, Polar Night, Blizzard, Summer Surge, Emergency</li>
                    <li>Battery management: 20-90% SoC safe zone</li>
                    <li>Generator min-load constraint: 30% for efficiency</li>
                    <li>Critical load protection (150 kW baseline)</li>
                </ul>
                <p style="margin-top: 0.5rem;"><strong>Stations:</strong> Maitri, Bharati (Antarctica), Himadri (Arctic)</p>
                <p><strong>Theme:</strong> Clean & Green Technology</p>
            </div>
        </div>
    `;
}

// ===== MAIN UPDATE FUNCTION =====
async function updateDashboard(station) {
    try {
        const [dashboardData, modelData, weatherData, annualData, modeData] = await Promise.all([
            fetchDashboardData(station),
            fetchModelPerformance(),
            fetchWeatherImpact(),
            fetchAnnualSummary(station),
            fetchCurrentMode(station)
        ]);

        if (modeData) updateCurrentModeCard(modeData);

        if (dashboardData) {
            updateKPIs(dashboardData);
            createDemandForecastChart(dashboardData);
            createRenewableForecastChart(dashboardData);
            createDispatchChart(dashboardData);
            updateInsights(dashboardData);
            updateSummaryKPIs(dashboardData);
        }

        if (weatherData) {
            createWeatherDemandChart(weatherData);
            createSolarMonthlyChart(weatherData);
            createMonthlyTrendsChart(weatherData);
            updateWeatherInsights(weatherData);
        }

        if (annualData) {
            updateAnnualKPIs(annualData);
            updateResupplyPlan(annualData);
            updateImpactInsights(annualData);
        }

        if (modelData) {
            createFeatureImportanceChart(modelData);
            createModelPerformanceChart(modelData);
            updateArchitectureInfo(modelData);
        }
    } catch (error) {
        console.error('Dashboard update error:', error);
    }
}

// ===== TAB HANDLING =====
function setupTabs() {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active from all tabs
            tabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            // Activate clicked tab
            tab.classList.add('active');
            const tabId = `tab-${tab.dataset.tab}`;
            document.getElementById(tabId).classList.add('active');
        });
    });
}

// ===== STATION SELECTOR =====
function setupStationSelector() {
    const selector = document.getElementById('stationSelector');
    selector.addEventListener('change', async () => {
        await updateDashboard(selector.value);
    });
}

// ===== CURRENT MODE FUNCTIONS =====
async function fetchCurrentMode(station) {
    try {
        const response = await fetch(`/api/current-mode?station=${encodeURIComponent(station)}`);
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Current mode fetch error:', error);
        return null;
    }
}

async function simulateMode(station, mode, hours) {
    try {
        const response = await fetch(`/api/simulate-mode?station=${encodeURIComponent(station)}&mode=${mode}&hours_ahead=${hours}`, {
            method: 'POST'
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Simulation error:', error);
        return null;
    }
}

function updateCurrentModeCard(data) {
    if (!data) return;

    const icon = document.getElementById('modeIcon');
    const value = document.getElementById('modeValue');
    const desc = document.getElementById('modeDesc');

    icon.textContent = data.mode_icon;
    value.textContent = data.mode_label;
    value.style.color = data.mode_color;
    desc.textContent = data.mode_description;

    // Update card border color
    const card = document.getElementById('currentModeCard');
    card.style.borderLeftColor = data.mode_color;

    // Update conditions
    document.getElementById('condTemp').textContent = `${data.conditions.temperature}°C`;
    document.getElementById('condWind').textContent = `${data.conditions.wind_speed} m/s`;
    document.getElementById('condSolar').textContent = `${data.conditions.solar_kw} kW`;
    document.getElementById('condSoc').textContent = `${data.conditions.battery_soc}%`;
}

function createSimDispatchChart(data) {
    const ctx = document.getElementById('simDispatchChart');
    if (!ctx) return;

    if (charts.simDispatch) charts.simDispatch.destroy();

    const labels = data.dispatch.timestamps;
    const dispatch = data.dispatch;

    charts.simDispatch = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Demand',
                    data: dispatch.demand,
                    backgroundColor: 'rgba(0, 212, 255, 0.3)',
                    borderColor: COLORS.demand,
                    borderWidth: 1,
                    order: 4
                },
                {
                    label: 'Solar',
                    data: dispatch.solar,
                    backgroundColor: 'rgba(251, 191, 36, 0.7)',
                    borderColor: COLORS.solar,
                    borderWidth: 0,
                    order: 3
                },
                {
                    label: 'Wind',
                    data: dispatch.wind,
                    backgroundColor: 'rgba(6, 182, 212, 0.7)',
                    borderColor: COLORS.wind,
                    borderWidth: 0,
                    order: 2
                },
                {
                    label: 'Generator',
                    data: dispatch.generator,
                    backgroundColor: 'rgba(239, 68, 68, 0.7)',
                    borderColor: COLORS.generator,
                    borderWidth: 0,
                    order: 1
                },
                {
                    label: 'Battery SoC (%)',
                    data: dispatch.soc,
                    type: 'line',
                    borderColor: COLORS.purple,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    tension: 0.3,
                    pointRadius: 0,
                    yAxisID: 'y1',
                    order: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { font: { size: 11 } } },
                tooltip: { backgroundColor: 'rgba(26, 34, 53, 0.95)', padding: 12 }
            },
            scales: {
                x: { stacked: true, ticks: { maxTicksLimit: 12, font: { size: 10 } }, grid: { color: 'rgba(42, 58, 92, 0.3)' } },
                y: { stacked: true, title: { display: true, text: 'Power (kW)' }, grid: { color: 'rgba(42, 58, 92, 0.3)' }, beginAtZero: true },
                y1: { position: 'right', title: { display: true, text: 'Battery SoC (%)' }, grid: { drawOnChartArea: false }, min: 0, max: 100 }
            }
        }
    });
}

function updateSimulationUI(data) {
    if (!data) return;

    // Update conditions display
    document.getElementById('scTemp').textContent = `${data.conditions.temperature}°C`;
    document.getElementById('scWind').textContent = `${data.conditions.wind_speed} m/s`;
    document.getElementById('scSolar').textContent = `${(data.conditions.solar_factor * 100).toFixed(0)}%`;
    document.getElementById('scSoc').textContent = `${data.conditions.start_soc}%`;

    // Update KPIs
    const summary = data.summary;
    document.getElementById('simDiesel').textContent = `${formatNumber(summary.total_diesel_liters)} L`;
    document.getElementById('simCost').textContent = `${formatNumber(summary.total_cost_rs)}`;
    document.getElementById('simCO2').textContent = `${formatNumber(summary.total_co2_kg)} kg`;
    document.getElementById('simRenew').textContent = `${summary.renewable_share}%`;

    // Create chart
    createSimDispatchChart(data);

    // Update insights
    const container = document.getElementById('simInsightsContainer');
    if (container && data.insights) {
        container.innerHTML = '';
        data.insights.forEach(insight => {
            const div = document.createElement('div');
            div.className = 'insight-item';
            div.textContent = insight;
            container.appendChild(div);
        });
    }
}

function setupSimulationTab() {
    let selectedMode = 'normal';

    // Mode button clicks
    const modeBtns = document.querySelectorAll('.mode-btn');
    modeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modeBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedMode = btn.dataset.mode;
        });
    });

    // Run simulation button
    const runBtn = document.getElementById('runSimBtn');
    if (runBtn) {
        runBtn.addEventListener('click', async () => {
            runBtn.disabled = true;
            runBtn.textContent = '⏳ Running...';

            const station = document.getElementById('stationSelector').value;
            const hours = parseInt(document.getElementById('simHours').value);

            const result = await simulateMode(station, selectedMode, hours);

            if (result) {
                updateSimulationUI(result);
            } else {
                alert('Simulation failed. Check console for details.');
            }

            runBtn.disabled = false;
            runBtn.textContent = ' Run Simulation';
        });
    }
}

// ===== INITIALIZATION =====
async function init() {
    // Setup UI
    setupTabs();
    setupStationSelector();
    setupSimulationTab();

    // Initial data load
    const station = document.getElementById('stationSelector').value;
    await updateDashboard(station);

    // Hide loading screen
    setTimeout(() => {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }, 1500);

    // Auto-refresh (includes current mode)
    setInterval(async () => {
        const currentStation = document.getElementById('stationSelector').value;
        await updateDashboard(currentStation);
    }, UPDATE_INTERVAL);
}

// Start the dashboard
document.addEventListener('DOMContentLoaded', init);
