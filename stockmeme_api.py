from flask import Flask, jsonify
from datetime import datetime, timezone
import threading
import time

app = Flask(__name__)

# Shared status data
status_data = {
    "status": "stopped",
    "last_scan": None
}

# Dummy scan loop (replace with your watcher logic)
def watcher_loop():
    global status_data
    status_data["status"] = "running"
    while True:
        # Here you would call your real scan_once()
        status_data["last_scan"] = datetime.now(timezone.utc).isoformat()
        time.sleep(300)  # match your scan interval

# Run watcher loop in a background thread
threading.Thread(target=watcher_loop, daemon=True).start()

@app.route("/status")
def status():
    return jsonify(status_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
