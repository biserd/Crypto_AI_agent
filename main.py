
import eventlet
eventlet.monkey_patch()

from app import app, socketio, db, sync_article_counts
import threading
from scheduler import start_scheduler

def run_scheduler():
    start_scheduler()

if __name__ == "__main__":
    # Initialize database within app context
    with app.app_context():
        try:
            db.create_all()
            sync_article_counts()
        except Exception as e:
            print(f"Database initialization error: {e}")

    # Start scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

    # Start the application
    socketio.run(
        app,
        host='0.0.0.0',
        port=3000,
        debug=False,
        use_reloader=False
    )
