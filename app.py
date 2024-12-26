import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template
import logging
from database import db
from models import Article, CryptoPrice, NewsSourceMetrics, CryptoGlossary
import re
from markupsafe import escape, Markup
from flask_socketio import SocketIO, emit
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Configuration
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

db.init_app(app)

def broadcast_new_article(article):
    """Broadcast new article to all connected clients"""
    try:
        article_data = {
            'id': article.id,
            'title': article.title,
            'summary': article.summary,
            'source_name': article.source_name,
            'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'sentiment_label': article.sentiment_label,
            'sentiment_score': article.sentiment_score
        }
        socketio.emit('new_article', article_data)
        logger.info(f"Broadcasted new article: {article.title}")
    except Exception as e:
        logger.error(f"Error broadcasting article: {str(e)}")

from functools import wraps
from flask import jsonify, request
import time

def check_rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not getattr(request, 'subscription', None):
            request.subscription = Subscription.query.filter_by(user_id=1, active=True).first()
            if not request.subscription:
                request.subscription = Subscription(user_id=1, plan_type='free')
                
        key = f"{request.remote_addr}:{int(time.time() // 3600)}"
        current = cache.get(key) or 0
        
        if current >= request.subscription.rate_limit:
            return jsonify({"error": "Rate limit exceeded", "upgrade_url": "/upgrade"}), 429
            
        cache.incr(key)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@check_rate_limit
def dashboard():
    try:
        logger.info("Starting dashboard view generation")

        # Fetch articles with error handling
        try:
            recent_articles = Article.query.order_by(Article.created_at.desc()).limit(20).all()
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
                enhanced_summary = escape(article.summary)
                logger.debug(f"Processing article {article.id} summary: {enhanced_summary[:100]}...")

                # Add crypto price tooltips to the summary
                for crypto in crypto_prices:
                    pattern = re.compile(r'\b' + re.escape(crypto.symbol) + r'\b', re.IGNORECASE)
                    if pattern.search(str(enhanced_summary)):
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

                article.enhanced_summary = enhanced_summary

            except Exception as e:
                logger.error(f"Error processing tooltips for article {article.id}: {str(e)}")
                article.enhanced_summary = article.summary

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

@app.route('/glossary')
def glossary():
    try:
        logger.info("Accessing crypto glossary page")
        terms = CryptoGlossary.query.order_by(CryptoGlossary.term).all()
        categories = db.session.query(CryptoGlossary.category).distinct().all()
        categories = [cat[0] for cat in categories if cat[0]]

        return render_template('glossary.html', 
                             terms=terms,
                             categories=categories)
    except Exception as e:
        logger.error(f"Error accessing glossary: {str(e)}")
        return "Error loading glossary", 500

@app.route('/glossary/term/<term_id>')
def get_term_details(term_id):
    try:
        term = CryptoGlossary.query.get_or_404(term_id)
        term.usage_count += 1
        db.session.commit()

        related_terms = []
        if term.related_terms:
            related_terms = CryptoGlossary.query.filter(
                CryptoGlossary.term.in_(term.related_terms.split(','))
            ).all()

        return render_template('term_details.html', 
                             term=term,
                             related_terms=related_terms)
    except Exception as e:
        logger.error(f"Error getting term details: {str(e)}")
        return "Error loading term details", 500

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected to WebSocket")

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected from WebSocket")

def sync_article_counts():
    """Synchronize article counts with actual numbers in database"""
    try:
        with app.app_context():
            sources = NewsSourceMetrics.query.all()
            for source in sources:
                count = Article.query.filter_by(source_name=source.name).count()
                source.article_count = count
                logger.info(f"Syncing article count for {source.name}: {count}")
            db.session.commit()
            logger.info("Successfully synchronized all article counts")
    except Exception as e:
        logger.error(f"Error syncing article counts: {str(e)}")
        db.session.rollback()

with app.app_context():
    try:
        db.create_all()
        sync_article_counts()  # Sync counts on startup
        logger.info("Successfully created database tables and synced counts")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=True, log_output=True)