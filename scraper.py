import logging
import time
from bs4 import BeautifulSoup, Comment
import requests
import trafilatura
from datetime import datetime
from app import db, socketio, broadcast_new_article # Added imports
from models import Article, NewsSourceMetrics # Added NewsSourceMetrics import
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random
import feedparser
import re
from html.parser import HTMLParser
from html.parser import HTMLParser as HTMLParser2

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

class MLStripper(HTMLParser2):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
    def handle_data(self, data):  # Changed parameter name from 'd' to 'data'
        self.fed.append(data)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    """Strip HTML tags from content"""
    try:
        if not html:
            return ""
        s = MLStripper()
        s.feed(html)
        return s.get_data()
    except Exception as e:
        logger.error(f"Error stripping HTML tags: {str(e)}")
        return re.sub(r'<[^>]+>', '', html)  # Fallback to regex cleaning

def clean_html_content(html_content):
    """Clean HTML content and extract readable text with enhanced cleaning"""
    try:
        if not html_content:
            return ""

        logger.debug(f"Starting HTML content cleaning (length: {len(html_content)})")

        # First try trafilatura for better content extraction
        try:
            downloaded = trafilatura.extract(html_content, include_links=False, include_images=False, 
                                          include_tables=False, no_fallback=False)
            if downloaded:
                cleaned_text = downloaded.strip()
                logger.debug("Successfully cleaned content using trafilatura")
                return cleaned_text
        except Exception as e:
            logger.warning(f"Trafilatura extraction failed: {str(e)}, falling back to BeautifulSoup")

        # Fallback to BeautifulSoup if trafilatura fails
        # Remove problematic unicode characters
        html_content = html_content.replace('\xa0', ' ')
        html_content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', html_content)

        # Parse with BeautifulSoup
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            logger.error(f"BeautifulSoup parsing failed: {str(e)}")
            return strip_tags(html_content)

        # Remove all comments first
        try:
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
        except Exception as e:
            logger.warning(f"Error removing HTML comments: {str(e)}")

        # Remove unwanted tags and their contents
        unwanted_tags = [
            "script", "style", "iframe", "form", "nav", "header", "footer",
            "aside", "noscript", "figure", "figcaption", "time", "button",
            "meta", "link", "img", "svg", "path", "source", "picture"
        ]

        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                try:
                    element.decompose()
                except Exception as e:
                    logger.warning(f"Error removing {tag} tag: {str(e)}")

        # Replace breaks and paragraphs with newlines
        for br in soup.find_all("br"):
            br.replace_with("\n")

        for p in soup.find_all("p"):
            p.replace_with(f"\n{p.get_text()}\n")

        # Get text and clean it
        text = soup.get_text(separator=' ')

        # Clean up the text
        text = re.sub(r'<[^>]+>', '', text)  # Remove any remaining HTML tags
        text = re.sub(r'&nbsp;|&amp;|&lt;|&gt;|&quot;|&#39;|&[a-zA-Z]+;', ' ', text)  # Replace HTML entities
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space
        text = re.sub(r'\n\s*\n', '\n', text)  # Replace multiple newlines
        text = text.strip()

        logger.debug(f"Completed HTML cleaning. Final length: {len(text)}")
        return text

    except Exception as e:
        logger.error(f"Error cleaning HTML content: {str(e)}")
        # Last resort: try simple tag stripping
        cleaned = strip_tags(html_content)
        if cleaned:
            return cleaned.strip()
        return ""  # Return empty string if all cleaning methods fail

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
    ),
    NewsSource(
        "Messari",
        "https://messari.io/rss",
        is_rss=True
    ),
    NewsSource(
        "The Block",
        "https://www.theblock.co/rss.xml",
        is_rss=True
    )
]

