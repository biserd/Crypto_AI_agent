import eventlet
eventlet.monkey_patch()

from app import app, socketio
import threading
from scheduler import start_scheduler
from database import db, init_app

def run_scheduler():
    start_scheduler()

if __name__ == "__main__":
    # Initialize database
    with app.app_context():
        try:
            init_app(app)
            db.create_all()
        except Exception as e:
            print(f"Database initialization error: {e}")

    # Start scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()