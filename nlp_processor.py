import logging
import sys
import spacy
from app import db
from models import Article

def ensure_spacy_model():
    """Ensure SpaCy model is downloaded and available"""
    try:
        nlp = spacy.load("en_core_web_sm")
        logging.info("Successfully loaded SpaCy language model")
        return nlp
    except Exception as e:
        logging.error(f"Error loading SpaCy model: {str(e)}")
        try:
            # Download the model using spacy CLI
            spacy.cli.download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
            logging.info("Successfully downloaded and loaded SpaCy model")
            return nlp
        except Exception as download_error:
            logging.error(f"Failed to download SpaCy model: {str(download_error)}")
            return None

# Initialize SpaCy
nlp = ensure_spacy_model()
if nlp is None:
    logging.error("Could not initialize SpaCy. Sentiment analysis will be disabled.")

def analyze_sentiment(text):
    """
    Analyze sentiment of text using SpaCy
    Returns (score, label)
    """
    if nlp is None:
        return 0.0, 'neutral'

    doc = nlp(text)

    # Calculate sentiment score based on token polarities
    sentiment_score = 0
    word_count = 0

    # Enhanced sentiment word lists
    positive_words = {
        'good', 'great', 'excellent', 'amazing', 'positive', 'success', 'wonderful',
        'best', 'perfect', 'innovative', 'breakthrough', 'achievement', 'improved'
    }
    negative_words = {
        'bad', 'poor', 'negative', 'terrible', 'awful', 'failed', 'worst',
        'problem', 'issue', 'concern', 'dangerous', 'disappointing', 'troubled'
    }

    for token in doc:
        # Check if token is a meaningful word (not punctuation or whitespace)
        if not token.is_punct and not token.is_space:
            # Use SpaCy's built-in token attributes for basic sentiment
            if token.pos_ in ['ADJ', 'VERB', 'ADV']:  # Focus on descriptive words
                word = token.text.lower()
                # Simple rule-based scoring
                if word in positive_words:
                    sentiment_score += 1
                elif word in negative_words:
                    sentiment_score -= 1
                word_count += 1

    # Normalize score
    if word_count > 0:
        final_score = sentiment_score / word_count
    else:
        final_score = 0

    # Convert score to label
    if final_score > 0.1:
        label = 'positive'
    elif final_score < -0.1:
        label = 'negative'
    else:
        label = 'neutral'

    return final_score, label

def process_articles():
    """Process unprocessed articles with NLP pipeline including sentiment analysis"""
    if nlp is None:
        logging.error("SpaCy is not initialized. Cannot process articles.")
        return

    logging.info("Starting NLP processing")

    # Process all articles to ensure sentiment analysis is applied
    articles = Article.query.all()
    logging.info(f"Processing {len(articles)} articles")

    for article in articles:
        try:
            # Simple extractive summarization if needed
            if not article.summary:
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

            # Perform sentiment analysis
            # Analyze both title and content for better accuracy
            title_score, title_label = analyze_sentiment(article.title)
            content_score, content_label = analyze_sentiment(article.content)

            # Combine scores (give more weight to content)
            combined_score = (title_score * 0.3) + (content_score * 0.7)

            article.sentiment_score = combined_score
            # Use content sentiment for final label as it's more comprehensive
            article.sentiment_label = content_label

            db.session.commit()
            logging.info(f"Successfully processed article: {article.id} (Sentiment: {content_label})")

        except Exception as e:
            logging.error(f"Error processing article {article.id}: {str(e)}")
            continue

    logging.info("Completed NLP processing")

# Automatically process articles when the module is imported
process_articles()