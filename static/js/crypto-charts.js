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
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'top',
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
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Price (USD)'
                    },
                    ticks: {
                        callback: function(value) {
                            return new Intl.NumberFormat('en-US', {
                                style: 'currency',
                                currency: 'USD'
                            }).format(value);
                        }
                    }
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

        chart.update();

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
