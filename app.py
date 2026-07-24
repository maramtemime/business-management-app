from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from sqlalchemy import or_ 

app = Flask(__name__)
app.secret_key = "super_secret_key_for_session" 

# --- DATABASE CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DATABASE MODEL ---
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    direction = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=False)
    tools = db.Column(db.Text, nullable=True)
    invoice = db.Column(db.Float, default=0.0)
    date = db.Column(db.String(10), nullable=False)
    done = db.Column(db.Boolean, default=False)
    canceled = db.Column(db.Boolean, default=False)
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

    # EXCLUDE canceled tasks from active dashboard view
    active_tasks = Task.query.filter_by(canceled=False).all()
    
    for t in active_tasks:
        t.time_diff = get_time_diff(t.date)
        try:
            date_obj = datetime.strptime(t.date, "%Y-%m-%d")
            t.date_display = date_obj.strftime("%d/%m/%Y")
        except ValueError:
            t.date_display = t.date

    today_tasks = [t for t in active_tasks if t.date == today]
    pending_tasks = [t for t in active_tasks if not t.done]
    
    done_week_tasks = []
    for t in active_tasks:
        if t.done:
            try:
                task_d = datetime.strptime(t.date, "%Y-%m-%d").date()
                if task_d >= start_week:
                    done_week_tasks.append(t)
            except ValueError:
                continue

    errors = request.args.getlist("errors")

    count_today = len(today_tasks)
    count_pending = len(pending_tasks)
    
    # FIX: Count ONLY tasks completed for the current week instead of all historical done tasks
    count_done = len(done_week_tasks)

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

@app.route("/add_task", methods=["POST"])
def add_task():
    client_name = request.form.get("client_name", "").strip()
    phone = request.form.get("phone", "").strip()
    direction = request.form.get("direction", "").strip()
    description = request.form.get("description", "").strip()
    tools = request.form.get("tools", "").strip()
    invoice_raw = request.form.get("invoice", "0").strip()
    date_value = request.form.get("date", "").strip()
    note = request.form.get("note", "").strip()
    
    errors = []

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

    if errors:
        return jsonify({
            "success": False, 
            "errors": errors,
            "phone_error": "Le numéro de téléphone doit contenir uniquement des chiffres." in errors
        }), 400

    is_past_date = task_date_obj < date.today()

    new_task = Task(
        client_name=client_name,
        phone=phone,
        direction=direction,
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
        task_id = request.form.get("task_index") or request.form.get("task_id") or request.form.get("index")
        
        if not task_id:
            return redirect(url_for("dashboard"))
        
        task = Task.query.get(int(task_id))
        
        if task:
            date_value = request.form.get("date", "").strip()
            
            try:
                task_date_obj = datetime.strptime(date_value, "%Y-%m-%d").date()
            except ValueError:
                task_date_obj = date.today()
                date_value = task_date_obj.strftime("%Y-%m-%d")

            is_done_checked = (request.form.get("done") == "on")

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
        task.canceled = True
        task.done = False  
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route("/check_date_tasks")
def check_date_tasks():
    date_val = request.args.get("date", "").strip()
    if not date_val:
        return jsonify({"count": 0, "tasks": []})
    
    tasks = Task.query.filter_by(date=date_val, canceled=False, done=False).all()
    
    task_list = []
    for t in tasks:
        task_list.append({
            "id": t.id,
            "client_name": t.client_name,
            "phone": t.phone,
            "direction": t.direction or "---",
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

@app.route('/archive')
def archive():
    archived_tasks = Task.query.filter(
        or_(Task.done == True, Task.canceled == True)
    ).order_by(Task.date.desc()).all()
    
    total_completed = Task.query.filter_by(done=True, canceled=False).count()
    total_canceled = Task.query.filter_by(canceled=True).count()

    return render_template(
        'archive.html',
        tasks=archived_tasks,
        total_completed=total_completed,
        total_canceled=total_canceled
    )

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)