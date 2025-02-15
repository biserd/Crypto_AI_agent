# Monkey patch must happen before any other imports
import eventlet
eventlet.monkey_patch()

import os
import logging
from flask import Flask, render_template, request, jsonify, redirect, flash, url_for, session, make_response, send_from_directory
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from database import db, init_app, sync_article_counts
from models import Article, CryptoPrice, NewsSourceMetrics, CryptoGlossary, Subscription, Users
from markupsafe import escape, Markup
from flask_socketio import SocketIO, emit
import json
from datetime import datetime, timedelta
import stripe
from sqlalchemy import desc
import pandas as pd
import numpy as np
import re
import requests
from functools import wraps

# Configure logging first
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Configuration
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config['GA_TRACKING_ID'] = os.environ.get('GA_TRACKING_ID', '')

# Initialize database
init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize SocketIO with minimal configuration
socketio = SocketIO(
    app,
    async_mode='eventlet',
    cors_allowed_origins="*"
)

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
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            recent_articles = Article.query.filter(
                Article.created_at >= cutoff_time,
                Article.sentiment_score.isnot(None)  # Ensure sentiment score exists
            ).order_by(Article.created_at.desc()).all()

            # Set default values for any None fields
            for article in recent_articles:
                if article.sentiment_score is None:
                    article.sentiment_score = 0.0
                if article.sentiment_label is None:
                    article.sentiment_label = 'neutral'

            logger.info(f"Retrieved {len(recent_articles)} articles from last 24 hours")
        except Exception as e:
            logger.error(f"Error fetching articles: {str(e)}")
            recent_articles = []

        # Fetch crypto prices with error handling
        try:
            crypto_prices = CryptoPrice.query.filter(
                CryptoPrice.price_usd.isnot(None),
                CryptoPrice.percent_change_24h.isnot(None)
            ).all()

            # Set default values for any None fields
            for price in crypto_prices:
                if price.price_usd is None:
                    price.price_usd = 0.0
                if price.percent_change_24h is None:
                    price.percent_change_24h = 0.0

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

        # Calculate signals consistently
        try:
            # Apply sentiment analysis to all crypto prices
            for price in crypto_prices:
                try:
                    # Get recent news for this token
                    cutoff_time = datetime.utcnow() - timedelta(days=3)
                    related_news = Article.query.filter(
                        db.and_(
                            db.or_(
                                Article.content.ilike(f'%{price.symbol}%'),
                                Article.title.ilike(f'%{price.symbol}%')
                            ),
                            Article.created_at >= cutoff_time
                        )
                    ).order_by(Article.created_at.desc()).all()

                    # Calculate sentiment
                    total_articles = len(related_news)
                    # Use the unified signal calculation function
                    signals = calculate_crypto_signals(price.symbol, related_news, price)
                    price.signal = signals['signal']
                    price.confidence_score = signals['confidence']
                except Exception as e:
                    logger.error(f"Error calculating sentiment for {price.symbol}: {str(e)}")
                    price.confidence_score = 50.0
                    price.signal = 'hold'

            logger.info(f"Calculated signals for {len(crypto_prices)} cryptocurrencies")
        except Exception as e:
            logger.error(f"Error processing crypto data: {str(e)}")

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
                            buy_signals=crypto_prices, #Use crypto_prices as buy_signals now.
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

# Add crypto_names dictionary at the top level
crypto_names = {
    'BTC': 'Bitcoin',
    'ETH': 'Ethereum',
    'USDT': 'Tether',
    'BNB': 'Binance Coin',
    'SOL': 'Solana',
    'XRP': 'Ripple',
    'AVAX': 'Avalanche',
    'MEME': 'Memecoin',
    'SEI': 'Sei Network',
    'SUI': 'Sui',
    'BONK': 'Bonk',
    'WLD': 'Worldcoin',
    'PYTH': 'Pyth Network',
    'JUP': 'Jupiter',
    'BLUR': 'Blur',
    'HFT': 'Hashflow',
    'WIF': 'Wif Token',
    'STRK': 'Starknet',
    'TIA': 'Celestia',
    'DYM': 'Dymension',
    'ORDI': 'Ordinals',
    'USDC': 'USD Coin',
    'ADA': 'Cardano',
    'DOGE': 'Dogecoin',
    'TON': 'Toncoin',
    'TRX': 'TRON',
    'DAI': 'Dai',
    'MATIC': 'Polygon',
    'DOT': 'Polkadot',
    'WBTC': 'Wrapped Bitcoin',
    'AVAX': 'Avalanche',
    'SHIB': 'Shiba Inu',
    'LEO': 'LEO Token',
    'LTC': 'Litecoin',
    'UNI': 'Uniswap',
    'CAKE': 'PancakeSwap',
    'LINK': 'Chainlink',
    'ATOM': 'Cosmos',
    'APE': 'ApeCoin',
    'AAVE': 'Aave',
    'MELANX': 'Melania Token',
    'TRUMP': 'Trump Token',
    'TUSD': 'True USD',
    'KLAY': 'Klaytn',
    'GT': 'Gatetoken',
    'CHZ': 'Chiliz',
    'XEC': 'Ecash',
    'BEAM': 'Beam',
    'VRA': 'Virtuals',
    'NEAR': 'NEAR Protocol',
    'RNDR': 'Render Token',
    'ICP': 'Internet Computer',
    'TAO': 'Bittensor',
}

