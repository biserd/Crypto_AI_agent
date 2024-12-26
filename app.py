import os
from flask import Flask, render_template
import logging
from database import db
from models import Article, CryptoPrice, NewsSourceMetrics
import re
from markupsafe import escape, Markup

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
app.secret_key = os.urandom(24)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

db.init_app(app)

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

        # Prepare articles with enhanced summaries
        for article in recent_articles:
            try:
                # Create a copy of the summary for modification
                enhanced_summary = escape(article.summary)
                logger.debug(f"Processing article {article.id} summary: {enhanced_summary[:100]}...")

                # Add crypto price tooltips to the summary
                for crypto in crypto_prices:
                    # Use word boundaries to match only whole words
                    pattern = re.compile(r'\b' + re.escape(crypto.symbol) + r'\b', re.IGNORECASE)
                    if pattern.search(str(enhanced_summary)):
                        # Create tooltip HTML with Markup to prevent double-escaping
                        tooltip_html = Markup(
                            f'<span class="crypto-tooltip">{crypto.symbol}'
                            f'<div class="tooltip-content">'
                            f'<span class="tooltip-price">${crypto.price_usd:.2f}</span>'
                            f'<span class="tooltip-change {("positive" if crypto.percent_change_24h > 0 else "negative")}">'
                            f'{crypto.percent_change_24h:.1f}%</span>'
                            f'</div></span>'
                        )

                        enhanced_summary = Markup(pattern.sub(str(tooltip_html), str(enhanced_summary)))
                        logger.debug(f"Added tooltip for whole word match {crypto.symbol} in article {article.id}")
                        logger.debug(f"Generated tooltip HTML: {tooltip_html}")
                    else:
                        logger.debug(f"No whole word match found for {crypto.symbol} in article {article.id}")


                # Store the enhanced summary in a new attribute
                article.enhanced_summary = enhanced_summary

            except Exception as e:
                logger.error(f"Error processing tooltips for article {article.id}: {str(e)}")
                article.enhanced_summary = article.summary

            # Attach source metrics
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