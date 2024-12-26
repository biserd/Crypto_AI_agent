import logging
import os
from app import db
from models import Article
import spacy
from spacy.cli import download

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def initialize_spacy():
    """Initialize SpaCy with error handling and logging"""
    try:
        logger.info("Attempting to load SpaCy model")
        try:
            nlp = spacy.load("en_core_web_sm")
            logger.info("Successfully loaded existing SpaCy model")
            return nlp
        except OSError:
            logger.info("Model not found, downloading en_core_web_sm")
            download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
            logger.info("Successfully downloaded and loaded SpaCy model")
            return nlp
    except Exception as e:
        logger.error(f"Failed to initialize SpaCy: {str(e)}")
        return None

# Initialize SpaCy
nlp = initialize_spacy()

def analyze_sentiment(text):
    """Analyze sentiment of text using custom word lists"""
    if nlp is None:
        logger.error("NLP model not initialized, returning neutral sentiment")
        return 0.0, 'neutral'

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

        doc = nlp(text.lower())
        sentiment_score = 0
        word_count = 0

        for token in doc:
            if not token.is_punct and not token.is_space:
                if token.text in positive_words:
                    sentiment_score += 1
                    word_count += 1
                elif token.text in negative_words:
                    sentiment_score -= 1
                    word_count += 1

        # Normalize score
        final_score = sentiment_score / max(word_count, 1)

        # Convert score to label
        if final_score > 0.2:
            label = 'positive'
        elif final_score < -0.2:
            label = 'negative'
        else:
            label = 'neutral'

        logger.debug(f"Sentiment analysis results - Score: {final_score}, Label: {label}")
        return final_score, label

    except Exception as e:
        logger.error(f"Error in sentiment analysis: {str(e)}")
        return 0.0, 'neutral'

def process_articles():
    """Process all articles with sentiment analysis"""
    if nlp is None:
        logger.error("SpaCy is not initialized. Cannot process articles.")
        return

    logger.info("Starting article processing")
    try:
        articles = Article.query.all()
        logger.info(f"Found {len(articles)} articles to process")

        for article in articles:
            try:
                # Analyze sentiment
                score, label = analyze_sentiment(article.content)
                article.sentiment_score = score
                article.sentiment_label = label

                # Set category
                content_lower = article.content.lower()
                if any(word in content_lower for word in ['bitcoin', 'crypto', 'blockchain', 'defi']):
                    article.category = 'Crypto Markets'
                elif any(word in content_lower for word in ['technology', 'protocol', 'network']):
                    article.category = 'Technology'
                else:
                    article.category = 'General'

                logger.info(f"Processed article {article.id}: Category={article.category}, Sentiment={label}")

            except Exception as e:
                logger.error(f"Error processing article {article.id}: {str(e)}")
                continue

        db.session.commit()
        logger.info("Successfully processed all articles")

    except Exception as e:
        logger.error(f"Error in process_articles: {str(e)}")

if __name__ == "__main__":
    process_articles()