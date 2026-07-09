from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.secret_key = "super_secret_key_for_session" 

# --- DATABASE CONFIGURATION ---
# This creates a local file named 'project.db' inside your project folder
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DATABASE MODEL (TABLE STRUCTURE) ---
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    direction = db.Column(db.String(200), nullable=True) # <--- NEW FIELD HERE
    description = db.Column(db.Text, nullable=False)
    tools = db.Column(db.Text, nullable=True)
    invoice = db.Column(db.Float, default=0.0)
    date = db.Column(db.String(10), nullable=False)
    done = db.Column(db.Boolean, default=False)
    note = db.Column(db.Text, nullable=True)

def get_time_diff(task_date):
    """Return difference in days between task date and today"""
    try:
        task_date_obj = datetime.strptime(task_date, "%Y-%m-%d").date()
        today = date.today()
        return (task_date_obj - today).days
    except ValueError:
        return 0 

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == "1234":
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Mot de passe incorrect")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    today = str(date.today())
    today_display = date.today().strftime("%d/%m/%Y")
    
    start_week = date.today() - timedelta(days=date.today().weekday())
    end_week = start_week + timedelta(days=6)
    
    french_months = {
        1: "janv", 2: "févr", 3: "mars", 4: "avr", 5: "mai", 6: "juin",
        7: "juil", 8: "août", 9: "sept", 10: "oct", 11: "nov", 12: "déc"
    }
    
    start_week_display = f"{start_week.day} {french_months[start_week.month]}"
    end_week_display = f"{end_week.day} {french_months[end_week.month]}"
    week_range_string = f"{start_week_display} au {end_week_display}"

    # --- SQLALCHEMY QUERY ---
    # Fetch ALL tasks from the database instead of a memory list
    all_tasks = Task.query.all()
    
    # Format dates dynamically for on-screen layout templates
    for t in all_tasks:
        t.time_diff = get_time_diff(t.date)
        try:
            date_obj = datetime.strptime(t.date, "%Y-%m-%d")
            t.date_display = date_obj.strftime("%d/%m/%Y")
        except ValueError:
            t.date_display = t.date

    # Filter task groups out of our processed database records
    today_tasks = [t for t in all_tasks if t.date == today]
    pending_tasks = [t for t in all_tasks if not t.done]
    
    done_week_tasks = []
    for t in all_tasks:
        if t.done:
            try:
                task_d = datetime.strptime(t.date, "%Y-%m-%d").date()
                if task_d >= start_week:
                    done_week_tasks.append(t)
            except ValueError:
                continue

    errors = request.args.getlist("errors")

    # --- SQLALCHEMY QUERY ---
    all_tasks = Task.query.all()
    
    # Calculate counts for summary badges
    count_today = len([t for t in all_tasks if t.date == today])
    count_pending = len([t for t in all_tasks if not t.done])
    count_done = len([t for t in all_tasks if t.done])

    return render_template(
        "dashboard.html",
        today_tasks=today_tasks,
        pending_tasks=pending_tasks,
        done_week_tasks=done_week_tasks,
        count_today=count_today,
        count_pending=count_pending,
        count_done=count_done,
        today=today_display,
        week_range=week_range_string,
        errors=errors
    )

from flask import jsonify, request, redirect, url_for
from datetime import datetime, date

@app.route("/add_task", methods=["POST"])
def add_task():
    client_name = request.form.get("client_name", "").strip()
    phone = request.form.get("phone", "").strip()
    direction = request.form.get("direction", "").strip()  # <--- 1. EXTRACT DIRECTION
    description = request.form.get("description", "").strip()
    tools = request.form.get("tools", "").strip()
    invoice_raw = request.form.get("invoice", "0").strip()
    date_value = request.form.get("date", "").strip()
    note = request.form.get("note", "").strip()
    
    errors = []

    # If you want 'direction' to be mandatory, add 'not direction' below.
    # Otherwise, leave it as is if it's optional!
    if not client_name or not description or not date_value:
        errors.append("Veuillez remplir tous les champs obligatoires.")

    if not phone.isdigit():
        errors.append("Le numéro de téléphone doit contenir uniquement des chiffres.")

    try:
        invoice = float(invoice_raw)
    except ValueError:
        errors.append("Le montant de la facture doit être un nombre valide.")
        invoice = 0.0

    try:
        task_date_obj = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        errors.append("Date invalide, veuillez vérifier la date.")
        task_date_obj = date.today()

    # --- RETURN JSON ERRORS IF VALIDATION FAILS ---
    if errors:
        return jsonify({
            "success": False, 
            "errors": errors,
            "phone_error": "Le numéro de téléphone doit contenir uniquement des chiffres." in errors
        }), 400

    is_past_date = task_date_obj < date.today()

    # --- SQLALCHEMY INSERT ---
    new_task = Task(
        client_name=client_name,
        phone=phone,
        direction=direction,  # <--- 2. PASS TO TASK MODEL
        description=description,
        tools=tools,
        invoice=invoice,
        date=date_value, 
        done=True if is_past_date else False, 
        note=note
    )

    try:
        db.session.add(new_task)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "errors": ["Une erreur serveur est survenue."]}), 500

