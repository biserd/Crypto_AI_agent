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
        "Tech Crunch",
        "https://techcrunch.com",
        ".post-block",  # Updated selector
    ),
    NewsSource(
        "The Verge",
        "https://www.theverge.com",
        ".duet--article--standard",  # Updated selector
    ),
]

def scrape_articles():
    """Scrape articles from configured sources"""
    logging.info("Starting article scraping")
    articles_added = 0

    for source in SOURCES:
        try:
            logging.info(f"Scraping from {source.name} at {source.url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(source.url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            logging.info(f"Successfully parsed HTML from {source.name}")

            # Log the HTML structure for debugging
            logging.debug(f"HTML content: {soup.prettify()[:1000]}")  # First 1000 chars

            articles = soup.select(source.article_selector)
            logging.info(f"Found {len(articles)} articles on {source.name}")

            for article in articles[:5]:  # Limit to 5 articles per source
                try:
                    # Extract article URL
                    link = article.find('a')
                    if not link or not link.get('href'):
                        logging.warning(f"No valid link found in article from {source.name}")
                        continue

                    article_url = link.get('href')
                    if not article_url.startswith('http'):
                        if article_url.startswith('//'):
                            article_url = f"https:{article_url}"
                        else:
                            article_url = f"{source.url.rstrip('/')}/{article_url.lstrip('/')}"

                    logging.info(f"Processing article URL: {article_url}")

                    # Check if article already exists
                    exists = Article.query.filter_by(source_url=article_url).first()
                    if exists:
                        logging.debug(f"Article already exists: {article_url}")
                        continue

                    # Get article content
                    downloaded = trafilatura.fetch_url(article_url)
                    if not downloaded:
                        logging.warning(f"Could not download content from {article_url}")
                        continue

                    content = trafilatura.extract(downloaded)
                    if not content:
                        logging.warning(f"No content extracted from {article_url}")
                        continue

                    # Find title
                    title = None
                    for tag in ['h1', 'h2', 'h3']:
                        title_tag = article.find(tag)
                        if title_tag and title_tag.text.strip():
                            title = title_tag.text.strip()
                            break

                    if not title:
                        # Try finding title in article content if not found in preview
                        soup_article = BeautifulSoup(downloaded, 'html.parser')
                        for tag in ['h1', 'h2']:
                            title_tag = soup_article.find(tag)
                            if title_tag and title_tag.text.strip():
                                title = title_tag.text.strip()
                                break

                    if not title:
                        logging.warning(f"No title found for article: {article_url}")
                        continue

                    new_article = Article(
                        title=title,
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
            logging.info(f"Successfully committed {articles_added} articles from {source.name}")

        except Exception as e:
            logging.error(f"Error scraping {source.name}: {str(e)}")
            continue

    logging.info(f"Completed article scraping. Added {articles_added} new articles")
    return articles_added