def calculate_crypto_signals(symbol, related_news=None, price_data=None):
    """Calculate unified crypto signals across the application"""
    try:
        if related_news is None:
            # Get related news from last 3 days for signal calculation
            cutoff_time = datetime.utcnow() - timedelta(days=3)
            related_news = Article.query.filter(
                db.and_(
                    db.or_(
                        Article.content.ilike(f'%{symbol}%'),
                        Article.title.ilike(f'%{symbol}%')
                    ),
                    Article.created_at >= cutoff_time
                )
            ).order_by(desc(Article.created_at)).all()

        total_articles = len(related_news)

        if total_articles > 0:
            positive_count = sum(1 for article in related_news if article.sentiment_label == 'positive')
            neutral_count = sum(1 for article in related_news if article.sentiment_label == 'neutral')
            negative_count = sum(1 for article in related_news if article.sentiment_label == 'negative')

            # Weight each sentiment type
            weighted_score = (positive_count * 1.2 + neutral_count * 0.2 - negative_count * 0.8) / total_articles

            if price_data and price_data.percent_change_24h:
                price_weight = 0.5 if price_data.percent_change_24h > 2.0 else (-0.5 if price_data.percent_change_24h < -2.0 else 0)
            else:
                price_weight = 0

            # Calculate final scores
            total_score = weighted_score + price_weight
            confidence = 50.0 + (total_score * 40.0) + (min(10.0, abs(price_data.percent_change_24h)) if price_data else 0)
            confidence = min(95.0, max(5.0, confidence))

            # Determine signal with consistent thresholds
            if total_score > 0.4 and (price_data and price_data.percent_change_24h > 2.0):
                signal = 'buy'
            elif total_score < -0.4 or (price_data and price_data.percent_change_24h < -6.0):
                signal = 'sell'
            else:
                signal = 'hold'
        else:
            confidence = 50.0
            signal = 'hold'

        return {
            'signal': signal,
            'confidence': confidence,
            'total_articles': total_articles
        }
    except Exception as e:
        logger.error(f"Error calculating signals for {symbol}: {str(e)}")
        return {'signal': 'hold', 'confidence': 50.0, 'total_articles': 0}

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

        # Calculate signals using unified function
        signals = calculate_crypto_signals(symbol, related_news, crypto_price)
        recommendation = signals['signal']

        logger.info(f"Generated {recommendation} recommendation for {symbol}")

        return render_template('crypto_detail.html',
                           crypto=crypto_price,
                           news=related_news,
                           news_impact=news_impact,
                           recommendation=recommendation,
                           crypto_names=crypto_names,
                           ga_tracking_id=app.config['GA_TRACKING_ID'])

    except Exception as e:
        logger.error(f"Error in crypto detail page for {symbol}: {str(e)}", exc_info=True)
        flash("Error loading cryptocurrency details. Please try again later.", "error")
        return redirect(url_for('dashboard'))

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
    priorities = {
        '/': '1.0',
        '/about': '0.8',
        '/glossary': '0.9',
        '/crypto': '0.9',
        '/contact': '0.7',
        '/pricing': '0.8'
    }
    for route in routes:
        pages.append({
            'loc': request.url_root[:-1] + route,
            'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
            'changefreq': 'daily' if route == '/' else 'weekly',
            'priority': priorities.get(route, '0.5')
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

@app.route('/api/price-history/<symbol>')
def price_history(symbol):
    try:
        logger.info(f"Fetching price history for {symbol}")
        days = request.args.get('days', default=30, type=int)

        # Normalize symbol
        symbol = symbol.upper()

        # Initialize tracker
        tracker = CryptoPriceTracker()

        # Check if symbol exists in our tracked cryptocurrencies
        if symbol not in tracker.crypto_ids:
            logger.error(f"Symbol {symbol} not found in supported cryptocurrencies")
            return jsonify({
                'error': f'Cryptocurrency {symbol} is not supported',
                'symbol': symbol,
                'supported_symbols': list(tracker.crypto_ids.keys())
            }), 404

        # Get historical data using the tracker
        historical_data = tracker.get_historical_prices(symbol, days=days)

        logger.debug(f"Raw historical data type: {type(historical_data)}")
        logger.debug(f"Raw historical data keys: {historical_data.keys() if isinstance(historical_data, dict) else 'Not a dict'}")

        # Validate the historical data structure
        if not historical_data or not isinstance(historical_data, dict):
            logger.error(f"Invalid historical data type for {symbol}: {type(historical_data)}")
            return jsonify({
                'error': f'Invalid data format received for {symbol}',
                'symbol': symbol
            }), 500

        # Ensure both prices and total_volumes exist and are lists
        prices = historical_data.get('prices', [])
        volumes = historical_data.get('total_volumes', [])

        if not isinstance(prices, list) or not isinstance(volumes, list):
            logger.error(f"Invalid price or volume data type for {symbol}")
            return jsonify({
                'error': f'Invalid price or volume data for {symbol}',
                'symbol': symbol
            }), 500

        # Filter out any invalid data points
        prices = [p for p in prices if isinstance(p, list) and len(p) == 2 and 
                  all(isinstance(x, (int, float)) or 
                      (isinstance(x, str) and x.replace('.', '').isdigit()) 
                      for x in p)]

        volumes = [v for v in volumes if isinstance(v, list) and len(v) == 2 and 
                  all(isinstance(x, (int, float)) or 
                      (isinstance(x, str) and x.replace('.', '').isdigit()) 
                      for x in v)]

        if not prices:
            logger.error(f"No valid price data points for {symbol}")
            return jsonify({
                'error': f'No valid price data available for {symbol}',
                'symbol': symbol
            }), 500

        logger.info(f"Successfully fetched price history for {symbol}")
        logger.debug(f"Returning {len(prices)} price points and {len(volumes)} volume points")

        return jsonify({
            'prices': prices,
            'total_volumes': volumes
        })

    except Exception as e:
        logger.error(f"Error in price history endpoint for {symbol}: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

# Add the following route after the existing routes but before the if __name__ == '__main__': block
@app.route('/robots.txt')
def serve_robots():
    """Serve robots.txt file"""
    try:
        logger.info("Serving robots.txt file")
        return send_from_directory(app.static_folder or app.root_path, 'robots.txt', mimetype='text/plain')
    except Exception as e:
        logger.error(f"Error serving robots.txt: {str(e)}")
        return "User-agent: *\nAllow: /\n", 200, {'Content-Type': 'text/plain'}

@app.route('/api/load-more-articles')
def load_more_articles():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10

        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        articles = Article.query.filter(
            Article.created_at >= cutoff_time,
            Article.sentiment_score.isnot(None)
        ).order_by(Article.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        if not articles.items:
            return jsonify({'articles': [], 'has_more': False})

        # Process articles similar to dashboard
        crypto_prices = getattr(app, 'crypto_prices', [])
        news_sources = getattr(app, 'news_sources', [])
        crypto_symbols = {crypto.symbol: crypto for crypto in crypto_prices}

        processed_articles = []
        for article in articles.items:
            try:
                enhanced_summary = escape(article.summary)
                for symbol, crypto in crypto_symbols.items():
                    pattern = re.compile(r'\b' + re.escape(symbol) + r'\b', re.IGNORECASE)
                    if pattern.search(str(enhanced_summary)):
                        tooltip_html = Markup(
                            f'<span class="crypto-tooltip">{symbol}'
                            f'<div class="tooltip-content">'
                            f'<span class="tooltip-price">${crypto.price_usd:.2f}</span>'
                            f'<span class="tooltip-change {("positive" if crypto.percent_change_24h > 0 else "negative")}">'
                            f'{crypto.percent_change_24h:.1f}%</span>'
                            f'</div></span>'
                        )
                        enhanced_summary = Markup(pattern.sub(str(tooltip_html), str(enhanced_summary)))

            except Exception as e:
                logger.error(f"Error processing tooltips for article {article.id}: {str(e)}")
                enhanced_summary = article.summary

            source_metrics = next(
                (source for source in news_sources if source.source_name == article.source_name),
                None
            )

            processed_article = {
                'id': article.id,
                'title': article.title,
                'content': article.content,
                'summary': str(enhanced_summary),
                'source_name': article.source_name,
                'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'sentiment_label': article.sentiment_label,
                'sentiment_score': article.sentiment_score,
                'url': article.url,
                'source_url': article.source_url,
                'source_metrics': {
                    'trust_score': source_metrics.trust_score if source_metrics else None
                } if source_metrics else None
            }
            processed_articles.append(processed_article)

        return jsonify({
            'articles': processed_articles,
            'has_more': articles.pages > page
        })

    except Exception as e:
        logger.error(f"Error loading more articles: {str(e)}")
        return jsonify({'error': str(e)}), 500

with app.app_context():
    try:
        db.create_all()
        sync_article_counts()
        logger.info("Successfully created database tables and synced counts")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        db.session.rollback()

if __name__ == "__main__":
    try:
        logger.info("Starting server with SocketIO support...")

        # Initialize database tables within app context
        with app.app_context():
            try:
                logger.info("Creating database tables...")
                db.create_all()
                logger.info("Database tables created successfully")

                logger.info("Syncing article counts...")
                sync_article_counts()
                logger.info("Article counts synced successfully")
            except Exception as e:
                logger.error(f"Error during database initialization: {str(e)}", exc_info=True)
                raise

        # Start the server with minimal configuration
        logger.info("Starting SocketIO server...")
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=False  # Disable reloader when using eventlet
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}", exc_info=True)
        raise