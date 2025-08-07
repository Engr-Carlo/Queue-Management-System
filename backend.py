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
                present_at TIMESTAMP DEFAULT NULL
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
        
        # Get current queue (not completed) for this department, ordered by creation time
        cur.execute("""
            SELECT id, number, person, date, time, status, created_at, is_present, present_at, is_muted 
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
                "created_at": row[6].isoformat() if row[6] else None,
                "is_present": row[7] if len(row) > 7 else False,
                "present_at": row[8].isoformat() if len(row) > 8 and row[8] else None,
                "is_muted": row[9] if len(row) > 9 else False
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
        
        # Mark queue as completed
        cur.execute("""
            UPDATE queue 
            SET completed = TRUE, completed_at = NOW(), completed_by = %s, status = 'completed'
            WHERE id = %s AND called = TRUE
        """, (data.get('completedBy'), queue_id))
        
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Queue not found, not called yet, or already completed"}), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Queue completed successfully"})
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
                "text": "🔴 You are now being called!",
                "class": "status-called",
                "priority": "high"
            }
        else:
            status = {
                "text": "🟡 Waiting",
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
            # Fallback to parsing the date string
            try:
                # Parse various date formats
                from dateutil import parser
                parsed_date = parser.parse(queue_date_str).date()
                is_previous_day = parsed_date < today
            except:
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
        
        print(f"🚨 EMERGENCY AUDIO TRIGGERED FOR QUEUE {queue_number}! 🚨")
        
        # Try to run the Python emergency audio script
        try:
            # Run the emergency audio script in background
            subprocess.Popen([
                sys.executable,
                'emergency_audio.py',
                str(queue_number)
            ], cwd=os.path.dirname(os.path.abspath(__file__)))
            
            print(f"✅ Emergency audio script launched for queue {queue_number}")
            return jsonify({
                "success": True,
                "message": f"Emergency audio triggered for queue {queue_number}"
            })
            
        except FileNotFoundError:
            print("❌ emergency_audio.py not found")
            return jsonify({
                "success": False,
                "error": "Emergency audio script not found"
            }), 404
            
        except Exception as script_error:
            print(f"❌ Emergency audio script error: {script_error}")
            return jsonify({
                "success": False,
                "error": f"Script execution error: {str(script_error)}"
            }), 500
            
    except Exception as e:
        print(f"❌ Emergency audio endpoint error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Starting Queue Management System API...")
    print(f"📡 Server running on port: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)