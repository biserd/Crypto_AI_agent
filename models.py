
from datetime import datetime
from database import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subscriptions = db.relationship('Subscription', backref='users', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
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
    sentiment_score = db.Column(db.Float)
    sentiment_label = db.Column(db.String(20))
    accuracy_verified = db.Column(db.Boolean, default=False)
    trust_impact = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f'<Article {self.title}>'

class DistributionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    message = db.Column(db.Text)

class CryptoPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    price_usd = db.Column(db.Float, nullable=False)
    percent_change_24h = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CryptoPrice {self.symbol}: ${self.price_usd:.2f}>'

class TokenSignal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    signal_type = db.Column(db.String(10), nullable=False)  # 'buy', 'sell', 'hold'
    confidence_score = db.Column(db.Float, nullable=False)
    price_at_signal = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    analysis_summary = db.Column(db.Text)

class CryptoGlossary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(100), unique=True, nullable=False)
    definition = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    difficulty_level = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usage_count = db.Column(db.Integer, default=0)
    related_terms = db.Column(db.String(200))

    def __repr__(self):
        return f'<CryptoGlossary {self.term}>'
