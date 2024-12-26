import time
import logging
import schedule
from app import app
from scraper import scrape_articles
from nlp_processor import process_articles
from distributors import distribute_articles

def run_pipeline():
    """Run the complete news pipeline with proper error handling"""
    with app.app_context():
        try:
            logging.info("Starting news pipeline")

            # Run scraper
            try:
                articles_added = scrape_articles()
                logging.info(f"Scraper added {articles_added} new articles")
            except Exception as e:
                logging.error(f"Scraping failed: {str(e)}")
                articles_added = 0

            # Always try to process articles, even if no new ones were added
            # This ensures any previously unprocessed articles get analyzed
            try:
                logging.info("Processing articles for sentiment analysis")
                process_articles()
            except Exception as e:
                logging.error(f"Sentiment analysis failed: {str(e)}")

            # Only distribute if we have new articles
            if articles_added > 0:
                try:
                    logging.info("Distributing processed articles")
                    distribute_articles()
                except Exception as e:
                    logging.error(f"Distribution failed: {str(e)}")

            logging.info("Completed news pipeline")
        except Exception as e:
            logging.error(f"Pipeline error: {str(e)}")

def start_scheduler():
    """Initialize and start the scheduler with proper error handling"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logging.info("Starting news aggregator scheduler")

    # Run once immediately on startup
    try:
        logging.info("Running initial pipeline")
        run_pipeline()
    except Exception as e:
        logging.error(f"Initial pipeline run failed: {str(e)}")

    # Schedule regular runs
    schedule.every(15).minutes.do(run_pipeline)  # Run more frequently to catch up on any missed articles

    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except Exception as e:
            logging.error(f"Scheduler error: {str(e)}")
            time.sleep(60)
            continue

if __name__ == "__main__":
    start_scheduler()