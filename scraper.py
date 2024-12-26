import logging
from bs4 import BeautifulSoup
import requests
import trafilatura
from datetime import datetime
from app import db
from models import Article

class NewsSource:
    def __init__(self, name, url, article_selector):
        self.name = name
        self.url = url
        self.article_selector = article_selector

SOURCES = [
    NewsSource(
        "Reuters",
        "https://www.reuters.com/world",
        "article.story",
    ),
    NewsSource(
        "Associated Press",
        "https://apnews.com/hub/world-news",
        "div.FeedCard",
    ),
]

def scrape_articles():
    logging.info("Starting article scraping")
    
    for source in SOURCES:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(source.url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            articles = soup.select(source.article_selector)
            for article in articles[:5]:  # Limit to 5 articles per source
                try:
                    # Extract article URL
                    link = article.find('a')
                    if not link:
                        continue
                        
                    article_url = link.get('href')
                    if not article_url.startswith('http'):
                        article_url = f"https://{source.url.split('/')[2]}{article_url}"
                    
                    # Check if article already exists
                    exists = Article.query.filter_by(source_url=article_url).first()
                    if exists:
                        continue
                    
                    # Get article content
                    downloaded = trafilatura.fetch_url(article_url)
                    content = trafilatura.extract(downloaded)
                    
                    if not content:
                        continue
                    
                    # Create new article
                    new_article = Article(
                        title=article.find('h3').text.strip() if article.find('h3') else "Untitled",
                        content=content,
                        source_url=article_url,
                        source_name=source.name,
                        created_at=datetime.utcnow()
                    )
                    
                    db.session.add(new_article)
                    
                except Exception as e:
                    logging.error(f"Error processing article: {str(e)}")
                    continue
            
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Error scraping {source.name}: {str(e)}")
            continue
            
    logging.info("Completed article scraping")
