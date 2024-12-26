import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import logging

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
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
    from models import Article
    logging.info("Fetching articles for dashboard")
    # Remove the published filter to show all articles
    recent_articles = Article.query.order_by(Article.created_at.desc()).all()
    logging.info(f"Found {len(recent_articles)} articles to display")
    return render_template('dashboard.html', articles=recent_articles)

with app.app_context():
    import models
    db.create_all()