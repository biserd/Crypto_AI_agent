import os
from flask import Flask, render_template
import logging
from database import db
from models import Article, CryptoPrice

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

    logging.info(f"Found {len(recent_articles)} articles to display")
    return render_template('dashboard.html', 
                         articles=recent_articles,
                         crypto_prices=crypto_prices)

with app.app_context():
    db.create_all()