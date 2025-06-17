
from flask import Flask, render_template, request, redirect, url_for, abort
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
    cur.execute("SELECT * FROM bookings ORDER BY date, start_time")
    bookings = cur.fetchall()
    conn.close()
    return render_template("index.html", bookings=bookings)

@app.route("/book", methods=["GET", "POST"])
def book():
    if request.method == "POST":
        date = request.form["date"]
        building = request.form["building"]
        room = request.form["room_number"]
        employer = request.form["employer"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        event_type = request.form["event_type"]

        # Validate inputs
        conn = get_db()
        cur = conn.cursor()

        # check if the room exists
        cur.execute("SELECT * FROM rooms WHERE building=%s AND room_number=%s", (building, room))
        if not cur.fetchone():
            conn.close()
            return "Room not found", 400

        # Check for overlapping bookings
        cur.execute("""
            SELECT * FROM bookings
            WHERE building = %s AND room_number = %s AND date = %s
            AND (
                (%s < end_time AND %s > start_time)  -- Overlap check
            )
        """, (building, room, date, start_time, end_time))

        # If there's an overlapping booking, return an error
        if cur.fetchone():
            conn.close()
            return "This room is already booked at that date and time.", 409

        # If no overlap, insert the new booking
        cur.execute("""
            INSERT INTO bookings (date, building, room_number, employer, event_type, start_time, end_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (date, building, room, employer, event_type, start_time, end_time))

        conn.commit()
        conn.close()
        return redirect(url_for("index"))
    
    # GET request: fetch buildings for dropdown
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT building FROM rooms ORDER BY building")
    buildings = [row[0] for row in cur.fetchall()]
    conn.close()

    return render_template("book.html", buildings=buildings)

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

@app.route("/delete/<int:booking_id>", methods=['POST'])
def delete(booking_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM bookings WHERE booking_id=%s", (booking_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/admin/sql", methods=["GET", "POST"])
def run_sql():
    # Optional: Simple passcode check (change "secret123" to something secure)
    if request.method == "POST":
        passcode = request.form.get("passcode")
        if passcode != "secret123":
            abort(403)

        query = request.form.get("query")
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(query)
            conn.commit()
            conn.close()
            return "Query executed successfully!"
        except Exception as e:
            return f"Error: {str(e)}", 500

    # Render a simple HTML form
    return '''
        <form method="post">
            Passcode: <input type="password" name="passcode"><br>
            SQL Query:<br>
            <textarea name="query" rows="5" cols="80"></textarea><br>
            <button type="submit">Run</button>
        </form>
    '''

if __name__ == "__main__":
    app.run(debug=True)
