import os
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, flash, url_for, session, make_response
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from database import db, init_app, sync_article_counts
from models import Article, CryptoPrice, NewsSourceMetrics, CryptoGlossary, Subscription, Users
import logging
import re
from markupsafe import escape, Markup
from flask_socketio import SocketIO, emit
import json
from datetime import datetime, timedelta
import stripe
from sqlalchemy import desc
import pandas as pd
import numpy as np
import eventlet
#from blockchain_metrics import EtherscanClient # Removed import as Etherscan is no longer used

eventlet.monkey_patch()

# Create Flask app
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

def filter_by_positive(value):
    return value.percent_change_24h > 0

def filter_by_negative(value):
    return value.percent_change_24h < 0

def apply_filter(sequence, fn):
    return [item for item in sequence if fn(item)]

app.jinja_env.filters['filter_by_positive'] = lambda x: apply_filter(x, filter_by_positive)
app.jinja_env.filters['filter_by_negative'] = lambda x: apply_filter(x, filter_by_negative)

# Initialize last run time in app config
app.config['LAST_SCRAPER_RUN'] = datetime.utcnow()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

# Add GA_TRACKING_ID to app config
app.config['GA_TRACKING_ID'] = os.environ.get('GA_TRACKING_ID', '')  # Default to empty string if not set

# Initialize database
init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Import CryptoPriceTracker after database initialization
from crypto_price_tracker import CryptoPriceTracker

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        terms = request.form.get('terms')

        if Users.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))

        if not terms:
            flash('You must accept the terms and conditions')
            return redirect(url_for('register'))

        user = Users(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        subscription = Subscription(
            user_id=user.id,
            tier='basic',
            expires_at=datetime.utcnow() + timedelta(days=365),
            rate_limit=100
        )
        db.session.add(subscription)
        db.session.commit()

        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Users.query.filter_by(email=request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('dashboard'))
        flash('Invalid email or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out successfully')
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    subscription = Subscription.query.filter_by(user_id=current_user.id, active=True).first()
    return render_template('profile.html', user=current_user, subscription=subscription)

@app.route('/')
def dashboard():
    try:
        logger.info("Starting dashboard view generation")

        # Fetch articles with error handling
        try:
            # Get articles from last 24 hours only
            cutoff_time = datetime.utcnow() - timedelta(hours=24) # Corrected to 24 hours
            recent_articles = Article.query.filter(
                Article.created_at >= cutoff_time
            ).order_by(Article.created_at.desc()).all()
            logger.info(f"Retrieved {len(recent_articles)} articles from last 24 hours")
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
                            last_scraper_run=app.config['LAST_SCRAPER_RUN'],
                            ga_tracking_id=app.config['GA_TRACKING_ID'])
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
                             categories=categories,
                             ga_tracking_id=app.config['GA_TRACKING_ID'])
    except Exception as e:
        logger.error(f"Error accessing glossary: {str(e)}")
        return "Error loading glossary", 500

@app.route('/glossary/<term_name>')
def get_term_details(term_name):
    try:
        # Convert URL-friendly term name back to proper format and make case-insensitive
        decoded_term = term_name.replace('-', ' ')
        term = CryptoGlossary.query.filter(
            CryptoGlossary.term.ilike(decoded_term)
        ).first_or_404()
        term.usage_count += 1
        db.session.commit()

        related_terms = []
        if term.related_terms:
            related_terms = CryptoGlossary.query.filter(
                CryptoGlossary.term.in_(term.related_terms.split(','))
            ).all()

        return render_template('term_details.html', 
                             term=term,
                             related_terms=related_terms,
                             ga_tracking_id=app.config['GA_TRACKING_ID'])
    except Exception as e:
        logger.error(f"Error getting term details: {str(e)}")
        return "Error loading term details", 500

