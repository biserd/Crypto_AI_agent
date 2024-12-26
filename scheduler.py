import time
import logging
import schedule
from scraper import scrape_articles
from nlp_processor import process_articles
from distributors import distribute_articles

def run_pipeline():
    """Run the complete news pipeline"""
    logging.info("Starting news pipeline")
    scrape_articles()
    process_articles()
    distribute_articles()
    logging.info("Completed news pipeline")

def start_scheduler():
    """Initialize and start the scheduler"""
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
