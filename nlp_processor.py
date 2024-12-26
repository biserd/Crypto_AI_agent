import logging
import spacy
import os
from app import db
from models import Article

def download_spacy_model():
    """Download SpaCy model if not already installed"""
    try:
        import en_core_web_sm
        return en_core_web_sm.load()
    except ImportError:
        try:
            os.system('python -m spacy download en_core_web_sm')
            import en_core_web_sm
            return en_core_web_sm.load()
        except Exception as e:
            logging.error(f"Failed to download SpaCy model: {str(e)}")
            return None

# Initialize SpaCy
nlp = download_spacy_model()
if nlp is None:
    logging.error("Could not initialize SpaCy. Sentiment analysis will be disabled.")

def analyze_sentiment(text):
    """
    Analyze sentiment of text using SpaCy and custom word lists
    Returns (score, label)
    """
    if nlp is None:
        return 0.0, 'neutral'

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
        if token.text in positive_words:
            sentiment_score += 1
            word_count += 1
        elif token.text in negative_words:
            sentiment_score -= 1
            word_count += 1
        elif token.pos_ in ['ADJ', 'VERB', 'ADV']:
            # Also consider general sentiment words
            if token.text in ['good', 'great', 'excellent', 'amazing']:
                sentiment_score += 0.5
                word_count += 1
            elif token.text in ['bad', 'poor', 'terrible', 'awful']:
                sentiment_score -= 0.5
                word_count += 1

    # Normalize score
    final_score = sentiment_score / max(word_count, 1)

    # Convert score to label with crypto-specific thresholds
    if final_score > 0.2:
        label = 'positive'
    elif final_score < -0.2:
        label = 'negative'
    else:
        label = 'neutral'

    return final_score, label

def process_articles():
    """Process all articles with NLP pipeline including sentiment analysis"""
    if nlp is None:
        logging.error("SpaCy is not initialized. Cannot process articles.")
        return

    logging.info("Starting NLP processing")

    try:
        # Process all articles to ensure sentiment analysis is applied
        articles = Article.query.all()
        logging.info(f"Processing {len(articles)} articles")

        for article in articles:
            try:
                # Generate summary if needed
                if not article.summary:
                    doc = nlp(article.content)
                    # Take first 3 sentences for summary
                    summary_sentences = [sent.text for sent in doc.sents][:3]
                    article.summary = ' '.join(summary_sentences)

                # Categorize based on crypto-specific keywords
                content_lower = article.content.lower()
                if any(word in content_lower for word in ['bitcoin', 'crypto', 'blockchain', 'defi', 'nft']):
                    article.category = 'Crypto Markets'
                elif any(word in content_lower for word in ['technology', 'protocol', 'network', 'mining']):
                    article.category = 'Technology'
                else:
                    article.category = 'General'

                # Perform sentiment analysis on both title and content
                title_score, title_label = analyze_sentiment(article.title)
                content_score, content_label = analyze_sentiment(article.content)

                # Combine scores (weight title more for crypto news)
                combined_score = (title_score * 0.4) + (content_score * 0.6)

                article.sentiment_score = combined_score
                article.sentiment_label = content_label

                logging.info(f"Processed article {article.id}: Category={article.category}, Sentiment={content_label}")

            except Exception as e:
                logging.error(f"Error processing article {article.id}: {str(e)}")
                continue

        db.session.commit()
        logging.info("Successfully processed all articles")

    except Exception as e:
        logging.error(f"Error in process_articles: {str(e)}")

# Process articles when the module is imported
process_articles()