@app.route('/crypto/<symbol>')
@check_subscription('basic')
def crypto_detail(symbol):
    try:
        logger.info(f"Accessing crypto detail page for symbol: {symbol}")
        symbol = symbol.upper()  # Normalize symbol to uppercase

        # Get current price data
        crypto_price = CryptoPrice.query.filter(CryptoPrice.symbol == symbol).first()
        if not crypto_price:
            logger.error(f"No price data found for symbol: {symbol}")
            flash(f"No data available for {symbol}", "error")
            return redirect(url_for('dashboard'))

        # Get related news articles (from last 7 days)
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=7)
            related_news = Article.query.filter(
                db.and_(
                    db.or_(
                        Article.content.ilike(f'%{symbol}%'),
                        Article.title.ilike(f'%{symbol}%')
                    ),
                    Article.created_at >= cutoff_time
                )
            ).order_by(desc(Article.created_at)).all()
            logger.info(f"Found {len(related_news)} related articles for {symbol}")

            # Calculate news impact
            news_impact = {
                'positive': 0,
                'negative': 0,
                'neutral': 0,
                'total_articles': len(related_news)
            }

            for article in related_news:
                if article.sentiment_label:
                    news_impact[article.sentiment_label.lower()] += 1

        except Exception as e:
            logger.error(f"Error fetching related news for {symbol}: {str(e)}")
            related_news = []
            news_impact = {'positive': 0, 'negative': 0, 'neutral': 0, 'total_articles': 0}

        # Calculate overall sentiment and trading signals
        total_articles = news_impact['total_articles']
        positive_ratio = news_impact['positive'] / total_articles if total_articles > 0 else 0
        negative_ratio = news_impact['negative'] / total_articles if total_articles > 0 else 0

        if positive_ratio > 0.6:
            recommendation = 'buy'
        elif negative_ratio > 0.6:
            recommendation = 'sell'
        else:
            recommendation = 'hold'

        logger.info(f"Generated {recommendation} recommendation for {symbol}")

        return render_template('crypto_detail.html',
                           crypto=crypto_price,
                           news=related_news,
                           news_impact=news_impact,
                           recommendation=recommendation,
                           ga_tracking_id=app.config['GA_TRACKING_ID'])

    except Exception as e:
        logger.error(f"Error in crypto detail page for {symbol}: {str(e)}", exc_info=True)
        return "Error loading cryptocurrency details", 500

