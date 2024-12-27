from datetime import datetime
from database import db

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)  # Will be linked to User model later
    tier = db.Column(db.String(20), nullable=False)  # 'basic', 'pro'
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    rate_limit = db.Column(db.Integer)  # Requests per day

    def __repr__(self):
        return f'<Subscription {self.tier}>'

class NewsSourceMetrics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(100), unique=True, nullable=False)
    trust_score = db.Column(db.Float, default=0.0)  # 0-100 scale
    article_count = db.Column(db.Integer, default=0)
    accuracy_score = db.Column(db.Float, default=0.0)  # Based on fact checking
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<NewsSourceMetrics {self.source_name}: {self.trust_score}>'

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
    accuracy_verified = db.Column(db.Boolean, default=False)  # For fact-checking tracking
    trust_impact = db.Column(db.Float, default=0.0)  # Impact on source trust score

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

class CryptoGlossary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(100), unique=True, nullable=False)
    definition = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # e.g., Technical, Trading, DeFi
    difficulty_level = db.Column(db.String(20))  # Beginner, Intermediate, Advanced
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usage_count = db.Column(db.Integer, default=0)  # Track how often term is viewed
    related_terms = db.Column(db.String(200))  # Comma-separated related terms

    def __repr__(self):
        return f'<CryptoGlossary {self.term}>'