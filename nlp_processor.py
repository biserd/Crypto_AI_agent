import logging
from app import db
from models import Article

def process_articles():
    """Process unprocessed articles with basic NLP pipeline"""
    logging.info("Starting NLP processing")

    # Get unprocessed articles (those without summaries)
    articles = Article.query.filter_by(summary=None).all()
    logging.info(f"Found {len(articles)} articles to process")

    for article in articles:
        try:
            # Simple extractive summarization
            sentences = article.content.split('.')
            important_sentences = sentences[:3]  # Take first 3 sentences as summary

            article.summary = '. '.join(important_sentences) + '.'

            # Basic categorization based on keywords
            content_lower = article.content.lower()
            if any(word in content_lower for word in ['market', 'stock', 'economy']):
                article.category = 'Business'
            elif any(word in content_lower for word in ['government', 'president', 'election']):
                article.category = 'Politics'
            else:
                article.category = 'General'

            db.session.commit()
            logging.info(f"Successfully processed article: {article.id}")

        except Exception as e:
            logging.error(f"Error processing article {article.id}: {str(e)}")
            continue

    logging.info("Completed NLP processing")