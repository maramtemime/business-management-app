from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from sqlalchemy import or_ 
import json
import calendar
import colorsys

app = Flask(__name__)
app.secret_key = "super_secret_key_for_session" 

# --- DATABASE CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class Task(db.Model):
    __tablename__ = 'task'

    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    direction = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=False)
    tools = db.Column(db.Text, nullable=True)
    invoice = db.Column(db.Float, default=0.0)
    
    date = db.Column(db.Date, nullable=False, default=date.today)
    
    done = db.Column(db.Boolean, default=False)
    canceled = db.Column(db.Boolean, default=False)
    note = db.Column(db.Text, nullable=True)

    worker_logs = db.relationship('WorkerTaskLog', backref='task', lazy=True, cascade="all, delete-orphan")

    @property
    def assigned_workers(self):
        return [log.worker for log in self.worker_logs if log.worker]

class Worker(db.Model):
    __tablename__ = 'worker'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone_num = db.Column(db.String(20), nullable=False)
    pay_per_normal_hr = db.Column(db.Float, default=0.0) # Stores 'Prix / Jour' or 'Prix / H Normale'
    pay_per_extra_hr = db.Column(db.Float, default=0.0)  # Stores 'Prix / H Extra'
    
    pay_type = db.Column(db.String(10), default='hourly')  # 'hourly' or 'daily'
    hours_per_day = db.Column(db.Float, nullable=True)     # Required if pay_type == 'daily'
    
    color = db.Column(db.String(20), nullable=True)
    _activities = db.Column('activities', db.Text, default='{}')

    task_logs = db.relationship('WorkerTaskLog', backref='worker', lazy=True, cascade="all, delete-orphan")
    payments = db.relationship('WorkerPayment', backref='worker', lazy=True, cascade="all, delete-orphan")

    @property
    def effective_normal_rate(self):
        """Returns the actual rate per hour based on pay_type."""
        if self.pay_type == 'daily' and self.hours_per_day and self.hours_per_day > 0:
            return self.pay_per_normal_hr / self.hours_per_day
        return self.pay_per_normal_hr

    @property
    def assigned_color(self):
        if self.color:
            return self.color

        palette = ['#dc3545', '#198754', '#6f42c1', '#fd7e14', '#0d6efd', '#20c997', '#d63384']
        if self.id and self.id <= len(palette):
            return palette[self.id - 1]

        hue = (self.id * 137.508) % 360
        rgb = colorsys.hls_to_rgb(hue / 360.0, 0.45, 0.65)
        return f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"

    @property
    def activities(self):
        try:
            return json.loads(self._activities) if self._activities else {}
        except Exception:
            return {}

    @activities.setter
    def activities(self, value):
        self._activities = json.dumps(value)

    @property
    def total_pay(self):
        """Calculates gross total earnings dynamically using applied rates."""
        gross = sum(
            (log.normal_hours * log.applied_normal_rate) + 
            (log.extra_hours * log.applied_extra_rate)
            for log in self.task_logs
        )
        return round(gross, 2)

    def get_logs_for_day(self, day_name):
        french_days = {
            'Lundi': 0, 'Mardi': 1, 'Mercredi': 2, 
            'Jeudi': 3, 'Vendredi': 4, 'Samedi': 5, 'Dimanche': 6
        }
        
        target_weekday = french_days.get(day_name)
        if target_weekday is None:
            return []

        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        matched_logs = []
        for log in self.task_logs:
            if log.task and log.task.canceled:
                continue

            if log.date and start_of_week <= log.date <= end_of_week and log.date.weekday() == target_weekday:
                matched_logs.append(log)
                
        return matched_logs

class WorkerTaskLog(db.Model):
    __tablename__ = 'worker_task_log'

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

    date = db.Column(db.Date, nullable=False, default=date.today)

    normal_hours = db.Column(db.Float, default=0.0)
    extra_hours = db.Column(db.Float, default=0.0)
    is_updated = db.Column(db.Boolean, default=False)

    applied_normal_rate = db.Column(db.Float, nullable=False, default=0.0)
    applied_extra_rate = db.Column(db.Float, nullable=False, default=0.0)

