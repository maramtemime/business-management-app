from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.secret_key = "super_secret_key_for_session" 

tasks = []

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
    
    # Process tasks and append formatting keys dynamically
    for i, t in enumerate(tasks):
        t["index"] = i
        t["time_diff"] = get_time_diff(t["date"])
        
        try:
            date_obj = datetime.strptime(t["date"], "%Y-%m-%d")
            t["date_display"] = date_obj.strftime("%d/%m/%Y")
        except ValueError:
            t["date_display"] = t["date"]

    # Filter task groups cleanly
    today_tasks = [t for t in tasks if t["date"] == today]
    pending_tasks = [t for t in tasks if not t["done"]]
    
    done_week_tasks = []
    for t in tasks:
        if t["done"]:
            try:
                task_d = datetime.strptime(t["date"], "%Y-%m-%d").date()
                if task_d >= start_week:
                    done_week_tasks.append(t)
            except ValueError:
                continue

    errors = request.args.getlist("errors")

    return render_template(
        "dashboard.html",
        today_tasks=today_tasks,
        pending_tasks=pending_tasks,
        done_week_tasks=done_week_tasks,
        today=today_display,
        errors=errors
    )

@app.route("/add_task", methods=["POST"])
def add_task():
    client_name = request.form.get("client_name", "").strip()
    phone = request.form.get("phone", "").strip()
    description = request.form.get("description", "").strip()
    tools = request.form.get("tools", "").strip()
    invoice_raw = request.form.get("invoice", "0").strip()
    date_value = request.form.get("date", "").strip()
    
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
        today_display = date.today().strftime("%d/%m/%Y")
        today = str(date.today())
        
        for i, t in enumerate(tasks):
            t["index"] = i
            t["time_diff"] = get_time_diff(t["date"])
            try:
                t["date_display"] = datetime.strptime(t["date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            except ValueError:
                t["date_display"] = t["date"]

        today_tasks = [t for t in tasks if t["date"] == today]
        pending_tasks = [t for t in tasks if not t["done"]]
        done_week_tasks = [t for t in tasks if t["done"]]
        
        return render_template(
            "dashboard.html",
            today_tasks=today_tasks,
            pending_tasks=pending_tasks,
            done_week_tasks=done_week_tasks,
            today=today_display,
            errors=errors
        )

    is_past_date = task_date_obj < date.today()

    new_task = {
        "client_name": client_name,
        "phone": phone,
        "description": description,
        "tools": tools,
        "invoice": invoice,
        "date": date_value, 
        "done": True if is_past_date else False, 
        "note": ""
    }

    tasks.append(new_task)
    return redirect(url_for("dashboard"))

@app.route("/toggle_done/<int:index>")
def toggle_done(index):
    if 0 <= index < len(tasks):
        tasks[index]["done"] = not tasks[index]["done"]
    return redirect(url_for("dashboard"))

@app.route("/update_task", methods=["POST"])
def update_task():
    try:
        index = int(request.form["index"])
        if 0 <= index < len(tasks):
            date_value = request.form["date"]
            task_date_obj = datetime.strptime(date_value, "%Y-%m-%d").date()
            
            is_done_checked = True if request.form.get("done") == "on" else False

            tasks[index]["client_name"] = request.form["client_name"]
            tasks[index]["phone"] = request.form["phone"]
            tasks[index]["description"] = request.form["description"]
            tasks[index]["tools"] = request.form["tools"]
            tasks[index]["invoice"] = float(request.form.get("invoice", 0) or 0)
            tasks[index]["date"] = date_value
            tasks[index]["note"] = request.form["note"]
            
            if not is_done_checked and task_date_obj < date.today():
                tasks[index]["done"] = True
            else:
                tasks[index]["done"] = is_done_checked
                
    except (ValueError, IndexError):
        pass 

    return redirect(url_for("dashboard"))

@app.route("/get_task/<int:index>")
def get_task(index):
    if 0 <= index < len(tasks):
        return jsonify(tasks[index])
    return jsonify({"error": "Task not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)