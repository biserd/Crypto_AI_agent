import os
from flask import Flask, render_template
import logging
from database import db
from models import Article, CryptoPrice, NewsSourceMetrics

app = Flask(__name__)

# Configuration
app.secret_key = os.urandom(24)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

db.init_app(app)

# Routes
@app.route('/')
def dashboard():
    try:
        logger.info("Starting dashboard view generation")

        # Fetch articles with error handling
        try:
            recent_articles = Article.query.order_by(Article.created_at.desc()).all()
            logger.info(f"Retrieved {len(recent_articles)} articles from database")
        except Exception as e:
            logger.error(f"Error fetching articles: {str(e)}")
            recent_articles = []

        # Fetch crypto prices with error handling
        try:
            crypto_prices = CryptoPrice.query.all()
            logger.info(f"Retrieved {len(crypto_prices)} crypto prices")
        except Exception as e:
            logger.error(f"Error fetching crypto prices: {str(e)}")
            crypto_prices = []

        # Fetch news sources with error handling
        try:
            news_sources = NewsSourceMetrics.query.order_by(NewsSourceMetrics.trust_score.desc()).all()
            logger.info(f"Retrieved {len(news_sources)} news sources")
        except Exception as e:
            logger.error(f"Error fetching news sources: {str(e)}")
            news_sources = []

        # Attach source metrics to articles for easy access in template
        for article in recent_articles:
            article.source_metrics = next(
                (source for source in news_sources if source.source_name == article.source_name),
                None
            )

        logger.info("Successfully prepared all data for dashboard")
        return render_template('dashboard.html', 
                             articles=recent_articles,
                             crypto_prices=crypto_prices,
                             news_sources=news_sources)
    except Exception as e:
        logger.error(f"Error generating dashboard: {str(e)}")
        return "Error loading dashboard", 500

with app.app_context():
    try:
        db.create_all()
        logger.info("Successfully created database tables")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")