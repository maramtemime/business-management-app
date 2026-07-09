from app import app, db

with app.app_context():
    try:
        db.session.execute(db.text("ALTER TABLE task ADD COLUMN canceled BOOLEAN DEFAULT 0"))
        db.session.commit()
        print(" Successfully added 'canceled' column to the database!")
    except Exception as e:
        print(f"Notice: {e}")