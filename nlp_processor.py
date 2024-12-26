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
        if not text or not isinstance(text, str):
            logger.warning("Invalid text input for sentiment analysis")
            return 0.0, 'neutral'

        logger.debug(f"Starting sentiment analysis for text (length: {len(text)})")

        # Enhanced crypto-specific sentiment words and phrases with weights
        positive_patterns = {
            # Price movements (weight: 1.0)
            'surge': 1.2, 'rally': 1.2, 'jump': 1.0, 'gain': 1.0, 'soar': 1.2, 'rise': 1.0, 'climb': 1.0, 
            'peak': 1.0, 'record high': 1.5, 'breakout': 1.2, 'outperform': 1.2,
            # Market sentiment (weight: 1.2)
            'bullish': 1.5, 'optimistic': 1.2, 'confident': 1.2, 'strong': 1.0, 'positive': 1.0, 
            'opportunity': 1.0, 'support': 1.0,
            # Adoption/Development (weight: 1.5)
            'adoption': 1.5, 'partnership': 1.5, 'launch': 1.2, 'upgrade': 1.2, 'integration': 1.2, 
            'milestone': 1.2, 'development': 1.2, 'progress': 1.2, 'innovation': 1.5, 'breakthrough': 1.5,
            'success': 1.2, 'approval': 1.3,
        }

        negative_patterns = {
            # Price movements (weight: 1.5)
            'crash': 2.0, 'plunge': 1.8, 'drop': 1.2, 'fall': 1.2, 'decline': 1.2, 'tumble': 1.5, 
            'slump': 1.5, 'correction': 1.2, 'collapse': 2.0, 'tank': 1.8,
            # Market sentiment (weight: 1.2)
            'bearish': 1.5, 'pessimistic': 1.2, 'fear': 1.5, 'concern': 1.2, 'worry': 1.2, 
            'uncertain': 1.0, 'volatile': 1.2, 'panic': 1.8,
            # Security/Risk (weight: 2.0)
            'hack': 2.0, 'breach': 2.0, 'scam': 2.0, 'fraud': 2.0, 'vulnerability': 1.5, 
            'exploit': 1.5, 'risk': 1.2, 'attack': 1.8,
            # Regulatory (weight: 1.5)
            'ban': 1.8, 'restrict': 1.5, 'crack down': 1.8, 'investigate': 1.2, 'sue': 1.5, 
            'lawsuit': 1.5, 'illegal': 1.5, 'regulation': 1.2,
            # Market problems (weight: 1.8)
            'sell-off': 1.8, 'dump': 1.8, 'liquidation': 1.8, 'margin call': 1.8, 'default': 1.8,
            'loss': 1.5, 'bearish': 1.5
        }

        # Clean and normalize text
        text = text.lower()
        text = re.sub(r'[^\w\s-]', ' ', text)  # Remove special characters except hyphens
        sentences = [s.strip() for s in text.split('.') if s.strip()]

        weighted_pos_score = 0
        weighted_neg_score = 0
        total_matches = 0

        for sentence in sentences:
            if not sentence.strip():
                continue

            has_negation = any(neg in sentence for neg in {'not', 'no', "n't", 'never', 'without', 'rarely'})
            logger.debug(f"Analyzing sentence: '{sentence.strip()}', has_negation: {has_negation}")

            # Calculate weighted sentiment scores
            for pattern, weight in positive_patterns.items():
                if pattern in sentence:
                    if has_negation:
                        weighted_neg_score += weight
                        logger.debug(f"Found negated positive pattern '{pattern}' (weight: {weight})")
                    else:
                        weighted_pos_score += weight
                        logger.debug(f"Found positive pattern '{pattern}' (weight: {weight})")
                    total_matches += 1

            for pattern, weight in negative_patterns.items():
                if pattern in sentence:
                    if has_negation:
                        weighted_pos_score += weight * 0.5  # Negated negative is less positive
                        logger.debug(f"Found negated negative pattern '{pattern}' (weight: {weight})")
                    else:
                        weighted_neg_score += weight
                        logger.debug(f"Found negative pattern '{pattern}' (weight: {weight})")
                    total_matches += 1

        if total_matches == 0:
            logger.debug("No sentiment patterns found in text")
            return 0.0, 'neutral'

        # Calculate weighted sentiment score
        sentiment_score = (weighted_pos_score - weighted_neg_score) / max(total_matches, 1)

        logger.debug(f"Final sentiment analysis results:"
                    f"\n- Positive score: {weighted_pos_score}"
                    f"\n- Negative score: {weighted_neg_score}"
                    f"\n- Total matches: {total_matches}"
                    f"\n- Final score: {sentiment_score:.4f}")

        # Adjusted thresholds with higher sensitivity to negative sentiment
        if sentiment_score > 0.2:  # Lowered threshold for positive sentiment
            logger.info(f"Positive sentiment detected with score {sentiment_score:.4f}")
            return sentiment_score, 'positive'
        elif sentiment_score < -0.1:  # More sensitive to negative sentiment
            logger.info(f"Negative sentiment detected with score {sentiment_score:.4f}")
            return sentiment_score, 'negative'
        else:
            logger.info(f"Neutral sentiment detected with score {sentiment_score:.4f}")
            return sentiment_score, 'neutral'

    except Exception as e:
        logger.error(f"Error in sentiment analysis: {str(e)}", exc_info=True)
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
        error_count = 0

        for article in articles:
            try:
                logger.debug(f"Processing article {article.id}: {article.title}")

                # Validate content
                if not article.content or not isinstance(article.content, str):
                    logger.warning(f"Invalid content for article {article.id}")
                    continue

                # Combine title and content for better context
                full_text = f"{article.title}. {article.content}"

                # Format content with bold assets and tickers
                formatted_content = article.content
                formatted_title = article.title

                for asset, ticker in crypto_assets.items():
                    # Create pattern that matches word boundaries
                    pattern = re.compile(rf'\b{asset}\b', re.IGNORECASE)
                    # Only show the asset name in bold with the ticker symbol
                    replacement = f'**{asset.title()}** (${ticker})'

                    formatted_content = pattern.sub(replacement, formatted_content)
                    formatted_title = pattern.sub(replacement, formatted_title)

                # Update article content
                article.content = formatted_content
                article.title = formatted_title

                # Analyze sentiment
                score, label = analyze_sentiment(full_text)
                article.sentiment_score = score
                article.sentiment_label = label

                processed_count += 1
                logger.info(f"Successfully processed article {article.id}: Sentiment={label} (score={score:.4f})")

            except Exception as e:
                error_count += 1
                logger.error(f"Error processing article {article.id}: {str(e)}", exc_info=True)
                continue

        # Commit all changes
        if processed_count > 0:
            db.session.commit()
            logger.info(f"Successfully processed and committed {processed_count} articles")
            if error_count > 0:
                logger.warning(f"Encountered {error_count} errors during processing")
        else:
            logger.info("No articles were processed successfully")

    except Exception as e:
        logger.error(f"Error in process_articles: {str(e)}")
        db.session.rollback()
        raise

if __name__ == "__main__":
    process_articles()