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
        "article.story-card",
    ),
    NewsSource(
        "Associated Press",
        "https://apnews.com/hub/world-news",
        "div.CardHeadline",
    ),
]

def scrape_articles():
    logging.info("Starting article scraping")
    articles_added = 0

    for source in SOURCES:
        try:
            logging.info(f"Scraping from {source.name} at {source.url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(source.url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an error for bad status codes

            soup = BeautifulSoup(response.text, 'html.parser')
            logging.debug(f"Successfully parsed HTML from {source.name}")

            articles = soup.select(source.article_selector)
            logging.info(f"Found {len(articles)} articles on {source.name}")

            for article in articles[:5]:  # Limit to 5 articles per source
                try:
                    # Extract article URL
                    link = article.find('a')
                    if not link:
                        logging.warning(f"No link found in article from {source.name}")
                        continue

                    article_url = link.get('href')
                    if not article_url.startswith('http'):
                        article_url = f"https://{source.url.split('/')[2]}{article_url}"

                    logging.debug(f"Processing article URL: {article_url}")

                    # Check if article already exists
                    exists = Article.query.filter_by(source_url=article_url).first()
                    if exists:
                        logging.debug(f"Article already exists: {article_url}")
                        continue

                    # Get article content
                    downloaded = trafilatura.fetch_url(article_url)
                    content = trafilatura.extract(downloaded)

                    if not content:
                        logging.warning(f"No content extracted from {article_url}")
                        continue

                    # Create new article
                    title = article.find(['h3', 'h2', 'h1'])
                    if not title:
                        logging.warning(f"No title found for article: {article_url}")
                        continue

                    new_article = Article(
                        title=title.text.strip(),
                        content=content,
                        source_url=article_url,
                        source_name=source.name,
                        created_at=datetime.utcnow()
                    )

                    db.session.add(new_article)
                    articles_added += 1
                    logging.info(f"Added new article: {new_article.title}")

                except Exception as e:
                    logging.error(f"Error processing article from {source.name}: {str(e)}")
                    continue

            db.session.commit()

        except Exception as e:
            logging.error(f"Error scraping {source.name}: {str(e)}")
            continue

    logging.info(f"Completed article scraping. Added {articles_added} new articles")
    return articles_added