// Chart.js configuration and setup
const createPriceChart = (chartId, timeframe = '30d') => {
    console.log('Creating price chart with ID:', chartId);
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
            maintainAspectRatio: false,
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
            }
        }
    });
    return chart;
};

const loadChartData = async (symbol, chart, timeframe = '30d') => {
    // Declare chart elements at the start
    const chartElement = chart.canvas.parentElement;
    const errorElement = chartElement.querySelector('#error-message');
    const loadingOverlay = chartElement.querySelector('.loading-overlay');

    try {
        console.log(`Loading chart data for ${symbol} with timeframe ${timeframe}`);

        // Show loading state
        if (errorElement) errorElement.classList.add('d-none');
        if (loadingOverlay) loadingOverlay.classList.remove('d-none');

        chartElement.style.opacity = '0.5';
        chartElement.style.pointerEvents = 'none';

        // Fetch price history data
        const response = await fetch(`/api/price-history/${symbol}?timeframe=${timeframe}`);
        const data = await response.json();

        console.log('API Response:', data);

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        if (!data || !data.prices || !data.sma) {
            console.error('Invalid data structure:', data);
            throw new Error('Invalid data format received');
        }

        console.log(`Received ${data.prices.length} price points and ${data.sma.length} SMA points`);

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
        console.log('Chart updated successfully');

    } catch (error) {
        console.error('Error loading chart data:', error);
        if (errorElement) {
            errorElement.textContent = error.message;
            errorElement.classList.remove('d-none');
        }
    } finally {
        // Reset loading state
        if (loadingOverlay) loadingOverlay.classList.add('d-none');
        chartElement.style.opacity = '1';
        chartElement.style.pointerEvents = 'auto';
    }
};

// Timeframe selector handling
const initializeTimeframeSelector = (chart, symbol) => {
    console.log('Initializing timeframe selector');
    const timeframeButtons = document.querySelectorAll('[data-timeframe]');
    timeframeButtons.forEach(button => {
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            const timeframe = e.target.dataset.timeframe;
            console.log(`Timeframe button clicked: ${timeframe}`);

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