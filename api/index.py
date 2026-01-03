from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
from datetime import datetime, timedelta

class PrefixMiddleware:
    """Middleware to strip /api prefix from URLs for Vercel deployment."""
    def __init__(self, app, prefix='/api'):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith(self.prefix):
            environ['PATH_INFO'] = path[len(self.prefix):]
            if not environ['PATH_INFO']:
                environ['PATH_INFO'] = '/'
        return self.app(environ, start_response)

def parse_date(date_str):
    """Parse a date string into a datetime.date without external dependencies."""
    if not date_str:
        return None

    # Try ISO format first (handles 'YYYY-MM-DD' and 'YYYY-MM-DDTHH:MM:SS' variants)
    try:
        # datetime.fromisoformat accepts 'YYYY-MM-DD' and 'YYYY-MM-DDTHH:MM:SS'
        return datetime.fromisoformat(date_str).date()
    except Exception:
        pass

    # Common date formats to try
    formats = [
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M:%S',
        '%Y/%m/%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%b %d, %Y',
        '%d %b %Y'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except Exception:
            continue

    # Try to extract YYYY-MM-DD from more complex strings
    try:
        import re
        m = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
        if m:
            return datetime.strptime(m.group(1), '%Y-%m-%d').date()
    except Exception:
        pass

    # Could not parse
    return None

app = Flask(__name__)
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/api')
CORS(app)

# Database connection - Updated for Vercel/Supabase
def get_db_connection():
    try:
        # Vercel uses DATABASE_URL environment variable
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # If using DATABASE_URL (Supabase/PostgreSQL connection string)
            conn = psycopg2.connect(database_url, sslmode='require')
        else:
            # Fallback to individual environment variables
            conn = psycopg2.connect(
                database=os.environ.get('PGDATABASE'),
                user=os.environ.get('PGUSER'), 
                password=os.environ.get('PGPASSWORD'),
                host=os.environ.get('PGHOST'),
                port=os.environ.get('PGPORT', 5432),
                sslmode='require'
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

@app.route('/queue/next-number/<department>', methods=['GET'])
def get_next_queue_number(department):
    """Generate the next sequential queue number for a department"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Get current date for daily reset
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get the highest number for this department today
        cur.execute("""
            SELECT MAX(CAST(SUBSTRING(number FROM 2) AS INTEGER)) as max_num
            FROM queue 
            WHERE number LIKE %s 
            AND DATE(created_at) = %s
        """, (f"{department}%", today))
        
        result = cur.fetchone()
        max_num = result[0] if result[0] is not None else 0
        
        # Generate next number (max 999)
        next_num = max_num + 1
        if next_num > 999:
            conn.close()
            return jsonify({
                "success": False, 
                "error": f"Maximum queue numbers reached for department {department} today (999)"
            }), 400
        
        # Format as A001, B001, etc.
        queue_number = f"{department}{str(next_num).zfill(3)}"
        
        conn.close()
        return jsonify({
            "success": True,
            "queue_number": queue_number,
            "sequence": next_num,
            "department": department
        })
        
    except Exception as e:
        print(f"Error generating queue number: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

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
                called_by VARCHAR(255) DEFAULT NULL,
                is_present BOOLEAN DEFAULT FALSE,
                present_at TIMESTAMP DEFAULT NULL,
                is_muted BOOLEAN DEFAULT FALSE,
                muted_at TIMESTAMP DEFAULT NULL,
                muted_by VARCHAR(255) DEFAULT NULL
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
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS is_present BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS present_at TIMESTAMP DEFAULT NULL")
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
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS completed_time VARCHAR(50) DEFAULT NULL")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS is_present BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS present_at TIMESTAMP DEFAULT NULL")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS is_muted BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS muted_at TIMESTAMP DEFAULT NULL")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS muted_by VARCHAR(255) DEFAULT NULL")
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
        
        # Get ALL queues for this department (including completed)
        # Sort by created_at ASC for first-come-first-serve order
        cur.execute("""
            SELECT id, number, person, date, time, status, created_at, is_present, present_at, is_muted, completed_at, completed_time 
            FROM queue 
            WHERE person LIKE %s
            ORDER BY created_at ASC, id ASC
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
                "created_at": row[6].isoformat() if row[6] else None,
                "is_present": row[7] if len(row) > 7 else False,
                "present_at": row[8].isoformat() if len(row) > 8 and row[8] else None,
                "is_muted": row[9] if len(row) > 9 else False,
                "completed_at": row[10].isoformat() if len(row) > 10 and row[10] else None,
                "completed_time": row[11] if len(row) > 11 else None
            })
        
        return jsonify(queues)
    except Exception as e:
        print(f"Error in get_queue: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
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
    """Call a queue (mark as called, not completed yet)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        data = request.json
        cur = conn.cursor()
        
        # Add missing columns if they don't exist
        try:
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS called BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS called_at TIMESTAMP DEFAULT NULL")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS called_by VARCHAR(255) DEFAULT NULL")
            conn.commit()
        except Exception:
            pass
        
        # Mark queue as called (not completed yet)
        cur.execute("""
            UPDATE queue 
            SET called = TRUE, called_at = NOW(), called_by = %s, status = 'called'
            WHERE id = %s AND completed = FALSE
        """, (data.get('calledBy'), queue_id))
        
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Queue not found or already completed"}), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Queue called successfully", "status": "called"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/return-queue/<queue_id>', methods=['POST'])
def return_queue(queue_id):
    """Return a called queue back to waiting status"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        data = request.json
        cur = conn.cursor()
        
        # Add missing columns if they don't exist
        try:
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS returned_by VARCHAR(255) DEFAULT NULL")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS returned_at TIMESTAMP DEFAULT NULL")
            conn.commit()
        except Exception:
            pass
        
        # Return queue back to waiting (reset called status)
        cur.execute("""
            UPDATE queue 
            SET called = FALSE, status = 'waiting', returned_by = %s, returned_at = NOW()
            WHERE id = %s AND called = TRUE AND completed = FALSE
        """, (data.get('returnedBy'), queue_id))
        
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Queue not found, not called, or already completed"}), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Queue returned to waiting successfully", "status": "waiting"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/complete-queue/<queue_id>', methods=['POST'])
def complete_queue(queue_id):
    """Complete a queue (mark as completed after being called)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        data = request.json
        cur = conn.cursor()
        
        # Get current local time (simplified - no pytz needed)
        now = datetime.now()
        completed_time = now.strftime('%I:%M %p')
        
        # Mark queue as completed (allow from any status)
        cur.execute("""
            UPDATE queue 
            SET completed = TRUE, completed_at = NOW(), completed_by = %s, completed_time = %s, status = 'completed', called = TRUE
            WHERE id = %s
        """, (data.get('completedBy'), completed_time, queue_id))
        
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Queue not found"}), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Queue completed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/return-queue/<queue_id>', methods=['POST'])
def return_queue(queue_id):
    """Return a called queue back to waiting status"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        data = request.json
        cur = conn.cursor()
        
        # Return queue to waiting status
        cur.execute("""
            UPDATE queue 
            SET status = 'waiting', called = FALSE, called_at = NULL, called_by = NULL,
                returned_by = %s, returned_at = NOW()
            WHERE id = %s AND status = 'called'
        """, (data.get('returnedBy'), queue_id))
        
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Queue not found or not in called status"}), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Queue returned to waiting successfully"})
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
        cur.execute("SELECT number, person, created_at, called, is_present FROM queue WHERE id = %s AND completed = FALSE", (queue_id,))
        current_queue = cur.fetchone()
        
        if not current_queue:
            return jsonify({"error": "Queue not found or already completed"}), 404
            
        queue_number = current_queue[0]
        person = current_queue[1]
        created_at = current_queue[2]
        is_called = current_queue[3] if len(current_queue) > 3 else False
        is_present = current_queue[4] if len(current_queue) > 4 else False
        
        # If created_at is None, use current time as fallback
        if not created_at:
            created_at = datetime.now()
        
        # Extract department prefix from queue number (A, B, C, D, E)
        department_prefix = queue_number[0].upper() if queue_number and len(queue_number) > 0 else 'A'
        
        # Debug: Print queue information
        print(f"Debug - Queue: {queue_number}, Department: {department_prefix}, Created: {created_at}")
        
        # Debug: Show all active queues in this department
        cur.execute("""
            SELECT number, created_at, id FROM queue 
            WHERE number LIKE %s 
            AND completed = FALSE 
            ORDER BY created_at ASC
        """, (department_prefix + '%',))
        
        all_queues = cur.fetchall()
        print(f"Debug - All active queues in {department_prefix}: {all_queues}")
        print(f"Debug - Current queue ID: {queue_id}, created_at: {created_at}")
        
        # Get admin status for this department
        admin_status = get_admin_status(department_prefix)

        # Determine status based on actual conditions and admin status
        if admin_status == 'away':
            status = {
                "text": "⚪ Admin Away",
                "class": "status-away",
                "priority": "low"
            }
        elif is_called:
            status = {
                "text": "You are now being called!",
                "class": "status-called",
                "priority": "high"
            }
        else:
            status = {
                "text": "Waiting",
                "class": "status-waiting",
                "priority": "low"
            }

        conn.close()

        return jsonify({
            "status": status,
            "department_prefix": department_prefix,
            "admin_status": admin_status,
            "is_called": is_called,
            "is_present": is_present,
            "queue_number": queue_number
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/queue/im-here/<queue_id>', methods=['POST'])
def queue_im_here(queue_id):
    """Mark queue as 'I'm here' - user is present and ready"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Add missing columns if they don't exist
        try:
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS is_present BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS present_at TIMESTAMP DEFAULT NULL")
            conn.commit()
        except Exception:
            pass  # Columns might already exist
        
        # Check if queue exists and is not completed
        cur.execute("SELECT number, person FROM queue WHERE id = %s AND completed = FALSE", (queue_id,))
        queue_data = cur.fetchone()
        
        if not queue_data:
            return jsonify({"success": False, "error": "Queue not found or already completed"}), 404
        
        # Mark as present
        cur.execute("""
            UPDATE queue 
            SET is_present = TRUE, present_at = NOW() 
            WHERE id = %s
        """, (queue_id,))
        
        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "Failed to update queue"}), 400
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": "Successfully marked as present",
            "queue_number": queue_data[0]
        })
        
    except Exception as e:
        print(f"Error in im-here endpoint: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/queue/cancel-im-here/<queue_id>', methods=['POST'])
def cancel_queue_im_here(queue_id):
    """Cancel 'I'm here' status"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if queue exists and is not completed
        cur.execute("SELECT number FROM queue WHERE id = %s AND completed = FALSE", (queue_id,))
        queue_data = cur.fetchone()
        
        if not queue_data:
            return jsonify({"success": False, "error": "Queue not found or already completed"}), 404
        
        # Remove present status
        cur.execute("""
            UPDATE queue 
            SET is_present = FALSE, present_at = NULL 
            WHERE id = %s
        """, (queue_id,))
        
        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "Failed to update queue"}), 400
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": "Successfully cancelled present status",
            "queue_number": queue_data[0]
        })
        
    except Exception as e:
        print(f"Error in cancel-im-here endpoint: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/mute-queue/<queue_id>', methods=['POST'])
def mute_queue(queue_id):
    """Mute audio alerts for a specific queue"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Add missing columns if they don't exist
        try:
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS is_muted BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS muted_at TIMESTAMP DEFAULT NULL")
            cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS muted_by VARCHAR(255) DEFAULT NULL")
            conn.commit()
        except Exception:
            pass  # Columns might already exist
        
        # Check if queue exists and is called
        cur.execute("SELECT number FROM queue WHERE id = %s AND called = TRUE AND completed = FALSE", (queue_id,))
        queue_data = cur.fetchone()
        
        if not queue_data:
            return jsonify({"success": False, "error": "Queue not found, not called, or already completed"}), 404
        
        # Mark as muted
        data = request.json
        cur.execute("""
            UPDATE queue 
            SET is_muted = TRUE, muted_at = NOW(), muted_by = %s 
            WHERE id = %s
        """, (data.get('mutedBy'), queue_id))
        
        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "Failed to mute queue"}), 400
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": "Queue audio alerts muted",
            "queue_number": queue_data[0]
        })
        
    except Exception as e:
        print(f"Error in mute-queue endpoint: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/unmute-queue/<queue_id>', methods=['POST'])
def unmute_queue(queue_id):
    """Unmute audio alerts for a specific queue"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if queue exists and is called
        cur.execute("SELECT number FROM queue WHERE id = %s AND called = TRUE AND completed = FALSE", (queue_id,))
        queue_data = cur.fetchone()
        
        if not queue_data:
            return jsonify({"success": False, "error": "Queue not found, not called, or already completed"}), 404
        
        # Remove muted status
        data = request.json
        cur.execute("""
            UPDATE queue 
            SET is_muted = FALSE, muted_at = NULL, muted_by = NULL 
            WHERE id = %s
        """, (queue_id,))
        
        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "Failed to unmute queue"}), 400
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": "Queue audio alerts unmuted",
            "queue_number": queue_data[0]
        })
        
    except Exception as e:
        print(f"Error in unmute-queue endpoint: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/queue/<queue_id>/mute-status')
def get_queue_mute_status(queue_id):
    """Check if a specific queue is muted"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Get mute status for this queue
        cur.execute("SELECT is_muted, muted_at, muted_by FROM queue WHERE id = %s", (queue_id,))
        mute_data = cur.fetchone()
        conn.close()
        
        if not mute_data:
            return jsonify({"error": "Queue not found"}), 404
        
        is_muted = mute_data[0] if mute_data[0] is not None else False
        muted_at = mute_data[1]
        muted_by = mute_data[2]
        
        return jsonify({
            "is_muted": is_muted,
            "muted_at": muted_at.isoformat() if muted_at else None,
            "muted_by": muted_by
        })
        
    except Exception as e:
        print(f"Error checking queue mute status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/queue/<queue_id>/is-previous-day')
def check_if_previous_day_queue(queue_id):
    """Check if a queue is from a previous day"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Get queue creation date
        cur.execute("SELECT created_at, date FROM queue WHERE id = %s", (queue_id,))
        queue_data = cur.fetchone()
        conn.close()
        
        if not queue_data:
            return jsonify({"error": "Queue not found"}), 404
        
        created_at = queue_data[0]
        queue_date_str = queue_data[1]
        
        # Get today's date
        today = datetime.now().date()
        
        # Check if created_at is from a previous day
        if created_at:
            queue_date = created_at.date()
            is_previous_day = queue_date < today
        else:
            # Fallback to parsing the date string using the local parse_date helper
            parsed_date = parse_date(queue_date_str)
            if parsed_date:
                queue_date = parsed_date
                is_previous_day = parsed_date < today
            else:
                # If parsing fails, assume it's not from previous day
                is_previous_day = False
        
        return jsonify({
            "is_previous_day": is_previous_day,
            "queue_date": queue_date.isoformat() if 'queue_date' in locals() else queue_date_str,
            "today": today.isoformat()
        })
        
    except Exception as e:
        print(f"Error checking previous day queue: {e}")
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

@app.route('/admin/delete-all-queues', methods=['POST'])
def delete_all_queues():
    """Delete all queues from the database - DEAN ONLY"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        data = request.get_json()
        department = data.get('department')
        confirmation = data.get('confirmation')
        
        # Only dean can delete all queues
        if department != 'dean':
            return jsonify({"success": False, "error": "Unauthorized - Only Dean can delete all queues"}), 403
            
        # Require confirmation string
        if confirmation != 'DELETE_ALL_QUEUES_PERMANENTLY':
            return jsonify({"success": False, "error": "Invalid confirmation"}), 400
        
        cur = conn.cursor()
        
        # Get count before deletion
        cur.execute("SELECT COUNT(*) FROM queue")
        total_count = cur.fetchone()[0] or 0
        
        # Delete all queues
        cur.execute("DELETE FROM queue")
        deleted_count = cur.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"ADMIN ACTION: Dean deleted all queues. Total deleted: {deleted_count}")
        
        return jsonify({
            "success": True,
            "message": f"Successfully deleted all {deleted_count} queues from the database",
            "deleted_count": deleted_count,
            "total_count": total_count
        })
        
    except Exception as e:
        print(f"Error deleting all queues: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/emergency-audio', methods=['POST'])
def emergency_audio():
    """Emergency audio alert endpoint - triggers external sound player"""
    try:
        import subprocess
        import sys
        
        data = request.json
        queue_number = data.get('queue_number', 'Unknown')
        
        print(f"[ALERT] EMERGENCY AUDIO TRIGGERED FOR QUEUE {queue_number}!")
        
        # Try to run the Python emergency audio script
        try:
            # Run the emergency audio script in background
            subprocess.Popen([
                sys.executable,
                'emergency_audio.py',
                str(queue_number)
            ], cwd=os.path.dirname(os.path.abspath(__file__)))
            
            print(f"[OK] Emergency audio script launched for queue {queue_number}")
            return jsonify({
                "success": True,
                "message": f"Emergency audio triggered for queue {queue_number}"
            })
            
        except FileNotFoundError:
            print("[ERROR] emergency_audio.py not found")
            return jsonify({
                "success": False,
                "error": "Emergency audio script not found"
            }), 404
            
        except Exception as script_error:
            print(f"[ERROR] Emergency audio script error: {script_error}")
            return jsonify({
                "success": False,
                "error": f"Script execution error: {str(script_error)}"
            }), 500
            
    except Exception as e:
        print(f"[ERROR] Emergency audio endpoint error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/analytics/hourly-queue-data')
def get_hourly_queue_data():
    """Get hourly queue data for today's chart - CLEAN VERSION"""
    try:
        # Get current time
        now = datetime.now()
        current_hour = now.hour
        
        # Show from 12:00 AM to current hour + 2 hours (or at least until 8 AM)
        max_hour = max(current_hour + 2, 8)
        
        print(f"DEBUG: Current hour: {current_hour}, showing until hour: {max_hour}")
        
        # Generate time labels in 12-hour format
        labels = []
        for hour in range(0, max_hour + 1):
            time_obj = datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
            labels.append(time_obj.strftime('%I:%M %p'))
        
        print(f"DEBUG: Generated {len(labels)} labels: {labels}")
        
        # Initialize data arrays with zeros for each hour
        dean_data = [0] * (max_hour + 1)
        ie_data = [0] * (max_hour + 1)
        cpe_data = [0] * (max_hour + 1)
        
        # Try to connect to database and get real data
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                today = now.strftime('%Y-%m-%d')
                
                print(f"DEBUG: Fetching data for {today}")
                
                # Get real data from database for each hour (only up to current hour)
                for hour in range(0, min(current_hour + 1, max_hour + 1)):
                    # Count Dean's office queues for this hour
                    cur.execute("""
                        SELECT COUNT(*) FROM queue 
                        WHERE (person LIKE %s OR person LIKE %s)
                        AND DATE(created_at) = %s 
                        AND EXTRACT(HOUR FROM created_at) = %s
                    """, ('%Dean%', '%dean%', today, hour))
                    dean_count = cur.fetchone()[0] or 0
                    dean_data[hour] = dean_count
                    
                    # Count IE department queues for this hour
                    cur.execute("""
                        SELECT COUNT(*) FROM queue 
                        WHERE (person LIKE %s OR person LIKE %s)
                        AND DATE(created_at) = %s 
                        AND EXTRACT(HOUR FROM created_at) = %s
                    """, ('%IE%', '%ie%', today, hour))
                    ie_count = cur.fetchone()[0] or 0
                    ie_data[hour] = ie_count
                    
                    # Count CPE department queues for this hour
                    cur.execute("""
                        SELECT COUNT(*) FROM queue 
                        WHERE (person LIKE %s OR person LIKE %s)
                        AND DATE(created_at) = %s 
                        AND EXTRACT(HOUR FROM created_at) = %s
                    """, ('%CPE%', '%cpe%', today, hour))
                    cpe_count = cur.fetchone()[0] or 0
                    cpe_data[hour] = cpe_count
                    
                    print(f"DEBUG: Hour {hour:02d}:00 - Dean: {dean_count}, IE: {ie_count}, CPE: {cpe_count}")
                
                conn.close()
                print("DEBUG: Using REAL database data")
                
            except Exception as db_error:
                print(f"Database error: {db_error}")
                # Use realistic fallback data if database error
                if current_hour >= 6:
                    dean_data[6] = 1
                    ie_data[6] = 2
                if current_hour >= 7:
                    dean_data[7] = 2
                    ie_data[7] = 3
                    cpe_data[7] = 1
                if current_hour >= 8:
                    dean_data[8] = 1
                    ie_data[8] = 2
                conn.close()
        
        # Create datasets
        datasets = [
            {
                'label': "Dean's Office",
                'data': dean_data,
                'borderColor': '#ef4444',
                'backgroundColor': 'transparent',
                'fill': False,
                'tension': 0.1,
                'borderWidth': 2,
                'pointRadius': 0,
                'pointHoverRadius': 0
            },
            {
                'label': 'IE Department',
                'data': ie_data,
                'borderColor': '#3b82f6',
                'backgroundColor': 'transparent',
                'fill': False,
                'tension': 0.1,
                'borderWidth': 2,
                'pointRadius': 0,
                'pointHoverRadius': 0
            },
            {
                'label': 'CPE Department',
                'data': cpe_data,
                'borderColor': '#10b981',
                'backgroundColor': 'transparent',
                'fill': False,
                'tension': 0.1,
                'borderWidth': 2,
                'pointRadius': 0,
                'pointHoverRadius': 0
            }
        ]
        
        response_data = {
            'labels': labels,
            'datasets': datasets
        }
        
        print(f"DEBUG: Returning data with {len(labels)} labels and {len(datasets)} datasets")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"ERROR in hourly-queue-data: {e}")
        # Emergency fallback
        return jsonify({
            'labels': ['12:00 AM', '01:00 AM', '02:00 AM', '03:00 AM', '04:00 AM', '05:00 AM', '06:00 AM', '07:00 AM'],
            'datasets': [
                {
                    'label': "Dean's Office",
                    'data': [0, 0, 0, 0, 0, 0, 0, 0],
                    'borderColor': '#ef4444',
                    'backgroundColor': 'transparent',
                    'fill': False,
                    'tension': 0.1,
                    'borderWidth': 2,
                    'pointRadius': 0,
                    'pointHoverRadius': 0
                }
            ]
        })

