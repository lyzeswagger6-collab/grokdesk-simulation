
import os
import time
import hmac
import secrets
import threading
from collections import defaultdict
from flask import (
    Flask, request, session, redirect,
    url_for, jsonify, render_template_string, abort
)

app = Flask(__name__)

password = os.environ.get("SIM_LOGIN_PASSWORD")
secret = os.environ.get("FLASK_SECRET_KEY")

if not password or not secret:
    raise RuntimeError("Configuration de sécurité manquante")

app.secret_key = secret
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800,
)

lock = threading.Lock()
state = {
    "running": False,
    "balance": 5.0,
    "decisions": 0,
    "last_event": "Simulation en pause",
    "mode": "PAPER ONLY",
}

attempts = defaultdict(list)

LOGIN_PAGE = """
<h2>GrokDesk — Connexion privée</h2>
<form method="post">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <input type="password" name="password"
         placeholder="Mot de passe" required>
  <button type="submit">Se connecter</button>
</form>
<p>{{ error }}</p>
"""

DASHBOARD = """
<h2>GrokDesk — PAPER ONLY</h2>
<p>Solde fictif : <b id="balance">...</b> SOL</p>
<p>Décisions : <b id="decisions">...</b></p>
<p>État : <b id="running">...</b></p>
<p id="event"></p>
<button onclick="action('/api/start')">Démarrer la simulation</button>
<button onclick="action('/api/stop')"
 style="background:#c00;color:white;padding:12px">
 ARRÊT D'URGENCE
</button>
<form method="post" action="/logout">
<input type="hidden" name="csrf" value="{{ csrf }}">
<button type="submit">Se déconnecter</button>
</form>
<script>
const csrf = "{{ csrf }}";
async function refresh() {
 const r = await fetch('/api/status');
 if (r.status === 401) { location.href='/login'; return; }
 const s = await r.json();
 document.getElementById('balance').textContent = s.balance;
 document.getElementById('decisions').textContent = s.decisions;
 document.getElementById('running').textContent =
   s.running ? 'EN MARCHE' : 'EN PAUSE';
 document.getElementById('event').textContent = s.last_event;
}
async function action(path) {
 const r = await fetch(path, {
   method:'POST',
   headers:{'X-CSRF-Token':csrf}
 });
 if (!r.ok) { alert('Commande refusée'); return; }
 refresh();
}
refresh();
setInterval(refresh, 5000);
</script>
"""

def logged_in():
    return session.get("authenticated") is True

def require_login():
    if not logged_in():
        abort(401)

def require_csrf():
    token = request.headers.get("X-CSRF-Token") or request.form.get("csrf", "")
    if not hmac.compare_digest(token, session.get("csrf", "")):
        abort(403)

def worker():
    while True:
        time.sleep(10)
        with lock:
            if state["running"]:
                state["decisions"] += 1
                state["last_event"] = (
                    f"Décision fictive #{state['decisions']}"
                )

threading.Thread(target=worker, daemon=True).start()

@app.get("/")
def home():
    return redirect("/dashboard" if logged_in() else "/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    ip = request.remote_addr or "unknown"
    now = time.time()
    attempts[ip] = [t for t in attempts[ip] if now - t < 600]

    if len(attempts[ip]) >= 5:
        abort(429)

    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)

    error = ""
    if request.method == "POST":
        require_csrf()
        supplied = request.form.get("password", "")
        if hmac.compare_digest(supplied.encode("utf-8"), password.encode("utf-8")):
            session.clear()
            session["authenticated"] = True
            session["csrf"] = secrets.token_urlsafe(32)
            session.permanent = False
            attempts.pop(ip, None)
            return redirect("/dashboard")
        attempts[ip].append(now)
        error = "Mot de passe incorrect"

    return render_template_string(
        LOGIN_PAGE, csrf=session["csrf"], error=error
    )

@app.get("/dashboard")
def dashboard():
    require_login()
    return render_template_string(
        DASHBOARD, csrf=session["csrf"]
    )

@app.post("/logout")
def logout():
    require_login()
    require_csrf()
    session.clear()
    return redirect("/login")

@app.get("/api/status")
def api_status():
    require_login()
    with lock:
        return jsonify(state)

@app.post("/api/start")
def start():
    require_login()
    require_csrf()
    with lock:
        state["running"] = True
        state["last_event"] = "Simulation démarrée"
    return jsonify({"ok": True})

@app.post("/api/stop")
def stop():
    require_login()
    require_csrf()
    with lock:
        state["running"] = False
        state["last_event"] = "Arrêt d'urgence activé"
    return jsonify({"ok": True})
