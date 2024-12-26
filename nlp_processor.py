import spacy
import logging
from app import db
from models import Article

nlp = spacy.load("en_core_web_sm")

def process_articles():
    """Process unprocessed articles with NLP pipeline"""
    logging.info("Starting NLP processing")
    
    # Get unprocessed articles (those without summaries)
    articles = Article.query.filter_by(summary=None).all()
    
    for article in articles:
        try:
            # Generate summary using spaCy
            doc = nlp(article.content)
            
            # Extract main sentences (simple extractive summarization)
            sentences = [sent for sent in doc.sents]
            important_sentences = sentences[:3]  # Take first 3 sentences as summary
            
            article.summary = ' '.join([str(sent) for sent in important_sentences])
            
            # Basic categorization based on named entities
            entities = [ent.label_ for ent in doc.ents]
            if 'GPE' in entities:
                article.category = 'World News'
            elif 'ORG' in entities:
                article.category = 'Business'
            else:
                article.category = 'General'
            
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Error processing article {article.id}: {str(e)}")
            continue
    
    logging.info("Completed NLP processing")
