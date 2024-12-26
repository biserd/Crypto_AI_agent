import tweepy
from telegram.ext import Updater
import logging
from app import db
from models import Article, DistributionLog
import os
import time
from requests.exceptions import RequestException

class TwitterDistributor:
    def __init__(self):
        self.api = None
        self.credentials_valid = False

    def setup_twitter(self):
        """Setup Twitter API with proper error handling"""
        try:
            api_key = os.environ.get("TWITTER_API_KEY")
            api_secret = os.environ.get("TWITTER_API_SECRET")
            access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
            access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

            if not all([api_key, api_secret, access_token, access_token_secret]):
                logging.error("Twitter credentials not configured. Please set all required environment variables.")
                return False

            auth = tweepy.OAuthHandler(api_key, api_secret)
            auth.set_access_token(access_token, access_token_secret)
            self.api = tweepy.API(auth)
            self.credentials_valid = True
            return True
        except Exception as e:
            logging.error(f"Twitter setup error: {str(e)}")
            return False

    def post_article(self, article):
        try:
            if not self.credentials_valid and not self.setup_twitter():
                log = DistributionLog(
                    article_id=article.id,
                    platform='twitter',
                    status='error',
                    message='Invalid Twitter credentials'
                )
                db.session.add(log)
                db.session.commit()
                return False

            tweet_text = f"{article.title}\n\nRead more: {article.source_url}"
            self.api.update_status(tweet_text)

            log = DistributionLog(
                article_id=article.id,
                platform='twitter',
                status='success'
            )
            db.session.add(log)
            db.session.commit()
            return True

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
            return False

class TelegramDistributor:
    def __init__(self):
        self.bot = None
        self.credentials_valid = False

    def setup_telegram(self):
        """Setup Telegram bot with proper error handling"""
        try:
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            if not bot_token:
                logging.error("Telegram bot token not configured")
                return False

            self.updater = Updater(token=bot_token, use_context=True)
            self.bot = self.updater.bot
            self.credentials_valid = True
            return True
        except Exception as e:
            logging.error(f"Telegram setup error: {str(e)}")
            return False

    def send_article(self, article):
        try:
            if not self.credentials_valid and not self.setup_telegram():
                log = DistributionLog(
                    article_id=article.id,
                    platform='telegram',
                    status='error',
                    message='Invalid Telegram credentials'
                )
                db.session.add(log)
                db.session.commit()
                return False

            channel_id = os.environ.get("TELEGRAM_CHANNEL_ID")
            if not channel_id:
                logging.error("Telegram channel ID not configured")
                return False

            message = f"*{article.title}*\n\n{article.summary}\n\n[Read more]({article.source_url})"

            self.bot.send_message(
                chat_id=channel_id,
                text=message,
                parse_mode='Markdown'
            )

            log = DistributionLog(
                article_id=article.id,
                platform='telegram',
                status='success'
            )
            db.session.add(log)
            db.session.commit()
            return True

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
            return False

def distribute_articles():
    """Distribute processed articles that haven't been published yet"""
    twitter = TwitterDistributor()
    telegram = TelegramDistributor()

    articles = Article.query.filter_by(published=False).all()
    logging.info(f"Found {len(articles)} unpublished articles to distribute")

    for article in articles:
        try:
            twitter_success = twitter.post_article(article)
            telegram_success = telegram.send_article(article)

            if twitter_success or telegram_success:
                article.published = True
                db.session.commit()
                logging.info(f"Successfully distributed article {article.id} to some platforms")
            else:
                logging.warning(f"Failed to distribute article {article.id} to any platform")

        except Exception as e:
            logging.error(f"Distribution error for article {article.id}: {str(e)}")
            continue