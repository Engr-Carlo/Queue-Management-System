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
    dbname=os.getenv('PGDATABASE', os.getenv('DB_NAME', 'queue_system')),
    user=os.getenv('PGUSER', os.getenv('DB_USER', 'postgres')),
    password=os.getenv('PGPASSWORD', os.getenv('DB_PASSWORD')),
    host=os.getenv('PGHOST', os.getenv('DB_HOST', 'localhost')),
    port=os.getenv('PGPORT', os.getenv('DB_PORT', '5432'))
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
