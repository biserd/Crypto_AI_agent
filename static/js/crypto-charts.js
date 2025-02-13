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

    function calculateSMA(data, period) {
        const sma = [];
        for (let i = 0; i < data.length; i++) {
            if (i < period - 1) {
                sma.push(null);
                continue;
            }
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += data[i - j].y;
            }
            sma.push({x: data[i].x, y: sum / period});
        }
        return sma;
    }

    function createChart(data) {
        if (currentChart) {
            currentChart.destroy();
        }

        // Format the price data
        const chartData = data.prices.map(item => ({
            x: new Date(item[0]),
            y: parseFloat(item[1])
        })).filter(item => !isNaN(item.y));

        // Format the volume data
        const volumeData = data.total_volumes.map(item => ({
            x: new Date(item[0]),
            y: parseFloat(item[1])
        })).filter(item => !isNaN(item.y));

        // Calculate moving averages
        const sma50 = calculateSMA(chartData, 50);
        const sma200 = calculateSMA(chartData, 200);

        // Calculate price change
        const firstPrice = chartData[0]?.y;
        const lastPrice = chartData[chartData.length - 1]?.y;
        const priceChange = firstPrice && lastPrice ? ((lastPrice - firstPrice) / firstPrice) * 100 : 0;

        currentChart = new Chart(ctx, {
            type: 'line', // Set default type as line
            data: {
                datasets: [
                    {
                        type: 'line',
                        label: `${symbol} Price (USD)`,
                        data: chartData,
                        borderColor: '#2196F3',
                        backgroundColor: 'rgba(33, 150, 243, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        yAxisID: 'y',
                        order: 1
                    },
                    {
                        type: 'line',
                        label: '50-day MA',
                        data: sma50,
                        borderColor: '#4CAF50',
                        borderWidth: 1.5,
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0.4,
                        yAxisID: 'y',
                        order: 2
                    },
                    {
                        type: 'line',
                        label: '200-day MA',
                        data: sma200,
                        borderColor: '#FFA726',
                        borderWidth: 1.5,
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0.4,
                        yAxisID: 'y',
                        order: 3
                    },
                    {
                        type: 'bar',
                        label: 'Volume',
                        data: volumeData,
                        backgroundColor: 'rgba(156, 39, 176, 0.2)',
                        borderColor: 'rgba(156, 39, 176, 0.4)',
                        borderWidth: 1,
                        yAxisID: 'volume',
                        order: 4
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
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.dataset.label || '';
                                const value = context.parsed.y;

                                if (label.includes('Volume')) {
                                    return `${label}: $${value.toLocaleString()}`;
                                }

                                if (label.includes('Price')) {
                                    const dataPoint = chartData[context.dataIndex];
                                    const prevDataPoint = chartData[context.dataIndex - 1];
                                    let change = '';

                                    if (prevDataPoint) {
                                        const percentChange = ((dataPoint.y - prevDataPoint.y) / prevDataPoint.y) * 100;
                                        change = ` (${percentChange >= 0 ? '+' : ''}${percentChange.toFixed(2)}%)`;
                                    }

                                    return `${label}: $${value.toFixed(2)}${change}`;
                                }

                                return `${label}: $${value.toFixed(2)}`;
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
                    },
                    volume: {
                        position: 'left',
                        grid: {
                            display: false
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + (value / 1000000).toFixed(1) + 'M';
                            }
                        }
                    }
                }
            }
        });

        // Remove any existing price change indicator
        const existingIndicator = chartContainer.querySelector('.price-change-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }

        // Add price change indicator to the chart container
        const priceChangeElement = document.createElement('div');
        priceChangeElement.className = `price-change-indicator ${priceChange >= 0 ? 'positive' : 'negative'}`;
        priceChangeElement.innerHTML = `${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}% (${data.prices.length}d)`;
        chartContainer.insertBefore(priceChangeElement, chartContainer.firstChild);
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
            createChart(data);
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