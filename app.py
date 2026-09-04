from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from sqlalchemy import or_ 
import json
import calendar

app = Flask(__name__)
app.secret_key = "super_secret_key_for_session" 

# --- DATABASE CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DATABASE MODELS ---
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
    workers = db.Column(db.Text, nullable=True)

class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone_num = db.Column(db.String(20), nullable=False)
    pay_per_normal_hr = db.Column(db.Float, default=0.0)
    pay_per_extra_hr = db.Column(db.Float, default=0.0)
    normal_hours = db.Column(db.Float, default=0.0)
    extra_hours = db.Column(db.Float, default=0.0)
    total_pay = db.Column(db.Float, default=0.0)
    _activities = db.Column('activities', db.Text, default='{}')
    def get_logs_for_day(self, day_name):
        """Returns WorkerTaskLog entries matching a specific French day of the week."""
        french_days = {
            'Lundi': 0, 'Mardi': 1, 'Mercredi': 2, 
            'Jeudi': 3, 'Vendredi': 4, 'Samedi': 5, 'Dimanche': 6
        }
        
        target_weekday = french_days.get(day_name)
        if target_weekday is None:
            return []

        matched_logs = []
        for log in self.task_logs:
            try:
                # Parses stored date_value ("YYYY-MM-DD")
                log_date = datetime.strptime(log.date, "%Y-%m-%d").date()
                if log_date.weekday() == target_weekday:
                    matched_logs.append(log)
            except (ValueError, TypeError):
                continue
                
        return matched_logs
    
class WorkerTaskLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False) # e.g. "2026-08-17"
    normal_hours = db.Column(db.Float, default=0.0)
    extra_hours = db.Column(db.Float, default=0.0)
    is_updated = db.Column(db.Boolean, default=False) # False = Yellow, True = Green

    worker = db.relationship('Worker', backref=db.backref('task_logs', lazy=True))
    task = db.relationship('Task', backref=db.backref('worker_logs', lazy=True))

    @property
    def activities(self):
        try:
            return json.loads(self._activities) if self._activities else {}
        except Exception:
            return {}

    @activities.setter
    def activities(self, value):
        self._activities = json.dumps(value)

class WorkerPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    worker = db.relationship('Worker', backref=db.backref('payments', lazy=True))

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
    count_done = len(done_week_tasks)

    all_workers = Worker.query.all()

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
        errors=errors,
        all_workers=all_workers
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
    selected_workers = request.form.getlist("workers") 
    workers_str = ",".join(selected_workers) if selected_workers else ""

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
        note=note,
        workers=workers_str
    )

    try:
        db.session.add(new_task)
        db.session.commit()

        # Automatically log tasks for each assigned worker
        for worker_name in selected_workers:
            worker = Worker.query.filter_by(full_name=worker_name).first()
            if worker:
                log = WorkerTaskLog(
                    worker_id=worker.id,
                    task_id=new_task.id,
                    date=date_value,
                    normal_hours=0.0,
                    extra_hours=0.0,
                    is_updated=False  # Unfilled state (Yellow)
                )
                db.session.add(log)

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
            
            # Fixed status update logic
            if is_done_checked:
                task.done = True
            elif task_date_obj < date.today():
                task.done = True
            else:
                task.done = False
                
            db.session.commit()
                
    except (ValueError, TypeError):
        db.session.rollback()

    selected_workers = request.form.getlist("workers")
    task.workers = ",".join(selected_workers) if selected_workers else ""

    return redirect(url_for("dashboard"))

@app.route("/get_task/<int:index>")
def get_task(index):
    task = Task.query.get(index)
    if task:
        worker_list = task.workers.split(",") if task.workers else []
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
            "note": task.note,
            "workers": worker_list
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
    
    tasks = Task.query.filter_by(date=date_val, canceled=False).all()
    
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

