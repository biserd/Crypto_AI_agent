// Price chart implementation
function createPriceChart(symbol) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    const chartContainer = document.querySelector('.price-chart-container');
    const loader = chartContainer.querySelector('.chart-loader');
    const errorElement = chartContainer.querySelector('.chart-error');
    const timeframeButtons = document.querySelectorAll('.timeframe-selector button');

    let currentChart = null;

    function showLoader() {
        loader.classList.remove('d-none');
        errorElement.classList.add('d-none');
    }

    function hideLoader() {
        loader.classList.add('d-none');
    }

    function showError(message) {
        errorElement.textContent = message;
        errorElement.classList.remove('d-none');
        hideLoader();
    }

    function createChart(data) {
        // Destroy existing chart if it exists
        if (currentChart) {
            currentChart.destroy();
        }

        currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: `${symbol} Price (USD)`,
                    data: data.map(item => ({
                        x: item[0],
                        y: item[1]
                    })),
                    borderColor: '#2196F3',
                    backgroundColor: 'rgba(33, 150, 243, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
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
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `$${context.parsed.y.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'day',
                            tooltipFormat: 'MMM DD, YYYY'
                        },
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        position: 'right',
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });
    }

    async function loadChartData(days = 30) {
        try {
            showLoader();

            const response = await fetch(`/api/price-history/${symbol}?days=${days}`);
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }

            if (!data.prices || data.prices.length === 0) {
                throw new Error('No price data available');
            }

            createChart(data.prices);
            hideLoader();
            errorElement.classList.add('d-none');
        } catch (error) {
            console.error('Error fetching price data:', error);
            showError(`Unable to load price chart: ${error.message}`);
        }
    }

    // Set up timeframe selector buttons
    timeframeButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            timeframeButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            loadChartData(button.dataset.days);
        });
    });

    // Load initial data
    loadChartData(30);

    return currentChart;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const symbolElement = document.querySelector('.symbol-badge');
    if (symbolElement) {
        const symbol = symbolElement.textContent.trim();
        createPriceChart(symbol);
    }
});