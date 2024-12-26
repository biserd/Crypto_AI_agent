import time
import logging
import schedule
from datetime import datetime
from app import app
from scraper import scrape_articles
from nlp_processor import process_articles
from distributors import distribute_articles
from crypto_price_tracker import CryptoPriceTracker

def run_pipeline():
    """Run the complete news pipeline with proper error handling"""
    logging.info("Starting news pipeline")

    with app.app_context():
        app.config['LAST_SCRAPER_RUN'] = datetime.utcnow()
        try:
            # Update crypto prices
            try:
                price_tracker = CryptoPriceTracker()
                price_tracker.fetch_current_prices()
                logging.info("Updated cryptocurrency prices")
            except Exception as e:
                logging.error(f"Price tracking failed: {str(e)}", exc_info=True)

            # Run scraper
            try:
                logging.info("Starting article scraping process")
                articles_added = scrape_articles()
                logging.info(f"Scraper completed: {articles_added} new articles added")
            except Exception as e:
                logging.error(f"Scraping failed: {str(e)}", exc_info=True)
                articles_added = 0

            # Process articles
            try:
                if articles_added > 0:
                    logging.info("Starting sentiment analysis for new articles")
                    process_articles()
                    logging.info("Completed sentiment analysis processing")
                else:
                    logging.info("No new articles to process for sentiment")
            except Exception as e:
                logging.error(f"Sentiment analysis failed: {str(e)}", exc_info=True)

            # Only distribute if we have new articles
            if articles_added > 0:
                try:
                    logging.info("Starting article distribution")
                    distribute_articles()
                    logging.info("Completed article distribution")
                except Exception as e:
                    logging.error(f"Distribution failed: {str(e)}", exc_info=True)

            logging.info("Completed news pipeline")
        except Exception as e:
            logging.error(f"Pipeline error: {str(e)}", exc_info=True)

def start_scheduler():
    """Initialize and start the scheduler with proper error handling"""
    # Configure logging with more detail
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logging.info("Starting news aggregator scheduler")

    # Run once immediately on startup with app context
    try:
        logging.info("Running initial pipeline")
        run_pipeline()
    except Exception as e:
        logging.error(f"Initial pipeline run failed: {str(e)}", exc_info=True)

    # Schedule regular runs
    def scheduled_pipeline():
        with app.app_context():
            run_pipeline()

    def scheduled_price_update():
        with app.app_context():
            CryptoPriceTracker().fetch_current_prices()

    schedule.every(15).minutes.do(scheduled_pipeline)
    schedule.every(5).minutes.do(scheduled_price_update)

    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except Exception as e:
            logging.error(f"Scheduler error: {str(e)}", exc_info=True)
            time.sleep(60)
            continue

if __name__ == "__main__":
    start_scheduler()