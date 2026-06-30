from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, date, timedelta

app = Flask(__name__)

tasks = []

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form["password"]

        if password == "1234":
            return redirect(url_for("dashboard"))
        else:
            return "Wrong password"

    return render_template("login.html")

def get_time_diff(task_date):
    """Return difference in days between task date and today"""
    task_date = datetime.strptime(task_date, "%Y-%m-%d").date()
    today = date.today()
    return (task_date - today).days

@app.route("/dashboard")
def dashboard():
    today = str(date.today())

    start_week = date.today() - timedelta(days=date.today().weekday())
    
    for i, t in enumerate(tasks):
        t["index"] = i
        t["time_diff"] = get_time_diff(t["date"])

    today_tasks = [t for t in tasks if t["date"] == today]
    pending_tasks = [t for t in tasks if not t["done"]]
    done_week_tasks = [
        t for t in tasks
        if t["done"] and datetime.strptime(t["date"], "%Y-%m-%d").date() >= start_week
    ]

    return render_template(
        "dashboard.html",
        today_tasks=today_tasks,
        pending_tasks=pending_tasks,
        done_week_tasks=done_week_tasks,
        today=today
    )

@app.route("/add_task", methods=["POST"])
def add_task():
    new_task = {
            "client_name": request.form["client_name"],
            "phone": request.form["phone"],
            "description": request.form["description"],
            "tools": request.form["tools"],
            "invoice": float(request.form["invoice"]),
            "date": request.form["date"],
            "done": False,
            "time_diff": 0
        }

    tasks.append(new_task)

    return redirect(url_for("dashboard"))

@app.route("/toggle_done/<int:index>")
def toggle_done(index):
    if 0 <= index < len(tasks):
        tasks[index]["done"] = not tasks[index]["done"]

    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True)