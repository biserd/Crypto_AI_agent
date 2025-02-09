// Simple price chart implementation
function createPriceChart(symbol) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    const chartContainer = document.querySelector('.price-chart-container');

    // Create error message element if it doesn't exist
    let errorElement = chartContainer.querySelector('.chart-error');
    if (!errorElement) {
        errorElement = document.createElement('div');
        errorElement.className = 'chart-error alert alert-danger d-none';
        chartContainer.appendChild(errorElement);
    }

    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [{
                label: `${symbol} Price (USD)`,
                borderColor: '#2196F3',
                backgroundColor: 'rgba(33, 150, 243, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                data: []
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

    // Load initial data
    fetch(`/api/price-history/${symbol}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }

            // Hide any existing error message
            errorElement.classList.add('d-none');

            // Update chart with new data
            chart.data.datasets[0].data = data.prices.map(item => ({
                x: item[0],
                y: item[1]
            }));
            chart.update();
        })
        .catch(error => {
            console.error('Error fetching price data:', error);
            errorElement.textContent = `Unable to load price chart: ${error.message}`;
            errorElement.classList.remove('d-none');
            chart.clear();
        });

    return chart;
}