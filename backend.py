from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# PostgreSQL connection settings using Railway's environment variables
try:
    conn = psycopg2.connect(
        dbname=os.getenv('PGDATABASE', 'railway'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD'),
        host=os.getenv('PGHOST', 'localhost'),
        port=os.getenv('PGPORT', '5432')
    )
    cur = conn.cursor()
    print("✅ Database connected successfully!")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    conn = None
    cur = None

@app.route('/', methods=['GET'])
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

@app.route('/queue', methods=['POST'])
def create_queue():
    if not conn:
        return jsonify({"success": False, "error": "Database not connected"}), 500
    
    try:
        data = request.json
        print(f"Received data: {data}")
        
        cur.execute(
            "INSERT INTO queue (id, number, person, date, time, status) VALUES (%s, %s, %s, %s, %s, %s)",
            (data['id'], data['number'], data['person'], data['date'], data['time'], data['status'])
        )
        conn.commit()
        print("Data inserted successfully")
        return jsonify({"success": True, "message": "Queue entry created"})
    except Exception as e:
        conn.rollback()
        print(f"Error inserting data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/queue/<queue_id>', methods=['GET'])
def get_queue(queue_id):
    if not conn:
        return jsonify({"success": False, "error": "Database not connected"}), 500
    
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
    if not conn:
        return jsonify({"success": False, "error": "Database not connected"}), 500
    
    try:
        cur.execute('SELECT 1')
        result = cur.fetchone()
        return jsonify({'db_connected': True, 'result': result[0]})
    except Exception as e:
        return jsonify({'db_connected': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Railway provides PORT env variable
    print("Starting Flask server...")
    print(f"Server will be accessible at:")
    print(f"- Local: http://localhost:{port}")
    print(f"- Railway: Will be provided after deployment")
    print("Make sure environment variables are set...")
    
    try:
        app.run(host='0.0.0.0', port=port, debug=False)  # debug=False for production
    except Exception as e:
        print(f"Failed to start server: {e}")
        input("Press Enter to continue...")