class WorkerPayment(db.Model):
    __tablename__ = 'worker_payment'
    
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text, nullable=True)

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    vendor = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Expense {self.title} - {self.amount} DT>'

class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    color = db.Column(db.String(20), nullable=False, default="#6c757d")

# --- ROUTES ---
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
    today_date = date.today()
    today_display = today_date.strftime("%d/%m/%Y")
    
    start_week = today_date - timedelta(days=today_date.weekday())
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
        t.time_diff = (t.date - today_date).days if t.date else 0
        t.date_display = t.date.strftime("%d/%m/%Y") if t.date else ""

    today_tasks = [t for t in active_tasks if t.date == today_date]
    pending_tasks = [t for t in active_tasks if not t.done]
    done_week_tasks = [t for t in active_tasks if t.done and t.date and t.date >= start_week]

    errors = request.args.getlist("errors")

    return render_template(
        "dashboard.html",
        today_tasks=today_tasks,
        pending_tasks=pending_tasks,
        done_week_tasks=done_week_tasks,
        count_today=len(today_tasks),
        count_pending=len(pending_tasks),
        count_done=len(done_week_tasks),
        today=today_display,
        week_range=week_range_string,
        errors=errors,
        all_workers=Worker.query.all()
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

    new_task = Task(
        client_name=client_name,
        phone=phone,
        direction=direction,
        description=description,
        tools=tools,
        invoice=invoice,
        date=task_date_obj,
        done=(task_date_obj < date.today()), 
        note=note
    )

    try:
        db.session.add(new_task)
        db.session.flush()

        for worker_identifier in selected_workers:
            if worker_identifier.isdigit():
                worker = Worker.query.get(int(worker_identifier))
            else:
                worker = Worker.query.filter_by(full_name=worker_identifier).first()

            if worker:
                log = WorkerTaskLog(
                    worker_id=worker.id,
                    task_id=new_task.id,
                    date=task_date_obj,
                    normal_hours=float(request.form.get(f"norm_hrs_{worker.id}", 0.0)),
                    extra_hours=float(request.form.get(f"extra_hrs_{worker.id}", 0.0)),
                    applied_normal_rate=worker.effective_normal_rate,
                    applied_extra_rate=worker.pay_per_extra_hr,
                    is_updated=False
                )
                db.session.add(log)

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
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

            task.client_name = request.form.get("client_name", "").strip()
            task.phone = request.form.get("phone", "").strip()
            task.direction = request.form.get("direction", "").strip()
            task.description = request.form.get("description", "").strip()
            task.tools = request.form.get("tools", "").strip()
            
            try:
                task.invoice = float(request.form.get("invoice", 0) or 0)
            except ValueError:
                task.invoice = 0.0

            task.date = task_date_obj
            task.note = request.form.get("note", "").strip()
            task.done = (request.form.get("done") == "on")

            selected_workers = request.form.getlist("workers")
            existing_logs = WorkerTaskLog.query.filter_by(task_id=task.id).all()
            existing_worker_ids = {log.worker_id: log for log in existing_logs}
            current_assigned_ids = set()

            for worker_identifier in selected_workers:
                if worker_identifier.isdigit():
                    worker = Worker.query.get(int(worker_identifier))
                else:
                    worker = Worker.query.filter_by(full_name=worker_identifier).first()

                if worker:
                    current_assigned_ids.add(worker.id)
                    if worker.id not in existing_worker_ids:
                        new_log = WorkerTaskLog(
                            worker_id=worker.id,
                            task_id=task.id,
                            date=task_date_obj,
                            normal_hours=0.0,
                            extra_hours=0.0,
                            applied_normal_rate=worker.effective_normal_rate,
                            applied_extra_rate=worker.pay_per_extra_hr,
                            is_updated=False
                        )
                        db.session.add(new_log)
                    else:
                        existing_worker_ids[worker.id].date = task_date_obj

            # Safely handle unassigned workers: preserve logs if work hours were already logged
            for worker_id, log in existing_worker_ids.items():
                if worker_id not in current_assigned_ids:
                    if log.normal_hours == 0.0 and log.extra_hours == 0.0:
                        db.session.delete(log)

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
            "date": task.date.strftime("%Y-%m-%d") if task.date else "",
            "done": task.done,
            "note": task.note,
            "workers": [w.full_name for w in task.assigned_workers]
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
    
    try:
        query_date = datetime.strptime(date_val, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"count": 0, "tasks": []})

    tasks = Task.query.filter_by(date=query_date, canceled=False).all()
    
    task_list = [{
        "id": t.id,
        "client_name": t.client_name,
        "phone": t.phone,
        "direction": t.direction or "---",
        "description": t.description,
        "tools": t.tools or "---",
        "invoice": t.invoice,
        "done": t.done,
        "note": t.note or "Aucune note."
    } for t in tasks]

    return jsonify({"count": len(task_list), "tasks": task_list})

