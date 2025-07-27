from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
from datetime import datetime, timedelta

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
            "GET /queue/<id>": "Get queue entry by ID (marks as accessed)",
            "GET /queue/<id>/accessed": "Check if queue has been accessed",
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
                status VARCHAR(50),
                accessed BOOLEAN DEFAULT FALSE,
                accessed_at TIMESTAMP DEFAULT NULL,
                completed BOOLEAN DEFAULT FALSE,
                completed_at TIMESTAMP DEFAULT NULL,
                completed_by VARCHAR(255) DEFAULT NULL,
                priority BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
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
        
        # First, try to add the new columns if they don't exist (for backward compatibility)
        try:
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS accessed BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS accessed_at TIMESTAMP DEFAULT NULL")
            conn.commit()
        except Exception as alter_error:
            # Columns might already exist, continue
            pass
        
        # Mark as accessed when someone visits the queue status page
        try:
            cur.execute(
                "UPDATE queue SET accessed = TRUE, accessed_at = NOW() WHERE id = %s",
                (queue_id,)
            )
            conn.commit()
        except Exception as update_error:
            # If update fails, just continue with the select
            print(f"Warning: Could not update accessed status: {update_error}")
        
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

@app.route('/queue/<queue_id>/accessed')
def check_queue_accessed(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Try to select with new columns, fallback if they don't exist
        try:
            cur.execute("SELECT accessed, accessed_at FROM queue WHERE id = %s", (queue_id,))
            row = cur.fetchone()
            conn.close()
            
            if row:
                return jsonify({
                    "accessed": row[0] if row[0] is not None else False,
                    "accessed_at": row[1].isoformat() if row[1] else None
                })
        except Exception as select_error:
            # Columns might not exist, return default values
            cur.execute("SELECT id FROM queue WHERE id = %s", (queue_id,))
            row = cur.fetchone()
            conn.close()
            
            if row:
                return jsonify({
                    "accessed": False,
                    "accessed_at": None
                })
        
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Admin endpoints
@app.route('/admin/queue/<department>')
def get_admin_queue(department):
    """Get current queue for a specific department"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Add missing columns if they don't exist
        try:
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS completed BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP DEFAULT NULL")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS completed_by VARCHAR(255) DEFAULT NULL")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS priority BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")
            conn.commit()
        except Exception:
            pass
        
        # Map department to person filter
        person_filters = {
            'dean': '%Dean%',
            'ie-chair': '%IE%',
            'cpe-chair': '%CPE%',
            'ece-chair': '%ECE%',
            'others': '%Other%'
        }
        
        person_filter = person_filters.get(department, '%')
        
        # Get current queue (not completed) for this department, ordered by priority and creation time
        cur.execute("""
            SELECT id, number, person, date, time, status, priority, created_at 
            FROM queue 
            WHERE person LIKE %s AND (completed IS NULL OR completed = FALSE)
            ORDER BY priority DESC, created_at ASC
        """, (person_filter,))
        
        rows = cur.fetchall()
        conn.close()
        
        queues = []
        for row in rows:
            queues.append({
                "id": row[0],
                "number": row[1],
                "person": row[2],
                "date": row[3],
                "time": row[4],
                "status": row[5],
                "priority": row[6] if row[6] is not None else False,
                "created_at": row[7].isoformat() if row[7] else None
            })
        
        return jsonify(queues)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/stats/<department>')
def get_admin_stats(department):
    """Get statistics for a specific department"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Map department to person filter
        person_filters = {
            'dean': '%Dean%',
            'ie-chair': '%IE%',
            'cpe-chair': '%CPE%',
            'ece-chair': '%ECE%',
            'others': '%Other%'
        }
        
        person_filter = person_filters.get(department, '%')
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Total queues today
        cur.execute("""
            SELECT COUNT(*) FROM queue 
            WHERE person LIKE %s AND DATE(created_at) = %s
        """, (person_filter, today))
        total_today = cur.fetchone()[0] or 0
        
        # Current queue count
        cur.execute("""
            SELECT COUNT(*) FROM queue 
            WHERE person LIKE %s AND (completed IS NULL OR completed = FALSE)
        """, (person_filter,))
        current_queue = cur.fetchone()[0] or 0
        
        # Completed today
        cur.execute("""
            SELECT COUNT(*) FROM queue 
            WHERE person LIKE %s AND completed = TRUE AND DATE(completed_at) = %s
        """, (person_filter, today))
        completed_today = cur.fetchone()[0] or 0
        
        # Average wait time (simplified calculation)
        avg_wait_time = max(current_queue * 5, 5)  # 5 minutes per queue
        
        conn.close()
        
        return jsonify({
            "totalToday": total_today,
            "currentQueue": current_queue,
            "completedToday": completed_today,
            "avgWaitTime": avg_wait_time
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/call-queue/<queue_id>', methods=['POST'])
def call_queue(queue_id):
    """Call a queue (mark as completed)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        data = request.json
        cur = conn.cursor()
        
        # Mark queue as completed
        cur.execute("""
            UPDATE queue 
            SET completed = TRUE, completed_at = NOW(), completed_by = %s, status = 'completed'
            WHERE id = %s
        """, (data.get('calledBy'), queue_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Queue called and completed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/priority/<queue_id>', methods=['POST'])
def set_priority(queue_id):
    """Set queue as priority"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Toggle priority
        cur.execute("UPDATE queue SET priority = NOT COALESCE(priority, FALSE) WHERE id = %s", (queue_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Priority updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/activity/<department>')
def get_recent_activity(department):
    """Get recent completed queues for a department"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Map department to person filter
        person_filters = {
            'dean': '%Dean%',
            'ie-chair': '%IE%',
            'cpe-chair': '%CPE%',
            'ece-chair': '%ECE%',
            'others': '%Other%'
        }
        
        person_filter = person_filters.get(department, '%')
        
        # Get recent completed queues
        cur.execute("""
            SELECT number, person, completed_at 
            FROM queue 
            WHERE person LIKE %s AND completed = TRUE 
            ORDER BY completed_at DESC 
            LIMIT 10
        """, (person_filter,))
        
        rows = cur.fetchall()
        conn.close()
        
        activities = []
        for row in rows:
            activities.append({
                "number": row[0],
                "person": row[1],
                "completedAt": row[2].strftime('%Y-%m-%d %H:%M') if row[2] else None
            })
        
        return jsonify(activities)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Starting Queue Management System API...")
    print(f"📡 Server running on port: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
