import logging
import spacy
from app import db
from models import Article

# Load SpaCy language model
try:
    nlp = spacy.load("en_core_web_sm")
    logging.info("Successfully loaded SpaCy language model")
except Exception as e:
    logging.error(f"Error loading SpaCy model: {str(e)}")
    # Download the model if not available
    logging.info("Downloading SpaCy language model...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def analyze_sentiment(text):
    """
    Analyze sentiment of text using SpaCy
    Returns (score, label)
    """
    doc = nlp(text)

    # Calculate sentiment score based on token polarities
    sentiment_score = 0
    word_count = 0

    for token in doc:
        # Check if token is a meaningful word (not punctuation or whitespace)
        if not token.is_punct and not token.is_space:
            # Use SpaCy's built-in token attributes for basic sentiment
            if token.pos_ in ['ADJ', 'VERB', 'ADV']:  # Focus on descriptive words
                # Simple rule-based scoring
                if token.text.lower() in ['good', 'great', 'excellent', 'amazing', 'positive']:
                    sentiment_score += 1
                elif token.text.lower() in ['bad', 'poor', 'negative', 'terrible', 'awful']:
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
    logging.info("Starting NLP processing")

    # Get unprocessed articles (those without summaries or sentiment analysis)
    articles = Article.query.filter(
        (Article.summary.is_(None)) |
        (Article.sentiment_score.is_(None))
    ).all()

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