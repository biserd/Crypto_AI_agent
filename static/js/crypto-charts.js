
// Price chart implementation
function createPriceChart(symbol) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    const chartContainer = document.querySelector('.price-chart-container');
    const loader = chartContainer.querySelector('.chart-loader');
    const errorElement = chartContainer.querySelector('.chart-error');
    const timeframeButtons = document.querySelectorAll('.timeframe-selector button');

    let currentChart = null;

    function showLoader() {
        if (loader) {
            loader.classList.remove('d-none');
        }
        if (errorElement) {
            errorElement.classList.add('d-none');
        }
    }

    function hideLoader() {
        if (loader) {
            loader.classList.add('d-none');
        }
    }

    function showError(message) {
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('d-none');
        }
        hideLoader();
    }

    function createChart(data) {
        if (currentChart) {
            currentChart.destroy();
        }

        // Format the data
        const chartData = data.map(item => ({
            x: new Date(item[0]),
            y: parseFloat(item[1])
        })).filter(item => !isNaN(item.y));

        currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: `${symbol} Price (USD)`,
                    data: chartData,
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

    async function loadChartData(days = 30, retryCount = 0) {
        try {
            showLoader();
            console.log(`Fetching data for ${symbol} with ${days} days (attempt ${retryCount + 1})`);

            const response = await fetch(`/api/price-history/${symbol}?days=${days}`);
            const data = await response.json();
            
            console.log('API Response:', data);

            if (response.status === 429 && retryCount < 3) {
                const retryAfter = parseInt(response.headers.get('Retry-After') || '30');
                console.log(`Rate limited, retrying after ${retryAfter} seconds...`);
                showError(`Rate limited, retrying in ${retryAfter} seconds...`);
                await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
                return loadChartData(days, retryCount + 1);
            }

            if (!response.ok) {
                throw new Error(data.error || 'Failed to load price data');
            }

            if (!data.prices || !Array.isArray(data.prices)) {
                console.error('Invalid price data format:', data);
                throw new Error('Invalid price data format received');
            }

            if (data.prices.length === 0) {
                throw new Error('No price data available');
            }

            // Validate data format before creating chart
            const validData = data.prices.every(item => 
                Array.isArray(item) && 
                item.length === 2 && 
                !isNaN(new Date(item[0]).getTime()) && 
                !isNaN(parseFloat(item[1]))
            );

            if (!validData) {
                throw new Error('Invalid price data format');
            }

            console.log(`Processing ${data.prices.length} price points`);
            createChart(data.prices);
            hideLoader();
            if (errorElement) {
                errorElement.classList.add('d-none');
            }

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
            loadChartData(parseInt(button.dataset.days, 10));
        });
    });

    // Load initial data
    loadChartData(30);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const symbolElement = document.querySelector('.symbol-badge');
    if (symbolElement) {
        const symbol = symbolElement.textContent.trim();
        createPriceChart(symbol);
    }
});
