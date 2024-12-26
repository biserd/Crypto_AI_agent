from datetime import datetime
from database import db

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    source_url = db.Column(db.String(1000), nullable=False)
    source_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    published = db.Column(db.Boolean, default=False)
    sentiment_score = db.Column(db.Float)  # Overall sentiment score
    sentiment_label = db.Column(db.String(20))  # Positive, Negative, or Neutral

    def __repr__(self):
        return f'<Article {self.title}>'

class DistributionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False)  # 'twitter' or 'telegram'
    status = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    message = db.Column(db.Text)

class CryptoPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)  # e.g., BTC, ETH
    price_usd = db.Column(db.Float, nullable=False)
    percent_change_24h = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CryptoPrice {self.symbol}: ${self.price_usd:.2f}>'