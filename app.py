
import os
import time
import threading
import random
from flask import Flask, jsonify, request, abort

app = Flask(__name__)

lock = threading.Lock()
state = {
    "running": False,
    "balance": 5.0,
    "decisions": 0,
    "last_event": "Simulation en pause",
    "mode": "PAPER ONLY"
}

CONTROL_TOKEN = os.environ.get("SIM_CONTROL_TOKEN", "")

def authorized():
    if not CONTROL_TOKEN:
        abort(503, "Control token not configured")
    if request.headers.get("Authorization") != f"Bearer {CONTROL_TOKEN}":
        abort(401, "Unauthorized")

def simulation_worker():
    while True:
        time.sleep(10)
        with lock:
            if state["running"]:
                change = random.uniform(-0.01, 0.015)
                state["balance"] = round(
                    max(0, state["balance"] + change), 5
                )
                state["decisions"] += 1
                state["last_event"] = (
                    f"Décision simulée #{state['decisions']}"
                )

threading.Thread(
    target=simulation_worker,
    daemon=True
).start()

@app.get("/")
def home():
    return jsonify({
        "service": "GrokDesk Simulation",
        "mode": "PAPER ONLY",
        "message": "Serveur opérationnel"
    })

@app.get("/status")
def status():
    with lock:
        return jsonify(state)

@app.post("/start")
def start():
    authorized()
    with lock:
        state["running"] = True
        state["last_event"] = "Simulation démarrée"
    return jsonify({"ok": True, "status": "running"})

@app.post("/stop")
def stop():
    authorized()
    with lock:
        state["running"] = False
        state["last_event"] = "Arrêt d'urgence activé"
    return jsonify({"ok": True, "status": "stopped"})