@app.route('/api/price-history/<symbol>')
def price_history(symbol):
    try:
        timeframe = request.args.get('timeframe', '30d')  # Default to 30 days
        logger.info(f"Fetching price history for {symbol} with timeframe {timeframe}")

        # Normalize symbol
        symbol = symbol.upper()

        # Get coin id from symbol
        tracker = CryptoPriceTracker()
        coin_id = tracker.crypto_ids.get(symbol)
        if not coin_id:
            logger.error(f"No coin_id found for symbol {symbol}")
            return jsonify({'error': 'Cryptocurrency not supported'}), 404

        # Map timeframe to days
        timeframe_days = {
            '24h': 1,
            '7d': 7,
            '30d': 30
        }.get(timeframe, 30)

        logger.info(f"Using {timeframe_days} days for historical data")

        # Fetch historical data from CoinGecko
        api_url = f"{tracker.base_url}/coins/{coin_id}/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': timeframe_days,
            'interval': 'hourly' if timeframe == '24h' else 'daily'
        }
        logger.info(f"Calling CoinGecko API: {api_url} with params {params}")

        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Crypto Intelligence Platform)'
        }

        response = requests.get(api_url, params=params, headers=headers, timeout=15)
        response_data = response.json()

        logger.info(f"API Response status: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"API Error: {response_data.get('error', 'Unknown error')}")
            return jsonify({'error': 'Failed to fetch price data'}), response.status_code

        if not response_data.get('prices'):
            logger.error("No price data in response")
            return jsonify({'error': 'No price data available'}), 404

        formatted_data = {
            'prices': response_data['prices'],
            'volumes': response_data.get('total_volumes', []),
            'sma': []  # We'll calculate this below
        }

        # Calculate SMA if we have enough price points
        prices = response_data['prices']
        if len(prices) >= 7:
            formatted_data['sma'] = [
                {
                    'timestamp': prices[i][0],
                    'value': sum(p[1] for p in prices[i-7+1:i+1]) / 7
                }
                for i in range(6, len(prices))
            ]

        logger.info(f"Successfully processed data with {len(formatted_data['prices'])} price points")
        return jsonify(formatted_data)

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching price data: {str(e)}")
        return jsonify({'error': 'Failed to fetch price data'}), 503
    except Exception as e:
        logger.error(f"Unexpected error in price history endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/success')
@login_required
def success():
    session_id = request.args.get('session_id')
    if session_id:
        try:
            # Verify the session with Stripe
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status == 'paid':
                # Deactivate any existing subscriptions
                existing_subs = Subscription.query.filter_by(user_id=current_user.id, active=True).all()
                for sub in existing_subs:
                    sub.active = False

                # Create new subscription
                subscription = Subscription(
                    user_id=current_user.id,
                    tier='pro',
                    active=True,
                    expires_at=datetime.utcnow() + timedelta(days=30),
                    rate_limit=1000
                )
                db.session.add(subscription)
                db.session.commit()
                flash('Thank you for your subscription!', 'success')
                return redirect(url_for('profile'))

        except Exception as e:
            flash('Error processing payment', 'error')
            return redirect(url_for('profile'))

    return redirect(url_for('profile'))

@app.route('/sitemap.xml')
def sitemap():
    """Generate sitemap.xml. Makes a list of URLs and date modified."""
    pages = []

    # Static routes
    routes = ['/', '/about', '/pricing', '/contact', '/glossary', '/login', '/register']
    for route in routes:
        pages.append({
            'loc': request.url_root[:-1] + route,
            'lastmod': datetime.utcnow().strftime('%Y-%m-%d')
        })

    # Add crypto detail pages for each tracked cryptocurrency
    crypto_prices = CryptoPrice.query.all()
    for crypto in crypto_prices:
        pages.append({
            'loc': request.url_root[:-1] + f'/crypto/{crypto.symbol}',
            'lastmod': datetime.utcnow().strftime('%Y-%m-%d')
        })

    # Render template and ensure no whitespace before XML declaration
    sitemap_xml = render_template('sitemap.xml', pages=pages).strip()
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml;charset=utf-8"    
    return response

@app.route('/subscription/status')
def subscription_status():
    try:
        if current_user.is_authenticated:
            subscription = Subscription.query.filter_by(user_id=current_user.id, active=True).first()
            if subscription:
                return jsonify({
                    'tier': subscription.tier,
                    'active': subscription.active,
                    'expires_at': subscription.expires_at.isoformat(),
                    'rate_limit': subscription.rate_limit
                })
        return jsonify({'tier': 'basic', 'active': True, 'expires_at': None, 'rate_limit': 100})
    except Exception as e:
        return jsonify({'tier': 'basic', 'active': True, 'expires_at': None, 'rate_limit': 100})


@socketio.on('connect')
def handle_connect():
    logger.info("Client connected to WebSocket")

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected from WebSocket")

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

def sync_article_counts():
    """Synchronize article counts with actual numbers in database"""
    try:
        with app.app_context():
            sources = NewsSourceMetrics.query.all()
            for source in sources:
                count = Article.query.filter_by(source_name=source.source_name).count()
                source.article_count = count
                logger.info(f"Syncing article count for {source.source_name}: {count}")
            db.session.commit()
            logger.info("Successfully synchronized all article counts")
    except Exception as e:
        logger.error(f"Error syncing article counts: {str(e)}")
        db.session.rollback()

# Add routes for subscription management
@app.route('/create-checkout-session', methods=['POST'])
@login_required
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

@app.route('/about')
def about():
    return render_template('about.html', ga_tracking_id=app.config['GA_TRACKING_ID'])

@app.route('/pricing')
def pricing():
    return render_template('pricing.html', ga_tracking_id=app.config['GA_TRACKING_ID'])

@app.route('/contact')
def contact():
    return render_template('contact.html', ga_tracking_id=app.config['GA_TRACKING_ID'])

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    if not query:
        return redirect('/')

    # Map common names to symbols
    name_to_symbol = {
        'bitcoin': 'BTC',
        'ethereum': 'ETH',
        'binance': 'BNB',
        'cardano': 'ADA',
        'solana': 'SOL',
        'ripple': 'XRP',
        'dogecoin': 'DOGE',
        'polygon': 'MATIC',
        'avalanche': 'AVAX',
        'ondo': 'ONDO'  # Added Ondo token
    }

    # Try to find the symbol
    symbol = name_to_symbol.get(query, query.upper())

    return redirect(f'/crypto/{symbol}')

import requests
from crypto_price_tracker import CryptoPriceTracker

import time

# Add GA_TRACKING_ID to template context
@app.context_processor
def inject_ga_tracking_id():
    return dict(ga_tracking_id=app.config['GA_TRACKING_ID'])

with app.app_context():
    try:
        db.create_all()
        sync_article_counts()  # Sync counts on startup
        logger.info("Successfully created database tables and synced counts")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")

if __name__ == '__main__':
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5000)), app)