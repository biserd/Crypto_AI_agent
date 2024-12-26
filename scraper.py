import logging
import time
from bs4 import BeautifulSoup
import requests
import trafilatura
from datetime import datetime
from app import db
from models import Article
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class NewsSource:
    def __init__(self, name, url, article_selector):
        self.name = name
        self.url = url
        self.article_selector = article_selector

SOURCES = [
    NewsSource(
        "CoinDesk",
        "https://www.coindesk.com/markets",  # Updated to markets section for more relevant news
        ".article-cardstyles__StyledWrapper-q1x8lc-0",
    ),
    NewsSource(
        "The Block",
        "https://www.theblock.co/latest",  # Updated to latest news section
        ".post-card",
    ),
]

def create_session():
    """Create a requests session with retry strategy"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def scrape_articles():
    """Scrape articles from cryptocurrency news sources"""
    logger.info("Starting article scraping")
    articles_added = 0
    session = create_session()

    for source in SOURCES:
        try:
            logger.info(f"Scraping from {source.name} at {source.url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            response = session.get(source.url, headers=headers, timeout=15)
            response.raise_for_status()
            logger.info(f"Successfully fetched {source.url}")

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.select(source.article_selector)
            logger.info(f"Found {len(articles)} articles on {source.name}")

            if len(articles) == 0:
                logger.debug(f"HTML content sample: {soup.prettify()[:500]}")
                logger.debug("Available classes in HTML:")
                for tag in soup.find_all(class_=True):
                    logger.debug(f"Found element with classes: {tag.get('class')}")

            for article in articles[:5]:  # Limit to 5 most recent articles
                try:
                    # Extract article URL
                    if source.name == "CoinDesk":
                        link = article.find('a', href=True)
                    else:  # The Block
                        link = article.find('a', class_='post-card__title-link')

                    if not link or not link.get('href'):
                        logger.warning(f"No valid link found in article from {source.name}")
                        continue

                    article_url = link.get('href')
                    if not article_url.startswith('http'):
                        article_url = f"{source.url.split('/')[0]}//{source.url.split('/')[2]}{article_url}"

                    # Check if article already exists
                    exists = Article.query.filter_by(source_url=article_url).first()
                    if exists:
                        logger.debug(f"Article already exists: {article_url}")
                        continue

                    # Get article content
                    downloaded = trafilatura.fetch_url(article_url)
                    if not downloaded:
                        logger.warning(f"Could not download content from {article_url}")
                        continue

                    content = trafilatura.extract(downloaded)
                    if not content:
                        logger.warning(f"No content extracted from {article_url}")
                        continue

                    # Find title
                    title = None
                    if source.name == "CoinDesk":
                        title_elem = article.find('h6') or article.find('h5') or article.find('h4')
                    else:  # The Block
                        title_elem = article.find('h2', class_='post-card__title')

                    if title_elem:
                        title = title_elem.text.strip()

                    if not title:
                        logger.warning(f"No title found for article: {article_url}")
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
                    logger.info(f"Added new article: {title}")

                except Exception as e:
                    logger.error(f"Error processing article from {source.name}: {str(e)}")
                    continue

            db.session.commit()
            logger.info(f"Successfully committed {articles_added} articles from {source.name}")

        except Exception as e:
            logger.error(f"Error scraping {source.name}: {str(e)}")
            continue

    logger.info(f"Completed article scraping. Added {articles_added} new articles")
    return articles_added

if __name__ == "__main__":
    scrape_articles()