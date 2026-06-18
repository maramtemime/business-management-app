from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form["password"]

        if password == "1234":
            return "Welcome, Mohamed!"
        else:
            return "Wrong password"

    return render_template("login.html")

if __name__ == "__main__":
    app.run(debug=True)