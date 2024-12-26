import logging
import os
from app import db
from models import Article
import spacy
import time
from pathlib import Path

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_sentiment(text):
    """Analyze sentiment using crypto-specific lexicon with enhanced error handling"""
    try:
        logger.debug(f"Starting sentiment analysis for text (length: {len(text)})")

        # Enhanced crypto-specific sentiment words
        positive_words = {
            'bullish', 'surge', 'rally', 'gain', 'growth', 'profit', 'adoption',
            'innovation', 'partnership', 'success', 'breakthrough', 'upgrade',
            'support', 'launch', 'integration', 'milestone', 'achievement',
            'positive', 'boost', 'advance', 'progress', 'improve', 'recovery',
            'strengthen', 'momentum', 'optimistic', 'soar', 'peak', 'record-high'
        }
        negative_words = {
            'bearish', 'crash', 'drop', 'decline', 'loss', 'risk', 'scam',
            'hack', 'breach', 'concern', 'warning', 'vulnerability', 'ban',
            'sell-off', 'dump', 'lawsuit', 'regulation', 'investigation',
            'negative', 'fail', 'threat', 'weak', 'uncertain', 'volatile',
            'downward', 'struggle', 'panic', 'plunge', 'collapse', 'crisis'
        }

        # Input validation
        if not text or len(text.strip()) == 0:
            logger.warning("Empty text provided for sentiment analysis")
            return 0.0, 'neutral'

        # Convert to lowercase and split into words
        text_lower = text.lower()
        words = text_lower.split()

        # Count sentiment words with context
        pos_count = 0
        neg_count = 0

        # Consider negation words
        negation_words = {'not', 'no', "n't", 'never', 'neither', 'nor', 'none'}
        skip_next = False

        for i, word in enumerate(words):
            if skip_next:
                skip_next = False
                continue

            # Check for negation
            is_negated = False
            if i > 0 and any(neg in words[i-1] for neg in negation_words):
                is_negated = True

            # Count sentiment considering negation
            if word in positive_words:
                if is_negated:
                    neg_count += 1
                else:
                    pos_count += 1
            elif word in negative_words:
                if is_negated:
                    pos_count += 1
                else:
                    neg_count += 1

        logger.debug(f"Found {pos_count} positive words and {neg_count} negative words in {len(words)} total words")

        # Calculate sentiment score with enhanced thresholds
        total_words = max(len(words), 1)  # Prevent division by zero
        score = (pos_count - neg_count) / total_words

        # Determine sentiment label with adjusted thresholds
        if score > 0.02:  # More sensitive threshold for positive sentiment
            logger.debug(f"Determined positive sentiment with score {score:.4f}")
            return score, 'positive'
        elif score < -0.02:  # More sensitive threshold for negative sentiment
            logger.debug(f"Determined negative sentiment with score {score:.4f}")
            return score, 'negative'
        else:
            logger.debug(f"Determined neutral sentiment with score {score:.4f}")
            return score, 'neutral'

    except Exception as e:
        logger.error(f"Error in sentiment analysis: {str(e)}")
        return 0.0, 'neutral'  # Default to neutral on error

def process_articles():
    """Process all unprocessed articles with sentiment analysis"""
    logger.info("Starting article processing")
    try:
        # Process articles without sentiment
        articles = Article.query.filter(
            (Article.sentiment_label.is_(None)) | 
            (Article.sentiment_label == '')
        ).all()

        logger.info(f"Found {len(articles)} articles to process")

        if not articles:
            logger.info("No articles found needing sentiment analysis")
            return

        processed_count = 0
        for article in articles:
            try:
                logger.debug(f"Processing article {article.id}: {article.title}")

                # Analyze sentiment
                score, label = analyze_sentiment(article.content)
                article.sentiment_score = score
                article.sentiment_label = label

                # Set category based on content
                content_lower = article.content.lower()
                if any(word in content_lower for word in ['bitcoin', 'btc', 'crypto', 'blockchain', 'defi', 'eth', 'ethereum']):
                    article.category = 'Crypto Markets'
                elif any(word in content_lower for word in ['technology', 'protocol', 'network', 'platform']):
                    article.category = 'Technology'
                else:
                    article.category = 'General'

                processed_count += 1
                logger.info(f"Successfully processed article {article.id}: Category={article.category}, Sentiment={label}")

            except Exception as e:
                logger.error(f"Error processing article {article.id}: {str(e)}")
                continue

        # Commit all changes
        if processed_count > 0:
            db.session.commit()
            logger.info(f"Successfully processed and committed {processed_count} articles")
        else:
            logger.info("No articles were processed successfully")

    except Exception as e:
        logger.error(f"Error in process_articles: {str(e)}")
        db.session.rollback()
        raise

if __name__ == "__main__":
    process_articles()