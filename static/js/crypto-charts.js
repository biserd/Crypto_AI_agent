// Chart.js configuration and setup
const createPriceChart = (chartId, timeframe = '30d') => {
    const chart = new Chart(document.getElementById(chartId), {
        type: 'line',
        data: {
            datasets: [
                {
                    label: 'Price',
                    borderColor: '#10B981',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: false,
                    data: []
                },
                {
                    label: '7-day Moving Average',
                    borderColor: '#6366F1',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: false,
                    data: []
                }
            ]
        },
        options: {
            maintainAspectRatio: false, // Important: allows chart to fill container
            responsive: true,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 12,
                        padding: 10
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += new Intl.NumberFormat('en-US', {
                                    style: 'currency',
                                    currency: 'USD'
                                }).format(context.parsed.y);
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day'
                    },
                    grid: {
                        display: false
                    },
                    ticks: {
                        maxRotation: 0
                    }
                },
                y: {
                    position: 'left',
                    grid: {
                        color: 'rgba(0,0,0,0.05)'
                    },
                    ticks: {
                        callback: function(value) {
                            return new Intl.NumberFormat('en-US', {
                                style: 'currency',
                                currency: 'USD',
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2
                            }).format(value);
                        }
                    }
                }
            },
            layout: {
                padding: {
                    left: 10,
                    right: 10,
                    top: 10,
                    bottom: 10
                }
            }
        }
    });
    return chart;
};

const loadChartData = async (symbol, chart, timeframe = '30d') => {
    try {
        // Show loading state
        const chartElement = chart.canvas.parentElement;
        chartElement.style.opacity = '0.5';
        chartElement.style.pointerEvents = 'none';

        // Fetch price history data
        const response = await fetch(`/api/price-history/${symbol}?timeframe=${timeframe}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch data for ${symbol}`);
        }

        const data = await response.json();
        if (!data || !data.prices || !data.sma) {
            throw new Error('Invalid data format received');
        }

        // Update chart datasets
        chart.data.datasets[0].data = data.prices.map(item => ({
            x: new Date(item[0]),
            y: item[1]
        }));

        chart.data.datasets[1].data = data.sma.map(item => ({
            x: new Date(item.timestamp),
            y: item.value
        }));

        chart.update('none'); // Use 'none' for smoother updates

        // Reset loading state
        chartElement.style.opacity = '1';
        chartElement.style.pointerEvents = 'auto';

    } catch (error) {
        console.error('Error loading chart data:', error);
        const errorMessage = document.createElement('div');
        errorMessage.className = 'alert alert-danger mt-3';
        errorMessage.textContent = `Failed to load chart data: ${error.message}`;
        chart.canvas.parentElement.appendChild(errorMessage);
    }
};

// Timeframe selector handling
const initializeTimeframeSelector = (chart, symbol) => {
    const timeframeButtons = document.querySelectorAll('[data-timeframe]');
    timeframeButtons.forEach(button => {
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            const timeframe = e.target.dataset.timeframe;

            // Update active state
            timeframeButtons.forEach(btn => btn.classList.remove('active'));
            e.target.classList.add('active');

            // Reload chart data with new timeframe
            await loadChartData(symbol, chart, timeframe);
        });
    });
};

// Export functions for use in templates
window.CryptoCharts = {
    createPriceChart,
    loadChartData,
    initializeTimeframeSelector
};