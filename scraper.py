import logging
import time
from bs4 import BeautifulSoup, Comment
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
from html.parser import HTMLParser
from html.parser import HTMLParser as HTMLParser2 # Added to resolve Comment ambiguity


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
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    """Strip HTML tags from content"""
    try:
        s = MLStripper()
        s.feed(html)
        return s.get_data()
    except Exception as e:
        logger.error(f"Error stripping HTML tags: {str(e)}")
        return html

def clean_html_content(html_content):
    """Clean HTML content and extract readable text with enhanced cleaning"""
    try:
        if not html_content:
            return ""

        logger.debug(f"Starting HTML content cleaning (length: {len(html_content)})")

        # First try trafilatura for better content extraction
        try:
            cleaned_text = trafilatura.extract(html_content)
            if cleaned_text:
                logger.debug("Successfully cleaned content using trafilatura")
                return cleaned_text.strip()
        except Exception as e:
            logger.warning(f"Trafilatura extraction failed: {str(e)}, falling back to BeautifulSoup")

        # Fallback to BeautifulSoup if trafilatura fails
        # Remove problematic unicode characters
        html_content = html_content.replace('\xa0', ' ')

        # Parse with BeautifulSoup
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            logger.error(f"BeautifulSoup parsing failed: {str(e)}")
            return strip_tags(html_content)

        # Remove unwanted tags and their contents
        unwanted_tags = [
            "script", "style", "iframe", "form", "nav", "header", "footer",
            "aside", "noscript", "figure", "figcaption", "time", "button"
        ]
        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                try:
                    element.decompose()
                except Exception as e:
                    logger.warning(f"Error removing {tag} tag: {str(e)}")

        # Remove all HTML comments
        try:
            for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
                comment.extract()
        except Exception as e:
            logger.warning(f"Error removing HTML comments: {str(e)}")

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
        text = re.sub(r'&nbsp;|&amp;|&lt;|&gt;|&quot;|&#39;|&[a-zA-Z]+;', ' ', text)  # Replace HTML entities
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space
        text = re.sub(r'\n\s*\n', '\n', text)  # Replace multiple newlines
        text = text.strip()

        logger.debug(f"Completed HTML cleaning. Final length: {len(text)}")
        return text

    except Exception as e:
        logger.error(f"Error cleaning HTML content: {str(e)}")
        return strip_tags(html_content)  # Return stripped content as fallback

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
    """Scrape articles from RSS feed with improved content extraction"""
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

                # Try to get the full article content using trafilatura
                try:
                    downloaded = trafilatura.fetch_url(article_url)
                    full_content = trafilatura.extract(downloaded)

                    if full_content:
                        content = full_content
                        logger.debug("Successfully extracted full article content")
                    else:
                        # Fallback to RSS content if full article extraction fails
                        content = entry.get('description', '')
                        if not content and 'content' in entry:
                            content = entry.content[0].value if isinstance(entry.content, list) else entry.content
                        logger.debug("Using RSS feed content as fallback")
                except Exception as e:
                    logger.error(f"Error fetching full article content: {str(e)}")
                    content = entry.get('description', '')

                if not content:
                    logger.warning(f"No content found for {article_url}")
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