from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# PostgreSQL connection settings using environment variables
conn = psycopg2.connect(
    dbname=os.getenv('DB_NAME', 'queue_system'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST', 'localhost'),
    port=os.getenv('DB_PORT', '5432')
)
cur = conn.cursor()

@app.route('/queue', methods=['POST'])
def create_queue():
    try:
        data = request.json
        print(f"Received data: {data}")  # Debug logging
        
        cur.execute(
            "INSERT INTO queue (id, number, person, date, time, status) VALUES (%s, %s, %s, %s, %s, %s)",
            (data['id'], data['number'], data['person'], data['date'], data['time'], data['status'])
        )
        conn.commit()
        print("Data inserted successfully")  # Debug logging
        return jsonify({"success": True, "message": "Queue entry created"})
    except Exception as e:
        conn.rollback()  # Rollback in case of error
        print(f"Error inserting data: {e}")  # Debug logging
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/queue/<queue_id>', methods=['GET'])
def get_queue(queue_id):
    cur.execute("SELECT * FROM queue WHERE id = %s", (queue_id,))
    row = cur.fetchone()
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

# Route to test database connection
@app.route('/test-db', methods=['GET'])
def test_db():
    try:
        cur.execute('SELECT 1')
        result = cur.fetchone()
        return jsonify({'db_connected': True, 'result': result[0]})
    except Exception as e:
        return jsonify({'db_connected': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