@app.route('/archive')
def archive():
    archived_tasks = Task.query.filter(
        or_(Task.done == True, Task.canceled == True)
    ).order_by(Task.date.desc()).all()
    
    return render_template(
        'archive.html',
        tasks=archived_tasks,
        total_completed=Task.query.filter_by(done=True, canceled=False).count(),
        total_canceled=Task.query.filter_by(canceled=True).count()
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
        pay_type = request.form.get('pay_type', 'hourly').strip()
        
        try:
            pay_per_normal_hr = float(request.form.get('pay_per_normal_hr', 0))
            pay_per_extra_hr = float(request.form.get('pay_per_extra_hr', 0))
            
            # Parse hours_per_day if daily option is chosen
            hours_per_day_raw = request.form.get('hours_per_day')
            hours_per_day = float(hours_per_day_raw) if hours_per_day_raw and pay_type == 'daily' else None
        except ValueError:
            pay_per_normal_hr = 0.0
            pay_per_extra_hr = 0.0
            hours_per_day = None
        
        new_worker = Worker(
            full_name=full_name,
            phone_num=phone_num,
            pay_per_normal_hr=pay_per_normal_hr,
            pay_per_extra_hr=pay_per_extra_hr,
            pay_type=pay_type,
            hours_per_day=hours_per_day
        )
        db.session.add(new_worker)
        db.session.commit()
        return redirect(url_for('travailleurs'))
        
    travailleurs = Worker.query.all()
    days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

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
                    "date": log.task.date.strftime("%Y-%m-%d") if log.task.date else "",
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

# app.py -> update_worker_hours()

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

    # Fix: Always sync the applied rates with the worker's current default rates when saving
    if log.worker:
        log.applied_normal_rate = log.worker.effective_normal_rate
        log.applied_extra_rate = log.worker.pay_per_extra_hr

    log.normal_hours = norm
    log.extra_hours = extra
    log.is_updated = True 

    db.session.commit()
    return jsonify({"success": True})

@app.route("/api/archive_events")
def get_archive_events():
    archived_tasks = Task.query.filter(
        or_(Task.done == True, Task.canceled == True)
    ).all()
    
    events = []
    for task in archived_tasks:
        events.append({
            "id": task.id,
            "title": task.client_name,
            "start": task.date.strftime("%Y-%m-%d") if task.date else "",
            "display": "list-item",
            "color": "#dc3545" if task.canceled else "#198754",
            "extendedProps": {
                "status": "canceled" if task.canceled else "completed"
            }
        })
    return jsonify(events)

@app.route('/get_worker/<int:worker_id>', methods=['GET'])
def get_worker(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    return jsonify({
        'id': worker.id,
        'full_name': worker.full_name,
        'phone_num': worker.phone_num or '',
        'pay_per_normal_hr': worker.pay_per_normal_hr,
        'pay_per_extra_hr': worker.pay_per_extra_hr,
        'pay_type': worker.pay_type or 'hourly',
        'hours_per_day': worker.hours_per_day or '',
        'color': worker.assigned_color
    })

@app.route('/update_worker', methods=['POST'])
def update_worker():
    worker_id = request.form.get('worker_id')
    worker = Worker.query.get_or_404(worker_id)
    
    worker.full_name = request.form.get('full_name', '').strip()
    worker.phone_num = request.form.get('phone_num', '').strip()
    worker.pay_type = request.form.get('pay_type', 'hourly').strip()
    
    try:
        # Accepts both field key conventions safely
        new_norm = float(request.form.get('hourly_rate') or request.form.get('pay_per_normal_hr') or 0)
        new_extra = float(request.form.get('overtime_rate') or request.form.get('pay_per_extra_hr') or 0)
        
        hours_per_day_raw = request.form.get('hours_per_day')
        worker.hours_per_day = float(hours_per_day_raw) if hours_per_day_raw and worker.pay_type == 'daily' else None
        
        worker.pay_per_normal_hr = new_norm
        worker.pay_per_extra_hr = new_extra

        # Apply worker's effective hourly rate to all task logs
        effective_rate = worker.effective_normal_rate
        for log in worker.task_logs:
            log.applied_normal_rate = effective_rate
            log.applied_extra_rate = new_extra

    except ValueError:
        pass

    manual_color = request.form.get('color', '').strip()
    if manual_color:
        worker.color = manual_color

    db.session.commit()
    return redirect(url_for('travailleurs'))

@app.route('/pay_worker', methods=['POST'])
def pay_worker():
    worker_id = request.form.get('worker_id')
    
    try:
        amount = float(request.form.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Montant invalide'}), 400
    
    if amount <= 0:
        return jsonify({'success': False, 'error': 'Montant invalide'}), 400
        
    worker = Worker.query.get_or_404(worker_id)
    
    # Parse payment date if provided by form; default to today
    payment_date_str = request.form.get('date', '').strip()
    try:
        payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d").date() if payment_date_str else date.today()
    except ValueError:
        payment_date = date.today()

    notes = request.form.get('notes', '').strip()

    payment = WorkerPayment(
        worker_id=worker.id,
        amount=amount,
        date=payment_date,
        notes=notes if notes else None
    )
    
    db.session.add(payment)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/worker_events/<int:worker_id>')
def get_worker_events(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    logs = WorkerTaskLog.query.filter_by(worker_id=worker_id).all()
    payments = WorkerPayment.query.filter_by(worker_id=worker_id).all()
    
    events = []
    for log in logs:
        if log.task and log.task.canceled:
            continue

        events.append({
            'id': f"log_{log.id}",
            'title': f"{log.normal_hours}h Norm / {log.extra_hours}h Extra",
            'start': log.date.strftime("%Y-%m-%d") if log.date else "",
            'color': worker.assigned_color,
            'textColor': '#ffffff'
        })
        
    for pay in payments:
        events.append({
            'id': f"pay_{pay.id}",
            'title': f"★ Payé: {pay.amount} DT",
            'start': pay.date.strftime("%Y-%m-%d") if pay.date else "",
            'color': worker.assigned_color,
            'textColor': '#ffffff'
        })
        
    return jsonify(events)

@app.route('/api/all_worker_events')
def get_all_worker_events():
    all_workers = Worker.query.order_by(Worker.id).all()
    events = []
    
    for worker in all_workers:
        for log in worker.task_logs:
            if log.task and log.task.canceled:
                continue

            events.append({
                'id': f"log_{log.id}",
                'title': f"{worker.full_name}: {log.normal_hours}h Norm / {log.extra_hours}h Extra",
                'start': log.date.strftime("%Y-%m-%d") if log.date else "",
                'color': worker.assigned_color,
                'textColor': '#ffffff'
            })
            
        for pay in worker.payments:
            events.append({
                'id': f"pay_{pay.id}",
                'title': f"★ {worker.full_name} Payé: {pay.amount} DT",
                'start': pay.date.strftime("%Y-%m-%d") if pay.date else "",
                'color': worker.assigned_color,
                'textColor': '#ffffff'
            })
            
    return jsonify(events)

@app.route('/api/payment_details/<int:payment_id>')
def get_payment_details(payment_id):
    payment = WorkerPayment.query.get_or_404(payment_id)
    worker = payment.worker

    subsequent_payments = WorkerPayment.query.filter(
        WorkerPayment.worker_id == worker.id,
        WorkerPayment.id > payment.id
    ).all()
    sum_subsequent = sum(p.amount for p in subsequent_payments)

    total_paid_all_time = sum(p.amount for p in worker.payments)
    current_remaining = worker.total_pay - total_paid_all_time
    
    remaining_after_payment = current_remaining + sum_subsequent
    amount_before_paying = remaining_after_payment + payment.amount

    return jsonify({
        "worker_name": worker.full_name,
        "payment_date": payment.date.strftime("%d/%m/%Y") if payment.date else "",
        "amount_paid": payment.amount,
        "amount_before_paying": round(amount_before_paying, 2),
        "remaining_after_payment": round(remaining_after_payment, 2),
        "notes": payment.notes or "Aucune note."  # Added notes field
    })

@app.route('/api/work_log_details/<int:log_id>')
def get_work_log_details(log_id):
    log = WorkerTaskLog.query.get_or_404(log_id)
    worker = log.worker
    task = log.task

    normal_pay = log.normal_hours * log.applied_normal_rate
    extra_pay = log.extra_hours * log.applied_extra_rate
    total_log_pay = normal_pay + extra_pay

    return jsonify({
        "worker_name": worker.full_name,
        "date": log.date.strftime("%d/%m/%Y") if log.date else "",
        "client_name": task.client_name if task else "Non spécifié",
        "task_description": task.description if task else "Aucune description",
        "normal_hours": log.normal_hours,
        "extra_hours": log.extra_hours,
        "applied_normal_rate": log.applied_normal_rate,
        "applied_extra_rate": log.applied_extra_rate,
        "total_earnings": round(total_log_pay, 2)
    })

@app.route('/api/update_payment_note', methods=['POST'])
def update_payment_note():
    payment_id = request.form.get('payment_id')
    notes = request.form.get('notes', '').strip()
    
    payment = WorkerPayment.query.get(payment_id)
    if not payment:
        return jsonify({"success": False, "error": "Paiement introuvable."}), 404

    payment.notes = notes if notes else None
    db.session.commit()
    
    return jsonify({"success": True})

@app.route('/depenses', methods=['GET', 'POST'])
def depenses():
    # Pre-populate default categories if none exist
    default_categories = [
        {'name': 'Matériaux', 'color': '#0d6efd'},
        {'name': 'Transport', 'color': '#fd7e14'},
        {'name': 'Outillage', 'color': '#198754'},
        {'name': 'Carburant', 'color': '#dc3545'},
        {'name': 'Autre', 'color': '#6c757d'}
    ]
    if Category.query.count() == 0:
        for cat in default_categories:
            db.session.add(Category(name=cat['name'], color=cat['color']))
        db.session.commit()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        amount_raw = request.form.get('amount', '0').strip()
        vendor = request.form.get('vendor', '').strip()
        date_str = request.form.get('date', '').strip()
        notes = request.form.get('notes', '').strip()

        try:
            amount = float(amount_raw)
        except ValueError:
            amount = 0.0

        try:
            expense_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        except ValueError:
            expense_date = date.today()

        if title and amount > 0:
            new_expense = Expense(
                title=title,
                category=category,
                amount=amount,
                vendor=vendor,
                date=expense_date,
                notes=notes if notes else None
            )
            db.session.add(new_expense)
            db.session.commit()
            return redirect(url_for('depenses'))

    categories = Category.query.all()
    categories_dict = {cat.name: cat.color for cat in categories}
    expenses = Expense.query.order_by(Expense.date.desc()).all()

    return render_template(
        'depenses.html', 
        expenses=expenses, 
        categories=categories, 
        categories_dict=categories_dict
    )

@app.route('/add_category', methods=['POST'])
def add_category():
    name = request.form.get('category_name', '').strip()
    color = request.form.get('category_color', '#0d6efd').strip()

    if name:
        existing = Category.query.filter_by(name=name).first()
        if not existing:
            new_cat = Category(name=name, color=color)
            db.session.add(new_cat)
            db.session.commit()

    return redirect(url_for('depenses'))

@app.route('/delete_category/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    
    # Optionally: update existing expenses under this category to 'Autre'
    Expense.query.filter_by(category=category.name).update({'category': 'Autre'})
    
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for('depenses'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)