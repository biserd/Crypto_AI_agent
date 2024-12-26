import logging
import os
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

        # Enhanced crypto-specific sentiment words and phrases
        positive_patterns = {
            # Price movements
            'surge', 'rally', 'jump', 'gain', 'soar', 'rise', 'climb', 'peak', 'record high',
            # Market sentiment
            'bullish', 'optimistic', 'confident', 'strong', 'positive', 'opportunity',
            # Adoption/Development
            'adoption', 'partnership', 'launch', 'upgrade', 'integration', 'milestone',
            'development', 'progress', 'innovation', 'breakthrough', 'success',
            # Regulatory
            'approve', 'support', 'legal', 'regulate', 'compliance',
        }

        negative_patterns = {
            # Price movements
            'crash', 'plunge', 'drop', 'fall', 'decline', 'tumble', 'slump', 'correction',
            # Market sentiment
            'bearish', 'pessimistic', 'fear', 'concern', 'worry', 'uncertain', 'volatile',
            # Security/Risk
            'hack', 'breach', 'scam', 'fraud', 'vulnerability', 'exploit', 'risk',
            # Regulatory
            'ban', 'restrict', 'crack down', 'investigate', 'sue', 'lawsuit', 'illegal',
            # Market problems
            'sell-off', 'dump', 'liquidation', 'margin call', 'default'
        }

        # Input validation
        if not text or len(text.strip()) == 0:
            logger.warning("Empty text provided for sentiment analysis")
            return 0.0, 'neutral'

        # Preprocess text
        text = text.lower().replace('\n', ' ').replace('\t', ' ')

        # Clean up extra spaces
        while '  ' in text:
            text = text.replace('  ', ' ')

        # Split into sentences for better context
        sentences = text.split('.')

        pos_count = 0
        neg_count = 0
        total_relevant_phrases = 0

        for sentence in sentences:
            # Skip empty sentences
            if not sentence.strip():
                continue

            words = sentence.strip().split()

            # Check for negation words in the sentence
            has_negation = any(neg in words for neg in {'not', 'no', "n't", 'never', 'without', 'rarely'})

            # Look for sentiment patterns
            found_positive = any(pattern in sentence for pattern in positive_patterns)
            found_negative = any(pattern in sentence for pattern in negative_patterns)

            # Apply negation logic
            if found_positive:
                if has_negation:
                    neg_count += 1
                else:
                    pos_count += 1
                total_relevant_phrases += 1

            if found_negative:
                if has_negation:
                    pos_count += 1
                else:
                    neg_count += 1
                total_relevant_phrases += 1

        # Calculate sentiment score
        if total_relevant_phrases == 0:
            logger.debug("No sentiment patterns found in text")
            return 0.0, 'neutral'

        # Calculate weighted sentiment score
        sentiment_score = (pos_count - neg_count) / max(total_relevant_phrases, 1)

        logger.debug(f"Sentiment analysis results: positive={pos_count}, negative={neg_count}, "
                    f"total_phrases={total_relevant_phrases}, score={sentiment_score:.4f}")

        # Even stricter thresholds with bias towards negative sentiment
        if sentiment_score > 0.25:
            logger.info(f"Positive sentiment detected with score {sentiment_score:.4f}")
            return sentiment_score, 'positive'
        elif sentiment_score < -0.05:  # Very sensitive to negative sentiment
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

        processed_count = 0
        for article in articles:
            try:
                logger.debug(f"Processing article {article.id}: {article.title}")

                # Combine title and content for better context
                full_text = f"{article.title}. {article.content}"

                # Define crypto assets and their tickers with variations
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

                # Analyze sentiment
                score, label = analyze_sentiment(full_text)
                article.sentiment_score = score
                article.sentiment_label = label

                # Format content with bold assets and tickers
                formatted_content = article.content
                for asset, ticker in crypto_assets.items():
                    pattern = re.compile(rf'\b{asset}\b', re.IGNORECASE)
                    formatted_content = pattern.sub(f'**{asset.title()}** (${ticker})', formatted_content)
                
                article.content = formatted_content

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