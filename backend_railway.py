from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os

app = Flask(__name__)
CORS(app)

# Database connection
def get_db_connection():
    try:
        conn = psycopg2.connect(
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER'), 
            password=os.environ.get('PGPASSWORD'),
            host=os.environ.get('PGHOST'),
            port=os.environ.get('PGPORT', 5432)
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

@app.route('/')
def home():
    return jsonify({
        "message": "Queue Management System API is running!",
        "status": "active",
        "endpoints": {
            "POST /queue": "Create new queue entry",
            "GET /queue/<id>": "Get queue entry by ID",
            "GET /test-db": "Test database connection"
        }
    })

@app.route('/test-db')
def test_db():
    conn = get_db_connection()
    if not conn:
        return jsonify({"db_connected": False, "error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        cur.execute('SELECT 1')
        result = cur.fetchone()
        conn.close()
        return jsonify({"db_connected": True, "result": result[0]})
    except Exception as e:
        return jsonify({"db_connected": False, "error": str(e)}), 500

@app.route('/queue', methods=['POST'])
def create_queue():
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    
    try:
        data = request.json
        cur = conn.cursor()
        
        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id VARCHAR(255) PRIMARY KEY,
                number VARCHAR(50),
                person VARCHAR(255),
                date VARCHAR(100),
                time VARCHAR(50),
                status VARCHAR(50)
            )
        """)
        
        # Insert data
        cur.execute(
            "INSERT INTO queue (id, number, person, date, time, status) VALUES (%s, %s, %s, %s, %s, %s)",
            (data['id'], data['number'], data['person'], data['date'], data['time'], data.get('status', 'waiting'))
        )
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Queue entry created"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/queue/<queue_id>')
def get_queue(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM queue WHERE id = %s", (queue_id,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            return jsonify({
                "id": row[0],
                "number": row[1],
                "person": row[2],
                "date": row[3],
                "time": row[4],
                "status": row[5]
            })
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Starting Queue Management System API...")
    print(f"📡 Server running on port: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
