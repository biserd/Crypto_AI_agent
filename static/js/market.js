document.addEventListener('DOMContentLoaded', function() {
    const marketCap = document.getElementById('total-market-cap');
    const volume = document.getElementById('total-volume');
    const btcDominance = document.getElementById('btc-dominance');
    const activeCryptos = document.getElementById('active-cryptos');
    const marketTable = document.getElementById('market-table').getElementsByTagName('tbody')[0];

    // Clear existing rows
    marketTable.innerHTML = '';

    async function fetchMarketData() {
        try {
            marketTable.innerHTML = ''; // Clear table before adding new data
            const response = await fetch('/api/crypto-prices');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (!Array.isArray(data) || data.length === 0) {
                throw new Error('No cryptocurrency data available');
            }

            let totalMarketCap = 0;
            let totalVolume = 0;
            let btcMarketCap = 0;

            data.forEach(crypto => {
                const mCap = parseFloat(crypto.market_cap) || 0;
                const vol = parseFloat(crypto.volume_24h) || 0;
                totalMarketCap += mCap;
                totalVolume += vol;
                if (crypto.symbol === 'BTC') {
                    btcMarketCap = mCap;
                }
            });

            // Update market statistics
            // Format large numbers
            const formatNumber = (num) => {
                if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
                if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
                if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
                return `$${num.toLocaleString()}`;
            };

            marketCap.textContent = formatNumber(totalMarketCap);
            volume.textContent = formatNumber(totalVolume);
            btcDominance.textContent = totalMarketCap > 0 ? 
                `${((btcMarketCap / totalMarketCap) * 100).toFixed(1)}%` : 
                '0%';
            activeCryptos.textContent = data.filter(c => c && c.market_cap > 0).length;

            // Create table rows
            // Sort data by market cap
            data.sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
            
            data.forEach((crypto, index) => {
                const row = marketTable.insertRow();
                const priceFormatted = parseFloat(crypto.price_usd).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
                
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td><a href="/crypto/${crypto.symbol}">${crypto.symbol}</a></td>
                    <td>$${priceFormatted}</td>
                    <td class="${crypto.percent_change_24h > 0 ? 'text-success' : 'text-danger'}">
                        ${parseFloat(crypto.percent_change_24h).toFixed(2)}%
                    </td>
                    <td class="${crypto.percent_change_7d > 0 ? 'text-success' : 'text-danger'}">
                        ${parseFloat(crypto.percent_change_7d || 0).toFixed(2)}%
                    </td>
                    <td>$${parseInt(crypto.market_cap || 0).toLocaleString()}</td>
                    <td>$${parseInt(crypto.volume_24h || 0).toLocaleString()}</td>
                `;
            });
        } catch (error) {
            console.error('Error fetching market data:', error);
        }
    }


    fetchMarketData();
});