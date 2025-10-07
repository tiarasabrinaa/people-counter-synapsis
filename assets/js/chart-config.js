// /Users/tiarasabrina/Documents/PROJECT/dashboard-people-counter/assets/js/chart-config.js

/**
 * Chart Configurations for People Counting Dashboard
 * Uses Chart.js for data visualization
 */

class ChartManager {
    constructor() {
        this.charts = {};
    }

    /**
     * Create or update Entry/Exit bar chart
     */
    /**
 * Create Entry/Exit LINE chart (not bar)
 */
    createEntryExitChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

        // Prepare data
        const labels = data.map(item => {
            const date = new Date(item.hour);
            return date.getHours() + ':00';
        });

        const entryData = data.map(item => item.entry_count);
        const exitData = data.map(item => item.exit_count);

        // Create LINE chart
        this.charts[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Entry',
                        data: entryData,
                        borderColor: 'rgb(52, 211, 153)',
                        backgroundColor: 'rgba(52, 211, 153, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: 'rgb(52, 211, 153)',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2
                    },
                    {
                        label: 'Exit',
                        data: exitData,
                        borderColor: 'rgb(239, 68, 68)',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: 'rgb(239, 68, 68)',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#fff',
                            font: {
                                family: 'Inter',
                                size: 12
                            },
                            padding: 15,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        displayColors: true
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: '#fff',
                            font: {
                                family: 'Inter',
                                size: 11
                            }
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)',
                            drawBorder: false
                        }
                    },
                    x: {
                        ticks: {
                            color: '#fff',
                            font: {
                                family: 'Inter',
                                size: 11
                            }
                        },
                        grid: {
                            display: false
                        }
                    }
                },
                interaction: {
                    mode: 'index',
                    intersect: false
                }
            }
        });

        return this.charts[canvasId];
    }

    /**
     * Create Net Count line chart
     */
    createNetCountChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

        const labels = data.map(item => {
            const date = new Date(item.hour);
            return date.getHours() + ':00';
        });

        const netData = data.map(item => item.net_count);

        this.charts[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Net Count',
                    data: netData,
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    borderColor: 'rgb(99, 102, 241)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    pointBackgroundColor: 'rgb(99, 102, 241)',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {                                     // >>> tambahkan ini
                    padding: { left: 6, right: 4, top: 6, bottom: 6 }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleColor: '#fff',
                        bodyColor: '#fff'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: 'rgba(0, 0, 0, 0.5)',
                            font: {
                                family: 'Inter',
                                size: 10
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)',
                            drawBorder: false
                        }
                    },
                    x: {
                        ticks: {
                            color: 'rgba(0, 0, 0, 0.5)',
                            font: {
                                family: 'Inter',
                                size: 10
                            }
                        },
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });

        return this.charts[canvasId];
    }

    /**
     * Create forecast chart
     */
    createForecastChart(canvasId, forecastData) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

        const labels = forecastData.map(item => {
            const date = new Date(item.timestamp);
            return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`;
        });

        const predicted = forecastData.map(item => item.predicted_count);
        const lowerBound = forecastData.map(item => item.lower_bound);
        const upperBound = forecastData.map(item => item.upper_bound);

        this.charts[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Predicted',
                        data: predicted,
                        borderColor: 'rgb(59, 130, 246)',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 3,
                        fill: false,
                        tension: 0.4
                    },
                    {
                        label: 'Upper Bound',
                        data: upperBound,
                        borderColor: 'rgba(59, 130, 246, 0.3)',
                        borderDash: [5, 5],
                        borderWidth: 1,
                        fill: '+1',
                        backgroundColor: 'rgba(59, 130, 246, 0.05)',
                        tension: 0.4,
                        pointRadius: 0
                    },
                    {
                        label: 'Lower Bound',
                        data: lowerBound,
                        borderColor: 'rgba(59, 130, 246, 0.3)',
                        borderDash: [5, 5],
                        borderWidth: 1,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });

        return this.charts[canvasId];
    }

    /**
     * Destroy all charts
     */
    destroyAll() {
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = {};
    }
}

// Export singleton
const chartManager = new ChartManager();