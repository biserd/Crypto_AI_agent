import eventlet
eventlet.monkey_patch()

import os
from functools import wraps
from flask import Flask, render_template, request, jsonify
from database import db
from models import Article, CryptoPrice, NewsSourceMetrics, CryptoGlossary, Subscription
import logging
import re
from markupsafe import escape, Markup
from flask_socketio import SocketIO, emit
import json
from datetime import datetime, timedelta
import stripe
from datetime import datetime

# Create Flask app
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Initialize last run time in app config
app.config['LAST_SCRAPER_RUN'] = datetime.utcnow()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



# Stripe configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

@app.route('/stripe-config')
def stripe_config():
    return jsonify({
        'publishableKey': os.environ.get('STRIPE_PUBLISHABLE_KEY', 'pk_test_yourdefaultkey')
    }), 200

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

def check_subscription(feature='basic'):
    """
    Decorator to check subscription status and rate limits
    feature: 'basic' or 'pro' to indicate required subscription level
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # For now, we'll use a test user_id of 1
            # This should be replaced with actual user authentication later
            request.subscription = Subscription.query.filter_by(user_id=1, active=True).first()

            if feature == 'pro' and (not request.subscription or request.subscription.tier != 'pro'):
                return jsonify({'error': 'Pro subscription required'}), 403

            # Check rate limiting for basic features
            if request.subscription and request.subscription.rate_limit:
                current = Article.query.filter(
                    Article.created_at > datetime.utcnow() - timedelta(days=1)
                ).count()

                if current >= request.subscription.rate_limit:
                    return jsonify({'error': 'Rate limit exceeded'}), 429

            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
@check_subscription('basic')
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
                            news_sources=news_sources,
                            last_scraper_run=app.config['LAST_SCRAPER_RUN'])
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

# Add routes for subscription management
@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        domain_url = request.host_url.rstrip('/')
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Pro Subscription',
                        'description': 'Access to premium features'
                    },
                    'unit_amount': 4900,
                    'recurring': {
                        'interval': 'month'
                    }
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=domain_url + '/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=domain_url + '/cancelled',
        )
        return jsonify({'id': checkout_session.id, 'url': checkout_session.url})
    except Exception as e:
        return jsonify({'error': str(e)}), 403

@app.route('/success')
def success():
    session_id = request.args.get('session_id')
    if session_id:
        # Update user subscription
        subscription = Subscription(
            user_id=1,  # Replace with actual user ID
            tier='pro',
            expires_at=datetime.utcnow() + timedelta(days=30),
            rate_limit=1000
        )
        db.session.add(subscription)
        db.session.commit()
    return redirect('/')

@app.route('/subscription/status')
def subscription_status():
    subscription = Subscription.query.filter_by(user_id=1, active=True).first()
    if subscription:
        return jsonify({
            'tier': subscription.tier,
            'active': subscription.active,
            'expires_at': subscription.expires_at.isoformat(),
            'rate_limit': subscription.rate_limit
        })
    return jsonify({'tier': 'basic', 'active': True})


with app.app_context():
    try:
        db.create_all()
        sync_article_counts()  # Sync counts on startup
        logger.info("Successfully created database tables and synced counts")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")

if __name__ == '__main__':
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5000)), app)