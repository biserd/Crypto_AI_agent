import logging
import os
from app import db
from models import Article
import spacy
from spacy.cli import download
import time

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def initialize_spacy(max_retries=3):
    """Initialize SpaCy with robust error handling and retries"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1} to initialize SpaCy")
            try:
                # Try loading existing model
                nlp = spacy.load("en_core_web_sm")
                logger.info("Successfully loaded existing SpaCy model")
                return nlp
            except OSError:
                # Model doesn't exist, try downloading
                logger.info("Model not found, attempting download")
                download("en_core_web_sm")
                time.sleep(2)  # Wait for download to complete
                nlp = spacy.load("en_core_web_sm")
                logger.info("Successfully downloaded and loaded SpaCy model")
                return nlp
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retrying
                continue
            else:
                logger.error("All attempts to initialize SpaCy failed")
                return None

def analyze_sentiment_fallback(text):
    """Simple rule-based sentiment analysis as fallback"""
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

    text_lower = text.lower()
    words = text_lower.split()

    pos_count = sum(1 for word in words if word in positive_words)
    neg_count = sum(1 for word in words if word in negative_words)

    score = (pos_count - neg_count) / max(len(words), 1)

    if score > 0.1:
        return 0.5, 'positive'
    elif score < -0.1:
        return -0.5, 'negative'
    return 0.0, 'neutral'

# Initialize SpaCy with retries
nlp = initialize_spacy()
logger.info("SpaCy initialization completed with status: %s", "Success" if nlp else "Failed")

def analyze_sentiment(text):
    """Analyze sentiment of text using SpaCy or fallback to rule-based"""
    if nlp is None:
        logger.warning("Using fallback sentiment analysis due to missing SpaCy model")
        return analyze_sentiment_fallback(text)

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

        final_score = sentiment_score / max(word_count, 1)

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
        logger.info("Falling back to basic sentiment analysis")
        return analyze_sentiment_fallback(text)

def process_articles():
    """Process all articles with sentiment analysis"""
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