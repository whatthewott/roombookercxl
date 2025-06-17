
from flask import Flask, render_template, request, redirect, url_for
import psycopg2
import os

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route("/")
def index():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM bookings ORDER BY date")
    bookings = cur.fetchall()
    conn.close()
    return render_template("index.html", bookings=bookings)

@app.route("/book", methods=["GET", "POST"])
def book():
    if request.method == "POST":
        date = request.form["date"]
        building = request.form["building"]
        room = request.form["room"]
        employer = request.form["employer"]
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM rooms WHERE building=%s AND room_number=%s", (building, room))
        if not cur.fetchone():
            conn.close()
            return "Room not found", 400

        cur.execute("SELECT * FROM bookings WHERE date=%s AND building=%s AND room_number=%s",
                    (date, building, room))
        if cur.fetchone():
            conn.close()
            return "Room already booked", 409

        cur.execute("INSERT INTO bookings (date, building, room_number, employer) VALUES (%s, %s, %s, %s)",
                    (date, building, room, employer))
        conn.commit()
        conn.close()
        return redirect(url_for("index"))
    return render_template("book.html")

@app.route("/edit/<int:booking_id>", methods=["GET", "POST"])
def edit(booking_id):
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        date = request.form["date"]
        building = request.form["building"]
        room = request.form["room"]
        employer = request.form["employer"]
        cur.execute("UPDATE bookings SET date=%s, building=%s, room_number=%s, employer=%s WHERE booking_id=%s",
                    (date, building, room, employer, booking_id))
        conn.commit()
        conn.close()
        return redirect(url_for("index"))
    cur.execute("SELECT * FROM bookings WHERE booking_id=%s", (booking_id,))
    booking = cur.fetchone()
    conn.close()
    return render_template("edit.html", booking=booking)

@app.route("/delete/<int:booking_id>")
def delete(booking_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM bookings WHERE booking_id=%s", (booking_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
