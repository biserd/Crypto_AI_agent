from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def init_app(app):
    """Initialize the database with the app context"""
    # Configure the SQLAlchemy part of the app instance
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config.get("SQLALCHEMY_DATABASE_URI")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # Initialize SQLAlchemy with the app
    db.init_app(app)

    with app.app_context():
        # Import models here to avoid circular imports
        import models  # noqa: F401

        # Create all tables
        db.create_all()

def sync_article_counts():
    """Sync article counts for all news sources"""
    from models import Article, NewsSourceMetrics
    try:
        sources = NewsSourceMetrics.query.all()
        for source in sources:
            count = Article.query.filter_by(source_name=source.source_name).count()
            source.article_count = count
        db.session.commit()
    except Exception as e:
        import logging
        logging.error(f"Error syncing article counts: {str(e)}")
        db.session.rollback()