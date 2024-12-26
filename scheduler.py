import time
import logging
import schedule
from app import app
from scraper import scrape_articles
from nlp_processor import process_articles
from distributors import distribute_articles

def run_pipeline():
    """Run the complete news pipeline"""
    with app.app_context():
        try:
            logging.info("Starting news pipeline")

            # Run scraper
            articles_added = scrape_articles()
            logging.info(f"Scraper added {articles_added} new articles")

            if articles_added > 0:
                # Process articles
                logging.info("Processing new articles")
                process_articles()

                # Distribute articles
                logging.info("Distributing processed articles")
                distribute_articles()
            else:
                logging.info("No new articles to process")

            logging.info("Completed news pipeline")
        except Exception as e:
            logging.error(f"Pipeline error: {str(e)}")

def start_scheduler():
    """Initialize and start the scheduler"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logging.info("Starting news aggregator scheduler")

    # Run once immediately on startup
    logging.info("Running initial pipeline")
    run_pipeline()

    # Schedule regular runs
    schedule.every(1).hours.do(run_pipeline)

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