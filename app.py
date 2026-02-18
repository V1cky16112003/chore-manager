from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from models import db, Chore, User, ChoreParticipant
import os

# ... (rest of imports/setup)

app = Flask(__name__)
# Cloud deployment support: Use DATABASE_URL if available, else local SQLite
database_url = os.environ.get("DATABASE_URL", "sqlite:///chores.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "funky-secret-key")

db.init_app(app)

with app.app_context():
    db.create_all()
    # Seed default users if empty
    if not User.query.first():
        db.session.add(User(name="Thiru", color="#FF6B6B")) # Red
        db.session.add(User(name="KP", color="#4ECDC4"))    # Teal
        db.session.add(User(name="Vicky", color="#FFE66D")) # Yellow
        db.session.add(User(name="Arvinth", color="#FF9F43")) # Orange
        db.session.commit()

# DEFAULT ADMIN PASSWORD
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "maamaa")

@app.route("/")
def index():
    chores = Chore.query.filter_by(status="pending").order_by(Chore.id).all()
    users = User.query.all()
    return render_template("index.html", chores=chores, users=users)

@app.route("/login_page")
def login_page():
    return """
    <html>
        <head>
            <link rel="stylesheet" href="/static/style.css">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="text-align: center; padding-top: 50px;">
            <div class="container">
                <div class="funky-card">
                    <h2>Admin Access</h2>
                    <form action="/login" method="POST">
                        <input type="password" name="password" class="funky-input" placeholder="Enter Magic Word" required>
                        <button type="submit" class="funky-btn">Unknown Super Power</button>
                    </form>
                    <br>
                    <a href="/">Back to Safety</a>
                </div>
            </div>
        </body>
    </html>
    """

@app.route("/login", methods=["POST"])
def login():
    password = request.form.get("password")
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.pop('is_admin', None)
    return redirect(url_for("index"))

@app.route("/add_user", methods=["POST"])
def add_user():
    if not session.get('is_admin'):
        return redirect(url_for("login_page"))
        
    name = request.form.get("name")
    color = request.form.get("color", "#000000")
    if name:
        db.session.add(User(name=name, color=color))
        db.session.commit()
    return redirect(url_for("index"))

@app.route("/add_chore", methods=["POST"])
def add_chore():
    if not session.get('is_admin'):
        return redirect(url_for("login_page"))

    title = request.form.get("title")
    points = request.form.get("points", type=int, default=10)
    participant_ids = request.form.getlist("participants")
    
    if title and participant_ids:
        assigned_user = User.query.get(participant_ids[0])
        
        new_chore = Chore(
            title=title, 
            points=points, 
            assigned_to=assigned_user,
            is_recurring=True
        )
        db.session.add(new_chore)
        db.session.flush() # Get ID
        
        for idx, uid in enumerate(participant_ids):
            cp = ChoreParticipant(chore_id=new_chore.id, user_id=uid, rotation_order=idx)
            db.session.add(cp)
            
        db.session.commit()
    
    return redirect(url_for("index"))

@app.route("/complete/<int:chore_id>", methods=["POST"])
def complete_chore(chore_id):
    if not session.get('is_admin'):
        return redirect(url_for("login_page"))

    chore = Chore.query.get_or_404(chore_id)
    
    if chore.is_recurring and chore.participants_association:
        # Get sorted participants
        assoc = chore.participants_association # properly ordered by rotation_order in model
        
        # Find current user index logic
        current_idx = -1
        for i, p in enumerate(assoc):
            if p.user_id == chore.assigned_to_id:
                current_idx = i
                break
        
        if current_idx != -1:
            next_idx = (current_idx + 1) % len(assoc)
            next_user = assoc[next_idx].user
            
            chore.assigned_to = next_user
            chore.status = "pending"
        else:
             # Fallback
             chore.assigned_to = assoc[0].user
             chore.status = "pending"

    else:
        chore.status = "completed"
        
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/reorder_chore/<int:chore_id>", methods=["POST"])
def reorder_chore(chore_id):
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    new_order_ids = data.get("user_ids", []) # List of user IDs in new order
    
    chore = Chore.query.get_or_404(chore_id)
    
    # Update rotation_order for each participant
    for idx, uid in enumerate(new_order_ids):
        # find the participant assoc
        assoc = next((p for p in chore.participants_association if p.user_id == int(uid)), None)
        if assoc:
            assoc.rotation_order = idx
            
    db.session.commit()
    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(debug=True)
