import logging
import time
from bs4 import BeautifulSoup, Comment
import requests
import trafilatura
from datetime import datetime
from app import db, socketio, broadcast_new_article
from models import Article, NewsSourceMetrics
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
    def handle_data(self, data):
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
        return re.sub(r'<[^>]+>', '', html)

def clean_html_content(html_content):
    """Clean HTML content and extract readable text with enhanced cleaning"""
    try:
        if not html_content:
            return ""

        logger.debug(f"Starting HTML content cleaning (length: {len(html_content)})")

        try:
            downloaded = trafilatura.extract(html_content, include_links=False, include_images=False, 
                                          include_tables=False, no_fallback=False)
            if downloaded:
                cleaned_text = downloaded.strip()
                logger.debug("Successfully cleaned content using trafilatura")
                return cleaned_text
        except Exception as e:
            logger.warning(f"Trafilatura extraction failed: {str(e)}, falling back to BeautifulSoup")

        html_content = html_content.replace('\xa0', ' ')
        html_content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', html_content)

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            logger.error(f"BeautifulSoup parsing failed: {str(e)}")
            return strip_tags(html_content)

        try:
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
        except Exception as e:
            logger.warning(f"Error removing HTML comments: {str(e)}")

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

        for br in soup.find_all("br"):
            br.replace_with("\n")

        for p in soup.find_all("p"):
            p.replace_with(f"\n{p.get_text()}\n")

        text = soup.get_text(separator=' ')

        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&nbsp;|&amp;|&lt;|&gt;|&quot;|&#39;|&[a-zA-Z]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        text = text.strip()

        logger.debug(f"Completed HTML cleaning. Final length: {len(text)}")
        return text

    except Exception as e:
        logger.error(f"Error cleaning HTML content: {str(e)}")
        cleaned = strip_tags(html_content)
        if cleaned:
            return cleaned.strip()
        return ""

def create_session():
    """Create a requests session with advanced retry strategy"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/rss+xml,application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,*/*;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9'
    })
    return session

SOURCES = [
    NewsSource(
        "CoinDesk",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
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
        existing_count = Article.query.filter_by(source_name=source_name).count()
        logger.info(f"Found {existing_count} existing articles for {source_name}")

        source_metrics = NewsSourceMetrics.query.filter_by(source_name=source_name).first()
        if not source_metrics:
            source_metrics = NewsSourceMetrics(
                source_name=source_name,
                trust_score=70.0,
                article_count=existing_count,
                accuracy_score=80.0,
                last_updated=datetime.utcnow()
            )
            db.session.add(source_metrics)
            logger.info(f"Created new source metrics for {source_name} with initial count {existing_count}")
        else:
            source_metrics.article_count = existing_count
            source_metrics.last_updated = datetime.utcnow()
            logger.info(f"Updated existing source metrics for {source_name}, count: {existing_count}")

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
        try:
            session = create_session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = session.get(source.url, timeout=10, headers=headers)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            
            if not feed or not hasattr(feed, 'entries'):
                logger.error(f"Invalid feed structure from {source.name}")
                return 0

            if feed.bozo:
                logger.error(f"Error parsing RSS feed for {source.name}: {feed.bozo_exception}")
                return 0

            if 'status' in feed and feed.status != 200:
                logger.error(f"Feed status error for {source.name}: {feed.status}")
                return 0
                
            if not hasattr(feed, 'entries'):
                logger.error(f"No entries found in feed for {source.name}")
                return 0
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed for {source.name}: {str(e)}")
            return 0

        if not feed.entries:
            logger.warning(f"No entries found in {source.name} RSS feed")
            return 0

        articles_added = 0
        logger.info(f"Found {len(feed.entries)} entries in {source.name} RSS feed")

        source_metrics = init_source_metrics(source.name)
        if not source_metrics:
            logger.error(f"Failed to initialize source metrics for {source.name}")
            return 0

        initial_count = source_metrics.article_count
        logger.info(f"Current article count for {source.name}: {initial_count}")

        try:
            for entry in feed.entries[:10]:
                try:
                    article_url = entry.link
                    published_date = None
                    
                    # Try to get the published date
                    if hasattr(entry, 'published_parsed'):
                        published_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    elif hasattr(entry, 'updated_parsed'):
                        published_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                    else:
                        published_date = datetime.utcnow()
                        
                    logger.debug(f"Processing article from {source.name}: {article_url}")
                    logger.debug(f"Article date: {published_date}")

                    exists = Article.query.filter_by(source_url=article_url).first()
                    if exists:
                        logger.debug(f"Article already exists: {article_url}")
                        continue

                    try:
                        content = entry.get('description', '')
                        if not content and 'content' in entry:
                            content = entry.content[0].value if isinstance(entry.content, list) else entry.content
                            
                        if 'content' in entry:
                            extended_content = entry.content[0].value if isinstance(entry.content, list) else entry.content
                            if len(extended_content) > len(content):
                                content = extended_content
                                
                        logger.debug(f"Using RSS feed content for {source.name}")
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
    logger.info(f"Scraping from sources: {[source.name for source in SOURCES]}")
    total_articles_added = 0

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