@app.route('/analytics/hourly-department-data')
def get_hourly_department_data():
    """Get real hourly queue data for each department from the database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'error': 'Database connection failed'
            }), 500
        
        cur = conn.cursor()
        
        # Get today's date
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Initialize result structure
        result = {
            'dean': {'hourlyData': [0] * 24, 'totalToday': 0},
            'ie': {'hourlyData': [0] * 24, 'totalToday': 0},
            'cpe': {'hourlyData': [0] * 24, 'totalToday': 0},
            'ece': {'hourlyData': [0] * 24, 'totalToday': 0},
            'others': {'hourlyData': [0] * 24, 'totalToday': 0}
        }
        
        # Department mapping
        department_map = {
            'A': 'dean',
            'B': 'ie', 
            'C': 'cpe',
            'D': 'ece',
            'E': 'others'
        }
        
        # Query to get hourly queue data for today
        cur.execute("""
            SELECT 
                SUBSTRING(number FROM 1 FOR 1) as dept_prefix,
                EXTRACT(HOUR FROM created_at) as hour,
                COUNT(*) as queue_count
            FROM queue 
            WHERE DATE(created_at) = %s
            GROUP BY SUBSTRING(number FROM 1 FOR 1), EXTRACT(HOUR FROM created_at)
            ORDER BY dept_prefix, hour
        """, (today,))
        
        hourly_data = cur.fetchall()
        
        # Process hourly data
        for row in hourly_data:
            dept_prefix = row[0]
            hour = int(row[1]) if row[1] is not None else 0
            count = row[2]
            
            dept_key = department_map.get(dept_prefix)
            if dept_key and 0 <= hour < 24:
                result[dept_key]['hourlyData'][hour] = count
        
        # Get total counts for each department today
        cur.execute("""
            SELECT 
                SUBSTRING(number FROM 1 FOR 1) as dept_prefix,
                COUNT(*) as total_count
            FROM queue 
            WHERE DATE(created_at) = %s
            GROUP BY SUBSTRING(number FROM 1 FOR 1)
        """, (today,))
        
        total_data = cur.fetchall()
        
        # Process total data
        for row in total_data:
            dept_prefix = row[0]
            total_count = row[1]
            
            dept_key = department_map.get(dept_prefix)
            if dept_key:
                result[dept_key]['totalToday'] = total_count
        
        conn.close()
        
        print(f"DEBUG: Hourly department data: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"ERROR in hourly-department-data: {e}")
        # Return empty data structure on error
        return jsonify({
            'dean': {'hourlyData': [0] * 24, 'totalToday': 0},
            'ie': {'hourlyData': [0] * 24, 'totalToday': 0},
            'cpe': {'hourlyData': [0] * 24, 'totalToday': 0},
            'ece': {'hourlyData': [0] * 24, 'totalToday': 0},
            'others': {'hourlyData': [0] * 24, 'totalToday': 0}
        })

# For Vercel Serverless deployment - export the Flask app
# The app variable is automatically used by Vercel's Python runtime

# Uncomment below for local development only:
# if __name__ == '__main__':
#     port = int(os.environ.get('PORT', 5000))
#     print("[START] Starting Queue Management System API...")
#     print(f"[INFO] Server running on port: {port}")
#     app.run(host='0.0.0.0', port=port, debug=False)

@app.route('/home')
def home_page():
    return app.send_static_file('home.html')

@app.route('/queue-number')
def queue_number_page():
    return app.send_static_file('queue-number.html')

@app.route('/queue-status')
def queue_status_page():
    return app.send_static_file('queue-status.html')

@app.route('/admin')
def admin_login_page():
    return app.send_static_file('admin-login.html')

@app.route('/admin-dashboard')
def admin_dashboard_page():
    return app.send_static_file('admin-dashboard.html')