@app.route('/delete_client/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    task = Task.query.get_or_404(client_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('archive'))

@app.route('/travailleurs', methods=['GET', 'POST'])
def travailleurs():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone_num = request.form.get('phone_num', '').strip()
        try:
            pay_per_normal_hr = float(request.form.get('pay_per_normal_hr', 0))
            pay_per_extra_hr = float(request.form.get('pay_per_extra_hr', 0))
        except ValueError:
            pay_per_normal_hr = 0.0
            pay_per_extra_hr = 0.0
        
        new_worker = Worker(
            full_name=full_name,
            phone_num=phone_num,
            pay_per_normal_hr=pay_per_normal_hr,
            pay_per_extra_hr=pay_per_extra_hr,
            normal_hours=0.0,
            extra_hours=0.0,
            total_pay=0.0,
            
        )
        db.session.add(new_worker)
        db.session.commit()
        return redirect(url_for('travailleurs'))
        
    travailleurs = Worker.query.all()
    days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

    # Pre-build logs data structure
    worker_logs_data = {}
    for worker in travailleurs:
        worker_logs_data[worker.id] = {}
        for day_name in days:
            logs = worker.get_logs_for_day(day_name)
            worker_logs_data[worker.id][day_name] = [
                {
                    "log_id": log.id,
                    "client_name": log.task.client_name,
                    "phone": log.task.phone,
                    "direction": log.task.direction,
                    "description": log.task.description,
                    "tools": log.task.tools,
                    "invoice": log.task.invoice,
                    "date": log.task.date,
                    "note": log.task.note,
                    "normal_hours": log.normal_hours,
                    "extra_hours": log.extra_hours,
                    "is_updated": log.is_updated
                }
                for log in logs
            ]

    return render_template(
        'workers.html', 
        travailleurs=travailleurs, 
        worker_logs_data=worker_logs_data
    )



@app.route("/update_worker_hours", methods=["POST"])
def update_worker_hours():
    log_id = request.form.get("log_id")
    try:
        norm = float(request.form.get("normal_hours", 0))
        extra = float(request.form.get("extra_hours", 0))
    except ValueError:
        return jsonify({"success": False, "error": "Valeurs invalides."}), 400

    log = WorkerTaskLog.query.get(log_id)
    if not log:
        return jsonify({"success": False, "error": "Log introuvable."}), 404

    # Update log entry
    log.normal_hours = norm
    log.extra_hours = extra
    log.is_updated = True  # Flips status to Green

    # Recalculate global worker totals
    worker = log.worker
    all_logs = WorkerTaskLog.query.filter_by(worker_id=worker.id).all()
    
    total_norm = sum(l.normal_hours for l in all_logs)
    total_extra = sum(l.extra_hours for l in all_logs)
    
    worker.normal_hours = total_norm
    worker.extra_hours = total_extra
    worker.total_pay = (total_norm * worker.pay_per_normal_hr) + (total_extra * worker.pay_per_extra_hr)

    db.session.commit()
    return jsonify({"success": True})

@app.route("/api/archive_events")
def get_archive_events():
    archived_tasks = Task.query.filter(
        or_(Task.done == True, Task.canceled == True)
    ).all()
    
    events = []
    for task in archived_tasks:
        # Determine status color: Green for completed, Red for canceled
        is_canceled = task.canceled
        events.append({
            "id": task.id,
            "title": task.client_name,
            "start": task.date,  # Expected format YYYY-MM-DD
            "display": "list-item",
            "color": "#dc3545" if is_canceled else "#198754",
            "extendedProps": {
                "status": "canceled" if is_canceled else "completed"
            }
        })
    return jsonify(events)

# app.py
@app.route("/api/task/<int:task_id>/toggle_tool", methods=["POST"])
def toggle_tool(task_id):
    data = request.json
    tool_name = data.get("tool_name")
    # Update your task tools status in database here
    db.session.commit()
    return jsonify({"success": True})

@app.route('/get_worker/<int:worker_id>', methods=['GET'])
def get_worker(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    return jsonify({
        'id': worker.id,
        'full_name': worker.full_name,
        'phone_num': worker.phone_num or '',
        'pay_per_normal_hr': worker.pay_per_normal_hr,
        'pay_per_extra_hr': worker.pay_per_extra_hr
    })

@app.route('/update_worker', methods=['POST'])
def update_worker():
    worker_id = request.form.get('worker_id')
    worker = Worker.query.get_or_404(worker_id)
    
    worker.full_name = request.form.get('full_name')
    worker.phone_num = request.form.get('phone_num')
    worker.pay_per_normal_hr = float(request.form.get('pay_per_normal_hr', 0))
    worker.pay_per_extra_hr = float(request.form.get('pay_per_extra_hr', 0))
    
    # Recalculate total pay with updated rates
    worker.total_pay = (worker.normal_hours * worker.pay_per_normal_hr) + (worker.extra_hours * worker.pay_per_extra_hr)
    
    db.session.commit()
    return redirect(url_for('travailleurs'))

@app.route('/worker-archive')  # Or keep '/archive' if replacing the old route completely
def worker_archive():
    workers = Worker.query.all()
    
    worker_activity_data = {}
    for worker in workers:
        worker_activity_data[worker.id] = {}
        for log in worker.logs:
            if log.date:
                date_str = log.date.strftime('%Y-%m-%d') if isinstance(log.date, (date, datetime)) else str(log.date)
                worker_activity_data[worker.id][date_str] = worker_activity_data[worker.id].get(date_str, 0) + 1

    return render_template(
        'archive.html',
        workers=workers,
        worker_activity_data=worker_activity_data
    )


@app.route('/pay_worker', methods=['POST'])
def pay_worker():
    worker_id = request.form.get('worker_id')
    amount = float(request.form.get('amount', 0))
    
    if amount <= 0:
        return jsonify({'success': False, 'error': 'Montant invalide'}), 400
        
    worker = Worker.query.get_or_404(worker_id)
    payment = WorkerPayment(worker_id=worker.id, amount=amount, date=date.today())
    db.session.add(payment)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/worker_events/<int:worker_id>')
def get_worker_events(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    logs = WorkerTaskLog.query.filter_by(worker_id=worker_id).all()
    payments = WorkerPayment.query.filter_by(worker_id=worker_id).all()
    
    # Get all workers ordered by ID to match Jinja2 template indexing (1-based)
    all_workers = Worker.query.order_by(Worker.id).all()
    worker_index = next((i for i, w in enumerate(all_workers) if w.id == worker_id), 0)
    
    color_palette = ['#dc3545', '#198754', '#6f42c1', '#fd7e14', '#0d6efd', '#20c997', '#d63384']
    worker_color = color_palette[worker_index % len(color_palette)]
    
    events = []
    # Regular task hours
    for log in logs:
        events.append({
            'id': f"log_{log.id}",
            'title': f"{log.normal_hours}h Norm / {log.extra_hours}h Extra",
            'start': str(log.date),
            'color': worker_color,
            'textColor': '#ffffff'
        })
        
    # Payment Star markers
    for pay in payments:
        events.append({
            'id': f"pay_{pay.id}",
            'title': f"★ Payé: {pay.amount} DT",
            'start': str(pay.date),
            'color': worker_color,
            'textColor': '#ffffff'
        })
        
    return jsonify(events)

@app.route('/api/all_worker_events')
def get_all_worker_events():
    all_workers = Worker.query.order_by(Worker.id).all()
    color_palette = ['#dc3545', '#198754', '#6f42c1', '#fd7e14', '#0d6efd', '#20c997', '#d63384']
    
    events = []
    
    for index, worker in enumerate(all_workers):
        worker_color = getattr(worker, 'color', None) or color_palette[index % len(color_palette)]
        
        # Add task hours
        logs = WorkerTaskLog.query.filter_by(worker_id=worker.id).all()
        for log in logs:
            events.append({
                'id': f"log_{log.id}",
                'title': f"{worker.full_name}: {log.normal_hours}h Norm / {log.extra_hours}h Extra",
                'start': str(log.date),
                'color': worker_color,
                'textColor': '#ffffff'
            })
            
        # Add payment stars
        payments = WorkerPayment.query.filter_by(worker_id=worker.id).all()
        for pay in payments:
            events.append({
                'id': f"pay_{pay.id}",
                'title': f"★ {worker.full_name} Payé: {pay.amount} DT",
                'start': str(pay.date),
                'color': worker_color,
                'textColor': '#ffffff'
            })
            
    return jsonify(events)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)