def init_source_metrics(source_name):
    """Initialize or get source metrics with proper error handling"""
    try:
        # Start a new transaction
        existing_count = Article.query.filter_by(source_name=source_name).count()
        logger.info(f"Found {existing_count} existing articles for {source_name}")

        source_metrics = NewsSourceMetrics.query.filter_by(source_name=source_name).first()
        if not source_metrics:
            # Create new metrics if none exist
            source_metrics = NewsSourceMetrics(
                source_name=source_name,
                trust_score=70.0,  # Default initial trust score
                article_count=existing_count,  # Initialize with existing count
                accuracy_score=80.0,  # Default initial accuracy score
                last_updated=datetime.utcnow()
            )
            db.session.add(source_metrics)
            logger.info(f"Created new source metrics for {source_name} with initial count {existing_count}")
        else:
            # Update existing metrics with correct count
            source_metrics.article_count = existing_count
            source_metrics.last_updated = datetime.utcnow()
            logger.info(f"Updated existing source metrics for {source_name}, count: {existing_count}")

        # Commit changes immediately
        db.session.commit()
        return source_metrics

    except Exception as e:
        logger.error(f"Error initializing source metrics for {source_name}: {str(e)}")
        db.session.rollback()
        return None

def scrape_rss_feed(source):
    """Scrape articles from RSS feed with improved content extraction"""
    try:
        logger.info(f"Fetching RSS feed from {source.name} at {source.url}")
        feed = feedparser.parse(source.url)

        if feed.bozo:
            logger.error(f"Error parsing RSS feed for {source.name}: {feed.bozo_exception}")
            return 0

        if not feed.entries:
            logger.warning(f"No entries found in {source.name} RSS feed")
            return 0

        articles_added = 0
        logger.info(f"Found {len(feed.entries)} entries in {source.name} RSS feed")

        # Initialize source metrics
        source_metrics = init_source_metrics(source.name)
        if not source_metrics:
            logger.error(f"Failed to initialize source metrics for {source.name}")
            return 0

        initial_count = source_metrics.article_count
        logger.info(f"Current article count for {source.name}: {initial_count}")

        try:
            for entry in feed.entries[:10]:  # Process latest 10 entries
                try:
                    article_url = entry.link
                    logger.debug(f"Processing article from {source.name}: {article_url}")

                    # Check if article already exists
                    exists = Article.query.filter_by(source_url=article_url).first()
                    if exists:
                        logger.debug(f"Article already exists: {article_url}")
                        continue

                    try:
                        downloaded = trafilatura.fetch_url(article_url)
                        full_content = trafilatura.extract(downloaded)

                        if full_content:
                            content = full_content
                            logger.debug(f"Successfully extracted full article content from {source.name}")
                        else:
                            content = entry.get('description', '')
                            if not content and 'content' in entry:
                                content = entry.content[0].value if isinstance(entry.content, list) else entry.content
                            logger.debug(f"Using RSS feed content as fallback for {source.name}")
                    except Exception as e:
                        logger.error(f"Error fetching full article content from {source.name}: {str(e)}")
                        content = entry.get('description', '')

                    if not content:
                        logger.warning(f"No content found for {article_url} from {source.name}")
                        continue

                    cleaned_content = clean_html_content(content)
                    summary = clean_html_content(entry.get('summary', ''))
                    if not summary:
                        summary = ' '.join(cleaned_content.split('. ')[:3]) + '.'

                    logger.info(f"Adding new article from {source.name}: {entry.title}")

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
                    source_metrics.article_count += 1
                    source_metrics.last_updated = datetime.utcnow()
                    articles_added += 1

                    try:
                        broadcast_new_article(new_article)
                    except Exception as e:
                        logger.error(f"Error broadcasting new article: {str(e)}")

                except Exception as e:
                    logger.error(f"Error processing article from {source.name}: {str(e)}")
                    continue

            if articles_added > 0:
                db.session.commit()
                logger.info(f"Successfully committed {articles_added} articles and updated metrics for {source.name}")
                logger.info(f"Updated article count for {source.name} from {initial_count} to {source_metrics.article_count}")
            return articles_added

        except Exception as e:
            logger.error(f"Error in RSS feed processing for {source.name}: {str(e)}")
            db.session.rollback()
            return 0

    except Exception as e:
        logger.error(f"Error fetching RSS feed from {source.name}: {str(e)}")
        return 0

def scrape_articles():
    """Scrape articles from cryptocurrency news sources"""
    logger.info("Starting article scraping")
    total_articles_added = 0

    # First, ensure all sources have metrics initialized
    for source in SOURCES:
        init_source_metrics(source.name)

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