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
import random

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class NewsSource:
    def __init__(self, name, url, article_selector, title_selector):
        self.name = name
        self.url = url
        self.article_selector = article_selector
        self.title_selector = title_selector

# Updated selectors and added more robust configuration
SOURCES = [
    NewsSource(
        "CoinDesk",
        "https://www.coindesk.com/markets/",
        "div.article-cardstyles__StyledWrapper-sc-q1x8lc-0",  # Updated selector
        "h6.typography__StyledTypography-sc-owin6q-0"
    ),
    NewsSource(
        "Cointelegraph",
        "https://cointelegraph.com/news",  # Changed to news section
        "article.post-card",
        "span.post-card-inline__title"
    ),
]

# List of user agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
]

def create_session():
    """Create a requests session with advanced retry strategy"""
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

def get_random_headers():
    """Generate random headers to avoid detection"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }

def scrape_articles():
    """Scrape articles from cryptocurrency news sources with enhanced error handling"""
    logger.info("Starting article scraping")
    articles_added = 0
    session = create_session()

    for source in SOURCES:
        try:
            logger.info(f"Scraping from {source.name} at {source.url}")

            # Get page with random headers
            headers = get_random_headers()
            response = session.get(source.url, headers=headers, timeout=15)
            response.raise_for_status()

            logger.info(f"Successfully fetched {source.url}")

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.select(source.article_selector)

            if not articles:
                logger.warning(f"No articles found for {source.name}. Trying alternative selectors...")
                # Try alternative selectors
                alternative_selectors = [
                    "div.article-card",
                    "article.article-card",
                    "div.post-card",
                    ".article-wrapper"
                ]
                for selector in alternative_selectors:
                    articles = soup.select(selector)
                    if articles:
                        logger.info(f"Found articles using alternative selector: {selector}")
                        break

            logger.info(f"Found {len(articles)} articles on {source.name}")

            if len(articles) == 0:
                logger.warning(f"No articles found for {source.name}. HTML structure might have changed.")
                logger.debug(f"Current selector: {source.article_selector}")
                continue

            for article in articles[:5]:  # Limit to 5 most recent articles
                try:
                    # Extract article URL and title
                    link = article.find('a', href=True)
                    if not link:
                        logger.warning(f"No link found in article from {source.name}")
                        continue

                    article_url = link.get('href', '')
                    if not article_url:
                        logger.warning("Empty URL found")
                        continue

                    if not article_url.startswith('http'):
                        article_url = f"https://{source.url.split('/')[2]}{article_url}"

                    logger.debug(f"Processing article URL: {article_url}")

                    # Check if article already exists
                    exists = Article.query.filter_by(source_url=article_url).first()
                    if exists:
                        logger.debug(f"Article already exists: {article_url}")
                        continue

                    # Get article content with random delay
                    time.sleep(random.uniform(1, 3))  # Random delay between requests
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
                    title_elem = article.select_one(source.title_selector)
                    if title_elem:
                        title = title_elem.text.strip()

                    if not title and link.get('title'):
                        title = link.get('title').strip()

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
                        category='Crypto Markets'  # Default category for crypto news
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