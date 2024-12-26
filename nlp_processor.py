import logging
import os
from app import db
from models import Article
import spacy
import time

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def initialize_spacy():
    """Initialize SpaCy with robust error handling"""
    try:
        logger.info("Attempting to load SpaCy model")
        try:
            nlp = spacy.load("en_core_web_sm")
            logger.info("Successfully loaded SpaCy model")
            return nlp
        except Exception as e:
            logger.error(f"Failed to load SpaCy model: {str(e)}")
            return None
    except Exception as e:
        logger.error(f"Critical error in SpaCy initialization: {str(e)}")
        return None

def analyze_sentiment(text):
    """Analyze sentiment using crypto-specific lexicon"""
    try:
        # Crypto-specific sentiment words
        positive_words = {
            'bullish', 'surge', 'rally', 'gain', 'growth', 'profit', 'adoption',
            'innovation', 'partnership', 'success', 'breakthrough', 'upgrade',
            'support', 'launch', 'integration', 'milestone', 'achievement'
        }
        negative_words = {
            'bearish', 'crash', 'drop', 'decline', 'loss', 'risk', 'scam',
            'hack', 'breach', 'concern', 'warning', 'vulnerability', 'ban',
            'sell-off', 'dump', 'lawsuit', 'regulation', 'investigation'
        }

        words = text.lower().split()
        pos_count = sum(1 for word in words if word in positive_words)
        neg_count = sum(1 for word in words if word in negative_words)

        score = (pos_count - neg_count) / max(len(words), 1)

        if score > 0.1:
            return 0.5, 'positive'
        elif score < -0.1:
            return -0.5, 'negative'
        return 0.0, 'neutral'

    except Exception as e:
        logger.error(f"Error in sentiment analysis: {str(e)}")
        return 0.0, 'neutral'

def process_articles():
    """Process all unprocessed articles with sentiment analysis"""
    logger.info("Starting article processing")
    try:
        # Only process articles without sentiment
        articles = Article.query.filter_by(sentiment_label=None).all()
        logger.info(f"Found {len(articles)} articles to process")

        processed_count = 0
        for article in articles:
            try:
                # Analyze sentiment
                score, label = analyze_sentiment(article.content)
                article.sentiment_score = score
                article.sentiment_label = label

                # Set category based on content
                content_lower = article.content.lower()
                if any(word in content_lower for word in ['bitcoin', 'crypto', 'blockchain', 'defi']):
                    article.category = 'Crypto Markets'
                elif any(word in content_lower for word in ['technology', 'protocol', 'network']):
                    article.category = 'Technology'
                else:
                    article.category = 'General'

                processed_count += 1
                logger.info(f"Processed article {article.id}: Category={article.category}, Sentiment={label}")

            except Exception as e:
                logger.error(f"Error processing article {article.id}: {str(e)}")
                continue

        db.session.commit()
        logger.info(f"Successfully processed {processed_count} articles")

    except Exception as e:
        logger.error(f"Error in process_articles: {str(e)}")
        db.session.rollback()

if __name__ == "__main__":
    process_articles()