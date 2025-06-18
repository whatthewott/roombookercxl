from datetime import date 
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify
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
    cur.execute("""
        SELECT bookings.*, rooms.confirmed
        FROM bookings
        JOIN rooms ON bookings.building = rooms.building AND bookings.room_number = rooms.room_number
        ORDER BY bookings.date, bookings.start_time
    """)
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

@app.route("/toggle_confirm/<string:building>/<string:room_number>", methods=["POST"])
def toggle_confirm(building, room_number):
    conn = get_db()
    cur = conn.cursor()

    # Get current confirmed status (as string)
    cur.execute("SELECT confirmed FROM rooms WHERE building = %s AND room_number = %s", (building, room_number))
    result = cur.fetchone()
    if not result:
        conn.close()
        return jsonify({"error": "Room not found"}), 404

    current_status = result[0].lower() if result[0] else "false"
    new_status = "false" if current_status in ["true", "t", "yes", "1"] else "true"

    # Update to new status (as string)
    cur.execute("UPDATE rooms SET confirmed = %s WHERE building = %s AND room_number = %s",
                (new_status, building, room_number))
    conn.commit()
    conn.close()

    return jsonify({"confirmed": new_status})

@app.route("/search", methods=["GET", "POST"])
def search():
    conn = get_db()
    cur = conn.cursor()

    # Get list of buildings for dropdown
    cur.execute("SELECT DISTINCT building FROM rooms ORDER BY building")
    buildings = [row[0] for row in cur.fetchall()]

    rooms = []
    if request.method == "POST":
        room_number = request.form.get("room_number", "").strip()
        building = request.form.get("building", "")
        date = request.form.get("date", "")
        start_time = request.form.get("start_time", "")
        end_time = request.form.get("end_time", "")

        # Build SQL query dynamically based on filters
        query = "SELECT * FROM rooms WHERE 1=1"
        params = []

        if building:
            query += " AND building = %s"
            params.append(building)
        if room_number:
            query += " AND room_number ILIKE %s"
            params.append(f"%{room_number}%")

        if date and start_time and end_time:
            # Exclude rooms that have bookings overlapping with given datetime
            query += """
                AND room_number NOT IN (
                    SELECT room_number FROM bookings
                    WHERE date = %s
                    AND (
                        (%s < end_time AND %s > start_time)
                    )
                )
            """
            params.extend([date, start_time, end_time])

        query += " ORDER BY building, room_number"

        cur.execute(query, params)
        rooms = cur.fetchall()

    conn.close()
    return render_template("search.html", buildings=buildings, rooms=rooms)

@app.route("/room/<string:building>/<string:room_number>")
def view_room(building, room_number):
    conn = get_db()
    cur = conn.cursor()

    # Get room details
    cur.execute("SELECT * FROM rooms WHERE building = %s AND room_number = %s", (building, room_number))
    room = cur.fetchone()

    if not room:
        conn.close()
        return "Room not found", 404

    # Get future bookings for this room
    cur.execute("""
        SELECT date, start_time, end_time, employer, event_type
        FROM bookings
        WHERE building = %s AND room_number = %s AND date >= %s::date
        ORDER BY date, start_time
    """, (building, room_number, date.today()))
    future_bookings = cur.fetchall()

    conn.close()
    return render_template("room.html", room=room, future_bookings=future_bookings)

if __name__ == "__main__":
    app.run(debug=True)
