
# Exploding Crypto - AI-Powered Crypto News Aggregator

A real-time cryptocurrency news aggregation platform that uses AI to analyze market sentiment and deliver insights to traders and enthusiasts.

## Tech Stack

- **Backend**: Python/Flask
- **Database**: SQLAlchemy with PostgreSQL
- **Frontend**: Bootstrap 5, JavaScript
- **Real-time Updates**: Flask-SocketIO with EventLet
- **Payment Processing**: Stripe Integration
- **Authentication**: Flask-Login

## Project Structure

```
├── app.py              # Main Flask application
├── main.py             # Application entry point
├── scraper.py          # News scraping functionality
├── models.py           # Database models
├── scheduler.py        # Background task scheduler
├── database.py         # Database configuration
├── crypto_price_tracker.py  # Cryptocurrency price tracking
├── nlp_processor.py    # Natural language processing
├── distributors.py     # Content distribution system
├── static/            # Static assets
└── templates/         # HTML templates
```

## Key Features

- Real-time News Aggregation from Multiple Sources
- AI-powered Sentiment Analysis
- Live Cryptocurrency Price Tracking
- Comprehensive Crypto Glossary
- User Authentication System
- Pro Subscription Management
- Source Reliability Scoring
- Mobile-Friendly Interface

## Data Sources

- CoinDesk
- Cointelegraph
- Messari
- The Block

## Subscription Tiers

- **Basic**: Access to fundamental features
- **Pro**: Enhanced capabilities including advanced sentiment indicators and early alerts

## Real-time Updates

The system uses WebSocket connections (Flask-SocketIO) to provide:
- Live price updates
- Instant news alerts
- Real-time sentiment analysis

## Getting Started

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
- FLASK_SECRET_KEY
- DATABASE_URL
- STRIPE_PUBLISHABLE_KEY
- STRIPE_TEST_SECRET_KEY

3. Run the application:
```bash
python main.py
```

## News Scraping Schedule

The scheduler runs periodically to:
- Fetch latest news articles
- Update cryptocurrency prices
- Process sentiment analysis
- Update source metrics

## Contributing

Feel free to submit issues and enhancement requests.

## License

[MIT License](LICENSE)
