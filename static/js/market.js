document.addEventListener('DOMContentLoaded', function() {
    const marketCap = document.getElementById('total-market-cap');
    const volume = document.getElementById('total-volume');
    const btcDominance = document.getElementById('btc-dominance');
    const activeCryptos = document.getElementById('active-cryptos');
    const marketTable = document.getElementById('market-table').getElementsByTagName('tbody')[0];

    async function fetchMarketData() {
        try {
            const response = await fetch('/api/crypto-prices');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            // Calculate totals
            let totalMarketCap = 0;
            let totalVolume = 0;
            let btcMarketCap = 0;

            // Format large numbers
            const formatLargeNumber = (num) => {
                if (num >= 1e12) return `${(num / 1e12).toFixed(2)}T`;
                if (num >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
                if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
                return num.toLocaleString();
            };

            // Clear existing table rows
            marketTable.innerHTML = '';

            // Sort data by market cap
            data.sort((a, b) => b.market_cap - a.market_cap);

            data.forEach((crypto, index) => {
                totalMarketCap += crypto.market_cap || 0;
                totalVolume += crypto.volume_24h || 0;
                if (crypto.symbol === 'BTC') {
                    btcMarketCap = crypto.market_cap;
                }

                const row = marketTable.insertRow();
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td><a href="/crypto/${crypto.symbol}">${crypto.symbol}</a></td>
                    <td>$${parseFloat(crypto.price_usd).toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                    })}</td>
                    <td class="${crypto.percent_change_24h >= 0 ? 'text-success' : 'text-danger'}">
                        ${crypto.percent_change_24h.toFixed(2)}%
                    </td>
                    <td class="${crypto.percent_change_7d >= 0 ? 'text-success' : 'text-danger'}">
                        ${crypto.percent_change_7d.toFixed(2)}%
                    </td>
                    <td>$${formatLargeNumber(crypto.market_cap)}</td>
                    <td>$${formatLargeNumber(crypto.volume_24h)}</td>
                `;
            });

            // Update market statistics
            marketCap.textContent = `$${formatLargeNumber(totalMarketCap)}`;
            volume.textContent = `$${formatLargeNumber(totalVolume)}`;
            btcDominance.textContent = `${((btcMarketCap / totalMarketCap) * 100).toFixed(1)}%`;
            activeCryptos.textContent = data.length;

        } catch (error) {
            console.error('Error fetching market data:', error);
            marketTable.innerHTML = '<tr><td colspan="7" class="text-center">Error loading market data. Please try refreshing the page.</td></tr>';
        }
    }

    // Initial fetch
    fetchMarketData();

    // Refresh every 60 seconds
    setInterval(fetchMarketData, 60000);
});