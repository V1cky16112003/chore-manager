from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from models import db, Chore, User, ChoreParticipant, MenuItem
import os

# ... (rest of imports/setup)

app = Flask(__name__)
# Cloud deployment support: Use DATABASE_URL if available, else local SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
database_url = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(basedir, "chores.db"))
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "funky-secret-key")

db.init_app(app)

with app.app_context():
    db.create_all()
    
    # Auto-migration: Add new columns to existing tables (Postgres doesn't auto-add them)
    from sqlalchemy import text, inspect
    with db.engine.connect() as conn:
        inspector = inspect(db.engine)
        # Add display_order to chore table if missing
        if 'chore' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('chore')]
            if 'display_order' not in columns:
                conn.execute(text('ALTER TABLE chore ADD COLUMN display_order INTEGER DEFAULT 0'))
                conn.commit()
    # Seed default users if empty
    if not User.query.first():
        db.session.add(User(name="Thiru", color="#FF6B6B")) # Red
        db.session.add(User(name="KP", color="#4ECDC4"))    # Teal
        db.session.add(User(name="Vicky", color="#FFE66D")) # Yellow
        db.session.add(User(name="Arvinth", color="#FF9F43")) # Orange
        db.session.commit()

# DEFAULT ADMIN PASSWORD
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "maamaa")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["Lunch", "Dinner"]

@app.route("/")
def index():
    chores = Chore.query.filter_by(status="pending").order_by(Chore.display_order, Chore.id).all()
    users = User.query.all()
    
    # Build menu grid: {day: {meal_type: MenuItem}}
    menu = {}
    for day in DAYS:
        menu[day] = {}
        for meal in MEALS:
            item = MenuItem.query.filter_by(day=day, meal_type=meal).first()
            menu[day][meal] = item
    
    return render_template("index.html", chores=chores, users=users, menu=menu, days=DAYS, meals=MEALS)

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

@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if not session.get('is_admin'):
        return redirect(url_for("login_page"))

    user = User.query.get_or_404(user_id)

    # Remove user from all chore rotations
    ChoreParticipant.query.filter_by(user_id=user_id).delete()

    # For chores where this user is currently assigned, assign to first remaining participant
    chores = Chore.query.filter_by(assigned_to_id=user_id).all()
    for chore in chores:
        if chore.participants_association:
            chore.assigned_to = chore.participants_association[0].user
        else:
            chore.assigned_to = None

    db.session.delete(user)
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
        
        # Set display_order to max+1
        max_order = db.session.query(db.func.max(Chore.display_order)).scalar() or 0
        new_chore = Chore(
            title=title, 
            points=points, 
            assigned_to=assigned_user,
            is_recurring=True,
            display_order=max_order + 1
        )
        db.session.add(new_chore)
        db.session.flush() # Get ID
        
        for idx, uid in enumerate(participant_ids):
            cp = ChoreParticipant(chore_id=new_chore.id, user_id=uid, rotation_order=idx)
            db.session.add(cp)
            
        db.session.commit()
    
    return redirect(url_for("index"))

@app.route("/delete_chore/<int:chore_id>", methods=["POST"])
def delete_chore(chore_id):
    if not session.get('is_admin'):
        return redirect(url_for("login_page"))

    chore = Chore.query.get_or_404(chore_id)
    db.session.delete(chore)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/remove_participant/<int:chore_id>/<int:user_id>", methods=["POST"])
def remove_participant(chore_id, user_id):
    if not session.get('is_admin'):
        return redirect(url_for("login_page"))

    chore = Chore.query.get_or_404(chore_id)
    participant = ChoreParticipant.query.filter_by(chore_id=chore_id, user_id=user_id).first()

    if participant:
        db.session.delete(participant)
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

@app.route("/reorder_tasks", methods=["POST"])
def reorder_tasks():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    chore_ids = data.get("chore_ids", [])
    
    for idx, cid in enumerate(chore_ids):
        chore = Chore.query.get(int(cid))
        if chore:
            chore.display_order = idx
    
    db.session.commit()
    return jsonify({"status": "success"})

@app.route("/set_menu", methods=["POST"])
def set_menu():
    if not session.get('is_admin'):
        return redirect(url_for("login_page"))
    
    for day in DAYS:
        for meal in MEALS:
            field_name = f"{day}_{meal}"
            food_name = request.form.get(field_name, "").strip()
            
            item = MenuItem.query.filter_by(day=day, meal_type=meal).first()
            if item:
                item.food_name = food_name
                item.is_cooked = False  # Reset when menu is updated
            else:
                item = MenuItem(day=day, meal_type=meal, food_name=food_name)
                db.session.add(item)
    
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/toggle_cooked/<int:item_id>", methods=["POST"])
def toggle_cooked(item_id):
    if not session.get('is_admin'):
        return redirect(url_for("login_page"))
    
    item = MenuItem.query.get_or_404(item_id)
    item.is_cooked = not item.is_cooked
    db.session.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
