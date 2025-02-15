
// Initialize price chart
function initPriceChart(symbol) {
    console.log("Initializing price chart for symbol:", symbol);
    let chart = null;
    let currentTimeframe = '30'; // Default to 30 days

    fetchChartData(symbol, currentTimeframe);

    function fetchChartData(symbol, days, attempt = 1) {
        console.log(`Fetching data for ${symbol} with ${days} days (attempt ${attempt})`);
        fetch(`https://api.coingecko.com/api/v3/coins/${symbol.toLowerCase()}/market_chart?vs_currency=usd&days=${days}`)
            .then(response => response.json())
            .then(data => {
                console.log("Creating chart with data:", data);
                createChart(data.prices);
            })
            .catch(error => {
                console.error('Error fetching chart data:', error);
                if (attempt < 3) {
                    setTimeout(() => fetchChartData(symbol, days, attempt + 1), 2000);
                } else {
                    displayChartError();
                }
            });
    }

    function createChart(priceData) {
        console.log("Creating Chart.js instance");
        const ctx = document.getElementById('priceChart').getContext('2d');
        
        // Destroy existing chart if it exists
        if (chart) {
            chart.destroy();
        }

        // Process data
        const labels = priceData.map(d => new Date(d[0]));
        const prices = priceData.map(d => d[1]);

        // Create new chart
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Price (USD)',
                    data: prices,
                    borderColor: '#10B981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
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
                            unit: 'day'
                        },
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
        console.log("Chart created successfully");
    }

    function displayChartError() {
        const container = document.querySelector('.price-chart-container');
        container.innerHTML = `
            <div class="chart-error">
                <p>Unable to load chart data. Please try again later.</p>
            </div>
        `;
    }

    // Timeframe buttons
    document.querySelectorAll('.timeframe-button').forEach(button => {
        button.addEventListener('click', () => {
            const days = button.dataset.days;
            currentTimeframe = days;
            fetchChartData(symbol, days);
            
            // Update active button state
            document.querySelectorAll('.timeframe-button').forEach(btn => {
                btn.classList.remove('active');
            });
            button.classList.add('active');
        });
    });
}
