import logging
import os
import re
from app import db
from models import Article
import time
from pathlib import Path

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_sentiment(text):
    """Analyze sentiment using crypto-specific lexicon and contextual analysis"""
    try:
        logger.debug(f"Starting sentiment analysis for text (length: {len(text)})")

        # Enhanced crypto-specific sentiment words and phrases with weights
        positive_patterns = {
            # Price movements (weight: 1.0)
            'surge': 1.0, 'rally': 1.0, 'jump': 1.0, 'gain': 1.0, 'soar': 1.0, 'rise': 1.0, 'climb': 1.0, 
            'peak': 1.0, 'record high': 1.2,
            # Market sentiment (weight: 1.2)
            'bullish': 1.2, 'optimistic': 1.2, 'confident': 1.2, 'strong': 1.0, 'positive': 1.0, 
            'opportunity': 1.0,
            # Adoption/Development (weight: 1.5)
            'adoption': 1.5, 'partnership': 1.5, 'launch': 1.2, 'upgrade': 1.2, 'integration': 1.2, 
            'milestone': 1.2, 'development': 1.2, 'progress': 1.2, 'innovation': 1.5, 'breakthrough': 1.5,
            'success': 1.2,
        }

        negative_patterns = {
            # Price movements (weight: 1.5)
            'crash': 1.5, 'plunge': 1.5, 'drop': 1.2, 'fall': 1.2, 'decline': 1.2, 'tumble': 1.5, 
            'slump': 1.5, 'correction': 1.2,
            # Market sentiment (weight: 1.2)
            'bearish': 1.2, 'pessimistic': 1.2, 'fear': 1.2, 'concern': 1.0, 'worry': 1.0, 
            'uncertain': 1.0, 'volatile': 1.0,
            # Security/Risk (weight: 2.0)
            'hack': 2.0, 'breach': 2.0, 'scam': 2.0, 'fraud': 2.0, 'vulnerability': 1.5, 
            'exploit': 1.5, 'risk': 1.2,
            # Regulatory (weight: 1.5)
            'ban': 1.5, 'restrict': 1.5, 'crack down': 1.5, 'investigate': 1.2, 'sue': 1.5, 
            'lawsuit': 1.5, 'illegal': 1.5,
            # Market problems (weight: 1.8)
            'sell-off': 1.8, 'dump': 1.8, 'liquidation': 1.8, 'margin call': 1.8, 'default': 1.8
        }

        if not text or len(text.strip()) == 0:
            logger.warning("Empty text provided for sentiment analysis")
            return 0.0, 'neutral'

        text = text.lower()
        sentences = text.split('.')

        weighted_pos_score = 0
        weighted_neg_score = 0
        total_matches = 0

        for sentence in sentences:
            if not sentence.strip():
                continue

            has_negation = any(neg in sentence for neg in {'not', 'no', "n't", 'never', 'without', 'rarely'})

            # Calculate weighted sentiment scores
            for pattern, weight in positive_patterns.items():
                if pattern in sentence:
                    if has_negation:
                        weighted_neg_score += weight
                    else:
                        weighted_pos_score += weight
                    total_matches += 1

            for pattern, weight in negative_patterns.items():
                if pattern in sentence:
                    if has_negation:
                        weighted_pos_score += weight * 0.5  # Negated negative is less positive
                    else:
                        weighted_neg_score += weight
                    total_matches += 1

        if total_matches == 0:
            logger.debug("No sentiment patterns found in text")
            return 0.0, 'neutral'

        # Calculate weighted sentiment score
        sentiment_score = (weighted_pos_score - weighted_neg_score) / max(total_matches, 1)

        logger.debug(f"Sentiment analysis results: positive={weighted_pos_score}, "
                    f"negative={weighted_neg_score}, total_matches={total_matches}, "
                    f"score={sentiment_score:.4f}")

        # Adjusted thresholds with bias towards negative sentiment
        if sentiment_score > 0.3:
            logger.info(f"Positive sentiment detected with score {sentiment_score:.4f}")
            return sentiment_score, 'positive'
        elif sentiment_score < -0.1:  # More sensitive to negative sentiment
            logger.info(f"Negative sentiment detected with score {sentiment_score:.4f}")
            return sentiment_score, 'negative'
        else:
            logger.info(f"Neutral sentiment detected with score {sentiment_score:.4f}")
            return sentiment_score, 'neutral'

    except Exception as e:
        logger.error(f"Error in sentiment analysis: {str(e)}")
        return 0.0, 'neutral'

def process_articles():
    """Process all unprocessed articles with sentiment analysis"""
    logger.info("Starting article processing")
    try:
        # Process articles without sentiment and reprocess articles with empty sentiment
        articles = Article.query.filter(
            (Article.sentiment_label.is_(None)) | 
            (Article.sentiment_label == '')
        ).all()

        logger.info(f"Found {len(articles)} articles to process")

        if not articles:
            logger.info("No articles found needing sentiment analysis")
            return

        # Define crypto assets and their tickers
        crypto_assets = {
            'bitcoin': 'BTC',
            'btc': 'BTC',
            'ethereum': 'ETH',
            'eth': 'ETH',
            'binance coin': 'BNB',
            'bnb': 'BNB',
            'cardano': 'ADA',
            'ada': 'ADA',
            'solana': 'SOL',
            'sol': 'SOL',
            'xrp': 'XRP',
            'ripple': 'XRP',
            'dogecoin': 'DOGE',
            'doge': 'DOGE',
            'polygon': 'MATIC',
            'matic': 'MATIC',
            'avalanche': 'AVAX',
            'avax': 'AVAX'
        }

        processed_count = 0
        for article in articles:
            try:
                logger.debug(f"Processing article {article.id}: {article.title}")

                # Combine title and content for better context
                full_text = f"{article.title}. {article.content}"

                # Format content with bold assets and tickers
                formatted_content = article.content
                formatted_title = article.title

                for asset, ticker in crypto_assets.items():
                    # Create pattern that matches word boundaries
                    pattern = re.compile(rf'\b{asset}\b', re.IGNORECASE)
                    replacement = f'**{asset.title()}** (${ticker})'

                    formatted_content = pattern.sub(replacement, formatted_content)
                    formatted_title = pattern.sub(replacement, formatted_title)

                article.content = formatted_content
                article.title = formatted_title

                # Analyze sentiment
                score, label = analyze_sentiment(full_text)
                article.sentiment_score = score
                article.sentiment_label = label

                processed_count += 1
                logger.info(f"Successfully processed article {article.id}: Sentiment={label} (score={score:.4f})")

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