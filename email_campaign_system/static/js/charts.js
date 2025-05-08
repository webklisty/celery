// Global chart instances
let dailyStatsChart = null;
let campaignStatsChart = null;

// Initialize daily stats chart
function initDailyStatsChart(data) {
    const ctx = document.getElementById('dailyStatsChart').getContext('2d');
    
    dailyStatsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'Sent',
                    data: data.sent,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Errors',
                    data: data.errors,
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

// Update daily stats chart with new data
function updateDailyStatsChart(data) {
    if (dailyStatsChart) {
        dailyStatsChart.data.labels = data.labels;
        dailyStatsChart.data.datasets[0].data = data.sent;
        dailyStatsChart.data.datasets[1].data = data.errors;
        dailyStatsChart.update();
    }
}

// Initialize or update campaign stats chart
function updateCampaignStatsChart(data) {
    const ctx = document.getElementById('campaignStatsChart').getContext('2d');
    
    // Destroy previous chart if it exists
    if (campaignStatsChart) {
        campaignStatsChart.destroy();
    }
    
    // Create new chart
    campaignStatsChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Sent', 'Errors', 'Remaining'],
            datasets: [{
                data: [data.sent, data.errors, data.remaining],
                backgroundColor: ['#0d6efd', '#dc3545', '#6c757d'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw || 0;
                            const total = data.total;
                            const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            },
            cutout: '70%'
        }
    });
}
