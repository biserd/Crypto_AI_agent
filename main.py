
from app import app, socketio
import threading
from scheduler import start_scheduler

def run_scheduler():
    start_scheduler()

if __name__ == "__main__":
    # Start scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Run the main Flask app
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
