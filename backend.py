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
                created_at TIMESTAMP DEFAULT NOW(),
                called BOOLEAN DEFAULT FALSE,
                called_at TIMESTAMP DEFAULT NULL,
                called_by VARCHAR(255) DEFAULT NULL
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
        
        # Get current queue (not completed) for this department, ordered by creation time
        cur.execute("""
            SELECT id, number, person, date, time, status, created_at 
            FROM queue 
            WHERE person LIKE %s AND (completed IS NULL OR completed = FALSE)
            ORDER BY created_at ASC
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
                "created_at": row[6].isoformat() if row[6] else None
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

@app.route('/queue/<queue_id>/status')
def get_queue_status(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Get the current queue details
        cur.execute("SELECT number, person, created_at, called FROM queue WHERE id = %s", (queue_id,))
        current_queue = cur.fetchone()
        
        if not current_queue:
            return jsonify({"error": "Queue not found"}), 404
            
        queue_number = current_queue[0]
        person = current_queue[1]
        created_at = current_queue[2]
        is_called = current_queue[3] if len(current_queue) > 3 else False
        
        # Extract department prefix from queue number (A, B, C, D, E)
        department_prefix = queue_number[0] if queue_number else 'A'
        
        # Count queues ahead of this one in the same department (not completed and created before this one)
        cur.execute("""
            SELECT COUNT(*) FROM queue 
            WHERE number LIKE %s 
            AND completed = FALSE 
            AND created_at < %s
            ORDER BY created_at ASC
        """, (department_prefix + '%', created_at))
        
        position_result = cur.fetchone()
        position = position_result[0] if position_result else 0
        
        # Count total active queues in department
        cur.execute("""
            SELECT COUNT(*) FROM queue 
            WHERE number LIKE %s 
            AND completed = FALSE
        """, (department_prefix + '%',))
        
        total_result = cur.fetchone()
        total_in_department = total_result[0] if total_result else 1
        
        # Get admin status for this department
        admin_status = get_admin_status(department_prefix)
        
        # Calculate estimated time based on position (5 minutes per position)
        if admin_status == 'away':
            estimated_minutes = 999  # Unknown time when admin is away
        elif position <= 0:
            estimated_minutes = 0  # They're being called now
        else:
            # 5 minutes per position ahead
            base_time = position * 5
            if admin_status == 'busy':
                estimated_minutes = base_time + 5  # Add 5 minutes when busy
            else:  # available
                estimated_minutes = base_time
        
        # Determine status based on actual conditions and admin status
        if admin_status == 'away':
            status = {
                "text": "⚪ Admin Away",
                "class": "status-away",
                "priority": "low"
            }
        elif is_called:
            status = {
                "text": "🔴 You are now being called!",
                "class": "status-called",
                "priority": "high"
            }
        elif position <= 0:
            status = {
                "text": "🟢 You're Next!",
                "class": "status-next",
                "priority": "high"
            }
        elif position <= 2:
            status = {
                "text": "🟢 Ready Soon",
                "class": "status-ready",
                "priority": "medium"
            }
        elif position <= 5:
            status = {
                "text": "🟡 Waiting",
                "class": "status-waiting",
                "priority": "low"
            }
        else:
            status = {
                "text": "⚪ In Queue",
                "class": "status-queued",
                "priority": "low"
            }
            
        conn.close()
        
        return jsonify({
            "position": position + 1,  # 1-based position
            "total_in_department": total_in_department,
            "estimated_minutes": estimated_minutes,
            "status": status,
            "department_prefix": department_prefix,
            "admin_status": admin_status,
            "is_called": is_called,
            "created_at": created_at.isoformat() if created_at else None,
            "queue_number": queue_number
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Admin status management
admin_statuses = {}  # In-memory storage for admin statuses

def get_admin_status(department):
    """Get admin status for a department"""
    status = admin_statuses.get(department, 'available')
    return status

@app.route('/admin/status', methods=['POST'])
def set_admin_status():
    """Set admin status for a department"""
    try:
        data = request.get_json()
        department = data.get('department')
        status = data.get('status')  # 'available', 'busy', 'away'
        
        if not department or status not in ['available', 'busy', 'away']:
            return jsonify({"success": False, "error": "Invalid department or status"}), 400
            
        # Map department to department prefix
        department_mapping = {
            'dean': 'A',
            'ie-chair': 'B',
            'cpe-chair': 'C',
            'ece-chair': 'D',
            'others': 'E'
        }
        
        department_prefix = department_mapping.get(department)
        if not department_prefix:
            return jsonify({"success": False, "error": "Invalid department"}), 400
            
        admin_statuses[department_prefix] = status
        
        return jsonify({
            "success": True,
            "department": department_prefix,
            "status": status
        })
        
    except Exception as e:
        print(f"Error setting admin status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/status/<department>', methods=['GET'])
def get_admin_status_endpoint(department):
    """Get admin status for a department"""
    try:
        status = admin_statuses.get(department.upper(), 'available')
        return jsonify({
            "success": True,
            "department": department.upper(),
            "status": status
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Starting Queue Management System API...")
    print(f"📡 Server running on port: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
