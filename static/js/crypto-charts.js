
// Initialize price chart
function initPriceChart(symbol) {
    console.log("Initializing price chart for symbol:", symbol);
    let chart = null;
    let currentTimeframe = '30'; // Default to 30 days

    fetchChartData(symbol, currentTimeframe);

    function calculateRSI(prices, periods = 14) {
        let gains = [], losses = [];
        for (let i = 1; i < prices.length; i++) {
            const diff = prices[i] - prices[i - 1];
            gains.push(diff > 0 ? diff : 0);
            losses.push(diff < 0 ? -diff : 0);
        }
        
        const avgGain = gains.slice(0, periods).reduce((a, b) => a + b) / periods;
        const avgLoss = losses.slice(0, periods).reduce((a, b) => a + b) / periods;
        
        return (100 - (100 / (1 + avgGain / avgLoss)));
    }

    function calculateMA(prices, periods) {
        let ma = [];
        for (let i = 0; i < prices.length; i++) {
            if (i < periods - 1) {
                ma.push(null);
                continue;
            }
            const slice = prices.slice(i - periods + 1, i + 1);
            const avg = slice.reduce((a, b) => a + b) / periods;
            ma.push(avg);
        }
        return ma;
    }

    function fetchChartData(symbol, days, attempt = 1) {
        console.log(`Fetching data for ${symbol} with ${days} days (attempt ${attempt})`);
        const symbolToId = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'USDT': 'tether',
            'BNB': 'binancecoin',
            'SOL': 'solana',
            'XRP': 'ripple',
            'USDC': 'usd-coin',
            'ADA': 'cardano',
            'AVAX': 'avalanche-2',
            'DOGE': 'dogecoin',
            'LINK': 'chainlink',
            'DOT': 'polkadot',
            'MATIC': 'matic-network',
            'AAVE': 'aave',
            'CAKE': 'pancakeswap-token',
            'POLY': 'polymath',
            'ORDI': 'ordinals-token',
            'TON': 'toncoin',
            'TRX': 'tron',
            'MEME': 'memecoin-2',
            'SEI': 'sei-network',
            'SUI': 'sui',
            'BONK': 'bonk',
            'WLD': 'worldcoin-wld',
            'PYTH': 'pyth-network',
            'JUP': 'jupiter',
            'BLUR': 'blur',
            'HFT': 'hashflow',
            'WIF': 'wif-token',
            'STRK': 'starknet',
            'TIA': 'celestia',
            'DYM': 'dymension'
        };
        
        const coinId = symbolToId[symbol.toUpperCase()] || symbol.toLowerCase();
        fetch(`https://api.coingecko.com/api/v3/coins/${coinId}/market_chart?vs_currency=usd&days=${days}`)
            .then(response => response.json())
            .then(data => {
                console.log("Creating chart with data:", data);
                if (data.error) {
                    throw new Error(data.error);
                }
                if (!data.prices || !data.total_volumes) {
                    throw new Error('Invalid data format received');
                }
                createChart(data.prices, data.total_volumes);
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

    function createChart(priceData, volumeData) {
        console.log("Creating Chart.js instance");
        const ctx = document.getElementById('priceChart').getContext('2d');
        
        if (chart) {
            chart.destroy();
        }

        const labels = priceData.map(d => new Date(d[0]));
        const prices = priceData.map(d => d[1]);
        const volumes = volumeData.map(d => d[1]);

        // Calculate technical indicators
        const ma20 = calculateMA(prices, 20);
        const ma50 = calculateMA(prices, 50);
        const rsi = calculateRSI(prices);

        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Price',
                        data: prices,
                        borderColor: '#10B981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        yAxisID: 'price',
                        order: 1
                    },
                    {
                        label: 'MA20',
                        data: ma20,
                        borderColor: '#FFB020',
                        borderWidth: 1.5,
                        fill: false,
                        tension: 0.4,
                        yAxisID: 'price',
                        order: 2,
                        hidden: true
                    },
                    {
                        label: 'MA50',
                        data: ma50,
                        borderColor: '#7C3AED',
                        borderWidth: 1.5,
                        fill: false,
                        tension: 0.4,
                        yAxisID: 'price',
                        order: 3,
                        hidden: true
                    },
                    {
                        label: 'Volume',
                        data: volumes,
                        type: 'bar',
                        backgroundColor: 'rgba(16, 185, 129, 0.2)',
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
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                if (context.dataset.label === 'Volume') {
                                    return `Volume: $${context.parsed.y.toFixed(0)}`;
                                }
                                return `${context.dataset.label}: $${context.parsed.y.toFixed(2)}`;
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
                    price: {
                        position: 'right',
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        beginAtZero: false
                    },
                    volume: {
                        position: 'left',
                        grid: {
                            display: false
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + (value/1000000).toFixed(0) + 'M';
                            }
                        },
                        beginAtZero: true,
                        display: true
                    }
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
