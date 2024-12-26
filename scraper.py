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
    def __init__(self, name, url, article_selector, title_selector):
        self.name = name
        self.url = url
        self.article_selector = article_selector
        self.title_selector = title_selector

SOURCES = [
    NewsSource(
        "CoinDesk",
        "https://www.coindesk.com/markets/",
        "article.article-cardstyles__StyledWrapper-sc-q1x8lc-0",
        "h6.typography__StyledTypography-sc-owin6q-0"
    ),
    NewsSource(
        "Cointelegraph",
        "https://cointelegraph.com/",
        "article.post-card",
        "span.post-card-inline__title"
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
                logger.warning(f"No articles found for {source.name}. HTML structure might have changed.")
                logger.debug(f"Current selector: {source.article_selector}")
                continue

            for article in articles[:5]:  # Limit to 5 most recent articles
                try:
                    # Extract article URL and title based on source
                    if source.name == "CoinDesk":
                        link = article.find('a', href=True)
                        title_elem = article.select_one(source.title_selector)
                    else:  # Cointelegraph
                        link = article.find('a', class_='post-card__title-link')
                        title_elem = article.select_one(source.title_selector)

                    if not link or not link.get('href'):
                        logger.warning(f"No valid link found in article from {source.name}")
                        continue

                    article_url = link.get('href')
                    if not article_url.startswith('http'):
                        article_url = f"https://{source.url.split('/')[2]}{article_url}"

                    logger.debug(f"Processing article URL: {article_url}")

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

                    # Get title
                    title = None
                    if title_elem:
                        title = title_elem.text.strip()

                    if not title:
                        logger.warning(f"No title found for article: {article_url}")
                        continue

                    logger.info(f"Adding new article: {title}")

                    new_article = Article(
                        title=title,
                        content=content,
                        source_url=article_url,
                        source_name=source.name,
                        created_at=datetime.utcnow(),
                        category='Crypto Markets'  # Set default category for crypto news
                    )

                    db.session.add(new_article)
                    articles_added += 1
                    logger.info(f"Added new article: {title}")

                except Exception as e:
                    logger.error(f"Error processing individual article from {source.name}: {str(e)}")
                    continue

            db.session.commit()
            logger.info(f"Successfully committed {articles_added} articles from {source.name}")

        except Exception as e:
            logger.error(f"Error scraping {source.name}: {str(e)}")
            db.session.rollback()
            continue

    logger.info(f"Completed article scraping. Added {articles_added} new articles")
    return articles_added

if __name__ == "__main__":
    scrape_articles()