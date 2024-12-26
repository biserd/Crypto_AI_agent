import tweepy
import telegram
import logging
from app import db
from models import Article, DistributionLog
import os

class TwitterDistributor:
    def __init__(self):
        self.api = None  # Initialize in setup_twitter()
    
    def setup_twitter(self):
        # Note: In real implementation, these would be environment variables
        auth = tweepy.OAuthHandler("API_KEY", "API_SECRET")
        auth.set_access_token("ACCESS_TOKEN", "ACCESS_TOKEN_SECRET")
        self.api = tweepy.API(auth)

    def post_article(self, article):
        try:
            if not self.api:
                self.setup_twitter()
            
            tweet_text = f"{article.title}\n\nRead more: {article.source_url}"
            self.api.update_status(tweet_text)
            
            log = DistributionLog(
                article_id=article.id,
                platform='twitter',
                status='success',
            )
            db.session.add(log)
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Twitter posting error: {str(e)}")
            log = DistributionLog(
                article_id=article.id,
                platform='twitter',
                status='error',
                message=str(e)
            )
            db.session.add(log)
            db.session.commit()

class TelegramDistributor:
    def __init__(self):
        self.bot = None  # Initialize in setup_telegram()
        
    def setup_telegram(self):
        # Note: In real implementation, this would be an environment variable
        self.bot = telegram.Bot(token="BOT_TOKEN")
    
    def send_article(self, article):
        try:
            if not self.bot:
                self.setup_telegram()
            
            message = f"*{article.title}*\n\n{article.summary}\n\n[Read more]({article.source_url})"
            
            self.bot.send_message(
                chat_id="CHANNEL_ID",
                text=message,
                parse_mode='Markdown'
            )
            
            log = DistributionLog(
                article_id=article.id,
                platform='telegram',
                status='success',
            )
            db.session.add(log)
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Telegram posting error: {str(e)}")
            log = DistributionLog(
                article_id=article.id,
                platform='telegram',
                status='error',
                message=str(e)
            )
            db.session.add(log)
            db.session.commit()

def distribute_articles():
    """Distribute processed articles that haven't been published yet"""
    twitter = TwitterDistributor()
    telegram = TelegramDistributor()
    
    articles = Article.query.filter_by(published=False).all()
    
    for article in articles:
        try:
            twitter.post_article(article)
            telegram.send_article(article)
            
            article.published = True
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Distribution error for article {article.id}: {str(e)}")
            continue
