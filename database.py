from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def sync_article_counts():
    """Sync article counts for all news sources"""
    try:
        sources = NewsSourceMetrics.query.all()
        for source in sources:
            count = Article.query.filter_by(source_name=source.source_name).count()
            source.article_count = count
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Error syncing article counts: {str(e)}")