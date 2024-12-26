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

db.init_app(app)

# Routes
@app.route('/')
def dashboard():
    logging.info("Fetching articles for dashboard")
    recent_articles = Article.query.order_by(Article.created_at.desc()).all()
    crypto_prices = CryptoPrice.query.all()
    news_sources = NewsSourceMetrics.query.order_by(NewsSourceMetrics.trust_score.desc()).all()

    # Attach source metrics to articles for easy access in template
    for article in recent_articles:
        article.source_metrics = next(
            (source for source in news_sources if source.source_name == article.source_name),
            None
        )

    logging.info(f"Found {len(recent_articles)} articles to display")
    return render_template('dashboard.html', 
                         articles=recent_articles,
                         crypto_prices=crypto_prices,
                         news_sources=news_sources)

with app.app_context():
    db.create_all()