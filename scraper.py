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
import feedparser
import re

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class NewsSource:
    """News source configuration class"""
    def __init__(self, name, url, article_selector=None, title_selector=None, is_rss=False):
        self.name = name
        self.url = url
        self.article_selector = article_selector
        self.title_selector = title_selector
        self.is_rss = is_rss

def clean_html_content(html_content):
    """Clean HTML content and extract readable text"""
    try:
        if not html_content:
            return ""

        logger.debug(f"Starting HTML content cleaning (length: {len(html_content)})")

        # Remove problematic unicode characters
        html_content = html_content.replace('\xa0', ' ')

        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove unwanted tags and their contents
        for element in soup(["script", "style", "iframe", "form", "nav", "header", "footer"]):
            element.decompose()

        # Replace <br> with newlines for better text flow
        for br in soup.find_all("br"):
            br.replace_with("\n")

        # Replace paragraph tags with double newlines for better readability
        for p in soup.find_all("p"):
            p.replace_with(f"\n{p.get_text()}\n")

        # Get text and clean it
        text = soup.get_text(separator=' ')

        # Clean up the text
        text = re.sub(r'<[^>]+>', '', text)  # Remove any remaining HTML tags
        text = re.sub(r'&nbsp;', ' ', text)  # Replace HTML entities
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'&#39;', "'", text)
        text = re.sub(r'&[a-zA-Z]+;', '', text)  # Remove other HTML entities
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space
        text = re.sub(r'\n\s*\n', '\n', text)  # Replace multiple newlines
        text = text.strip()

        logger.debug(f"Completed HTML cleaning. Final length: {len(text)}")
        return text

    except Exception as e:
        logger.error(f"Error cleaning HTML content: {str(e)}")
        return html_content  # Return original content if cleaning fails

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

# Define news sources
SOURCES = [
    NewsSource(
        "CoinDesk",
        "https://www.coindesk.com/arc/outboundfeeds/rss?_gl=1*15padrx*_up*MQ..*_ga*NTkwODIwNDc2LjE3MzUyMjUwMzc.*_ga_VM3STRYVN8*MTczNTIyNTAzNS4xLjAuMTczNTIyNTAzNS4wLjAuNzI5ODQ3NDEw",
        is_rss=True
    ),
    NewsSource(
        "Cointelegraph",
        "https://cointelegraph.com/rss",
        is_rss=True
    )
]

def scrape_rss_feed(source):
    """Scrape articles from RSS feed"""
    try:
        logger.info(f"Fetching RSS feed from {source.name} at {source.url}")
        feed = feedparser.parse(source.url)

        if feed.bozo:
            logger.error(f"Error parsing RSS feed for {source.name}: {feed.bozo_exception}")
            return 0

        articles_added = 0
        logger.info(f"Found {len(feed.entries)} entries in {source.name} RSS feed")

        for entry in feed.entries[:10]:  # Process latest 10 entries
            try:
                article_url = entry.link

                # Check if article already exists
                exists = Article.query.filter_by(source_url=article_url).first()
                if exists:
                    logger.debug(f"Article already exists: {article_url}")
                    continue

                # Extract content from RSS feed entry
                content = entry.get('description', '')
                if not content and 'content' in entry:
                    content = entry.content[0].value if isinstance(entry.content, list) else entry.content

                if not content:
                    logger.warning(f"No content found in RSS entry for {article_url}")
                    continue

                # Clean HTML content with detailed logging
                logger.debug(f"Raw content length before cleaning: {len(content)}")
                cleaned_content = clean_html_content(content)
                logger.debug(f"Cleaned content length: {len(cleaned_content)}")

                # Use summary from RSS feed or create from cleaned content
                summary = clean_html_content(entry.get('summary', ''))
                if not summary:
                    # Create a summary from the first few sentences of the cleaned content
                    summary = ' '.join(cleaned_content.split('. ')[:3]) + '.'

                logger.info(f"Adding new article: {entry.title}")

                new_article = Article(
                    title=entry.title,
                    content=cleaned_content,
                    summary=summary,
                    source_url=article_url,
                    source_name=source.name,
                    created_at=datetime.utcnow(),
                    category='Crypto Markets'
                )

                db.session.add(new_article)
                articles_added += 1
                logger.info(f"Successfully added article: {entry.title}")

            except Exception as e:
                logger.error(f"Error processing RSS entry from {source.name}: {str(e)}")
                continue

        if articles_added > 0:
            try:
                db.session.commit()
                logger.info(f"Successfully committed {articles_added} articles from {source.name}")
            except Exception as e:
                logger.error(f"Error committing articles from {source.name}: {str(e)}")
                db.session.rollback()
                return 0

        return articles_added

    except Exception as e:
        logger.error(f"Error fetching RSS feed from {source.name}: {str(e)}")
        return 0

def scrape_articles():
    """Scrape articles from cryptocurrency news sources"""
    logger.info("Starting article scraping")
    total_articles_added = 0

    for source in SOURCES:
        try:
            if source.is_rss:
                articles_added = scrape_rss_feed(source)
            else:
                logger.info(f"Skipping non-RSS source {source.name}")
                continue

            total_articles_added += articles_added

        except Exception as e:
            logger.error(f"Error processing source {source.name}: {str(e)}")
            continue

    logger.info(f"Completed article scraping. Added {total_articles_added} new articles")
    return total_articles_added

if __name__ == "__main__":
    scrape_articles()