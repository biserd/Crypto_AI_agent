
document.addEventListener('DOMContentLoaded', function() {
    const marketCap = document.getElementById('total-market-cap');
    const volume = document.getElementById('total-volume');
    const btcDominance = document.getElementById('btc-dominance');
    const activeCryptos = document.getElementById('active-cryptos');
    const marketTable = document.getElementById('market-table').getElementsByTagName('tbody')[0];

    async function fetchMarketData() {
        try {
            const response = await fetch('/api/crypto-prices');
            const data = await response.json();
            
            let totalMarketCap = 0;
            let totalVolume = 0;
            let btcMarketCap = 0;

            data.forEach(crypto => {
                totalMarketCap += crypto.market_cap || 0;
                totalVolume += crypto.volume_24h || 0;
                if (crypto.symbol === 'BTC') {
                    btcMarketCap = crypto.market_cap || 0;
                }

                const row = marketTable.insertRow();
                row.innerHTML = `
                    <td>${crypto.rank || '-'}</td>
                    <td><a href="/crypto/${crypto.symbol}">${crypto.symbol}</a></td>
                    <td>$${crypto.price_usd?.toFixed(2) || '0.00'}</td>
                    <td class="${crypto.percent_change_24h > 0 ? 'text-success' : 'text-danger'}">
                        ${crypto.percent_change_24h?.toFixed(2) || '0.00'}%
                    </td>
                    <td class="${crypto.percent_change_7d > 0 ? 'text-success' : 'text-danger'}">
                        ${crypto.percent_change_7d?.toFixed(2) || '0.00'}%
                    </td>
                    <td>$${(crypto.market_cap || 0).toLocaleString()}</td>
                    <td>$${(crypto.volume_24h || 0).toLocaleString()}</td>
                `;
            });

            marketCap.textContent = `$${totalMarketCap.toLocaleString()}`;
            volume.textContent = `$${totalVolume.toLocaleString()}`;
            btcDominance.textContent = `${((btcMarketCap / totalMarketCap) * 100).toFixed(2)}%`;
            activeCryptos.textContent = data.length;
        } catch (error) {
            console.error('Error fetching market data:', error);
        }
    }

    fetchMarketData();
});