@app.route("/toggle_done/<int:index>")
def toggle_done(index):
    # Retrieve task using primary key ID
    task = Task.query.get(index)
    if task:
        task.done = not task.done
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            
    return redirect(url_for("dashboard"))

@app.route("/update_task", methods=["POST"])
def update_task():
    try:
        # Check task_index first to match your exact HTML form attribute
        task_id = request.form.get("task_index") or request.form.get("task_id") or request.form.get("index")
        
        if not task_id:
            return redirect(url_for("dashboard"))
        
        # Query task by ID
        task = Task.query.get(int(task_id))
        
        if task:
            date_value = request.form.get("date", "").strip()
            
            # Safely parse task date
            try:
                task_date_obj = datetime.strptime(date_value, "%Y-%m-%d").date()
            except ValueError:
                task_date_obj = date.today()
                date_value = task_date_obj.strftime("%Y-%m-%d")

            is_done_checked = (request.form.get("done") == "on")

            # Mutate database record values
            task.client_name = request.form.get("client_name", "").strip()
            task.phone = request.form.get("phone", "").strip()
            task.direction = request.form.get("direction", "").strip()
            task.description = request.form.get("description", "").strip()
            task.tools = request.form.get("tools", "").strip()
            
            try:
                task.invoice = float(request.form.get("invoice", 0) or 0)
            except ValueError:
                task.invoice = 0.0

            task.date = date_value
            task.note = request.form.get("note", "").strip()
            
            # Auto-mark done for past dates unless manually unchecked
            if not is_done_checked and task_date_obj < date.today():
                task.done = True
            else:
                task.done = is_done_checked
                
            db.session.commit()
                
    except (ValueError, TypeError):
        db.session.rollback()

    return redirect(url_for("dashboard"))

@app.route("/get_task/<int:index>")
def get_task(index):
    task = Task.query.get(index)
    if task:
        # Convert model attributes to JSON dictionary representation payload
        return jsonify({
            "id": task.id,
            "client_name": task.client_name,
            "phone": task.phone,
            "direction": task.direction or "",
            "description": task.description,
            "tools": task.tools,
            "invoice": task.invoice,
            "date": task.date,
            "done": task.done,
            "note": task.note
        })
    return jsonify({"error": "Task not found"}), 404

@app.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    task = Task.query.get(task_id)
    if task:
        db.session.delete(task)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route("/check_date_tasks")
def check_date_tasks():
    date_val = request.args.get("date", "").strip()
    if not date_val:
        return jsonify({"count": 0, "tasks": []})
    
    # Query all tasks for the given date
    tasks = Task.query.filter_by(date=date_val).all()
    
    task_list = []
    for t in tasks:
        task_list.append({
            "id": t.id,
            "client_name": t.client_name,
            "phone": t.phone,
            "description": t.description,
            "tools": t.tools or "---",
            "invoice": t.invoice,
            "done": t.done,
            "note": t.note or "Aucune note."
        })

    return jsonify({
        "count": len(task_list),
        "tasks": task_list
    })

@app.route("/archive")
def archive():
    # Fetch all tasks marked as completed, ordered by most recent date
    archived_tasks = Task.query.filter_by(done=True).order_by(Task.date.desc()).all()
    
    # Calculate lifetime stats
    total_completed = len(archived_tasks)
    total_revenue = sum(task.invoice for task in archived_tasks if task.invoice)

    return render_template(
        "archive.html",
        tasks=archived_tasks,
        total_completed=total_completed,
        total_revenue=total_revenue
    )

# --- AUTOMATIC TABLE CREATION BOOTSTRAPPING ENGINE ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all() # This creates project.db and the tables automatically if they don't exist!
    app.run(debug=True)