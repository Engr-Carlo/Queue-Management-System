from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
import hashlib
import hmac
import secrets
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
    """Parse a date string into a datetime.date."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).date()
    except Exception:
        pass
    formats = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d',
               '%m/%d/%Y', '%d/%m/%Y', '%b %d, %Y', '%d %b %Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except Exception:
            continue
    import re
    m = re.search(r'(\d{4}-\d{2}-\d{2})', date_str or '')
    if m:
        try:
            return datetime.strptime(m.group(1), '%Y-%m-%d').date()
        except Exception:
            pass
    return None


# --- Password hashing (PBKDF2-HMAC-SHA256, no bcrypt dependency) ---

def hash_password(password):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(password, stored_hash):
    """Verify password against PBKDF2 hash. Also supports legacy plain-text."""
    if '$' not in stored_hash:
        return hmac.compare_digest(password, stored_hash)
    salt, hash_hex = stored_hash.split('$', 1)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000)
    return hmac.compare_digest(dk.hex(), hash_hex)


# =================================================================
# Flask App
# =================================================================

app = Flask(__name__)
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/api')
CORS(app)


def get_db_connection():
    try:
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Strip channel_binding param — not supported by all psycopg2 builds
            import re as _re
            database_url = _re.sub(r'[&?]channel_binding=[^&]*', '', database_url)
            conn = psycopg2.connect(database_url)
        else:
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


# Legacy person-filter map (kept only for backward-compatible endpoints)
LEGACY_PERSON_FILTERS = {
    'dean': '%Dean%', 'ie-chair': '%IE%', 'cpe-chair': '%CPE%',
    'ece-chair': '%ECE%', 'others': '%Other%'
}
LEGACY_DEPT_MAPPING = {
    'dean': 'A', 'ie-chair': 'B', 'cpe-chair': 'C', 'ece-chair': 'D', 'others': 'E'
}

# In-memory admin status (prefix -> 'available' | 'busy' | 'away')
admin_statuses = {}


# =================================================================
# SCHEMA
# =================================================================

def init_schema(conn):
    """Create all tables if they don't exist."""
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS institutions (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            type VARCHAR(50) NOT NULL DEFAULT 'other',
            logo_url TEXT,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            settings JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id SERIAL PRIMARY KEY,
            institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            prefix CHAR(1) NOT NULL,
            description TEXT,
            icon VARCHAR(50) DEFAULT 'fa-concierge-bell',
            is_active BOOLEAN DEFAULT TRUE,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(institution_id, prefix)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            institution_id INTEGER REFERENCES institutions(id) ON DELETE CASCADE,
            username VARCHAR(100) NOT NULL,
            password VARCHAR(512) NOT NULL,
            name VARCHAR(255) NOT NULL,
            role VARCHAR(30) NOT NULL DEFAULT 'service-admin',
            service_id INTEGER REFERENCES services(id) ON DELETE SET NULL,
            icon VARCHAR(50) DEFAULT 'fa-user',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS queue (
            id VARCHAR(255) PRIMARY KEY,
            institution_id INTEGER REFERENCES institutions(id) ON DELETE CASCADE,
            service_id INTEGER REFERENCES services(id) ON DELETE CASCADE,
            number VARCHAR(50),
            person VARCHAR(255),
            date VARCHAR(100),
            time VARCHAR(50),
            status VARCHAR(50) DEFAULT 'waiting',
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
            muted_by VARCHAR(255) DEFAULT NULL,
            returned_by VARCHAR(255) DEFAULT NULL,
            returned_at TIMESTAMP DEFAULT NULL
        )
    """)

    # === MIGRATION: add new columns to existing tables from old single-tenant schema ===
    # users table
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS institution_id INTEGER")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(100)")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(30) NOT NULL DEFAULT 'service-admin'")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS service_id INTEGER")
    # Populate username from legacy department column only when migrating the old schema
    cur.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'department'
            ) THEN
                UPDATE users
                SET username = department
                WHERE username IS NULL AND department IS NOT NULL;
            END IF;
        END $$;
    """)
    # Fix roles for known legacy users
    cur.execute("UPDATE users SET role = 'super-admin' WHERE username = 'super-admin' AND role = 'service-admin'")
    cur.execute("UPDATE users SET role = 'institution-admin' WHERE username = 'dean' AND role = 'service-admin'")
    # queue table
    cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS institution_id INTEGER")
    cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS service_id INTEGER")
    cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS returned_by VARCHAR(255) DEFAULT NULL")
    cur.execute("ALTER TABLE queue ADD COLUMN IF NOT EXISTS returned_at TIMESTAMP DEFAULT NULL")

    # Unique per institution (NULL institution_id = super-admin, only one)
    cur.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'institution_id'
            ) AND EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'username'
            ) AND NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_inst_username'
            ) THEN
                ALTER TABLE users ADD CONSTRAINT uq_users_inst_username UNIQUE (institution_id, username);
            END IF;
        END $$;
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_queue_institution ON queue(institution_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_queue_service ON queue(service_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(institution_id, status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_queue_date ON queue(institution_id, created_at)")

    conn.commit()


def seed_default_data(conn):
    """Seed the default PNC College of Engineering institution and users.
    Safe to call on both fresh DBs and DBs migrated from the old single-tenant schema.
    """
    cur = conn.cursor()

    # Get or create the default institution
    cur.execute("SELECT id FROM institutions WHERE slug = 'pnc-engineering'")
    row = cur.fetchone()
    if row:
        inst_id = row[0]
    else:
        cur.execute("""
            INSERT INTO institutions (name, slug, type, description, is_active)
            VALUES (%s, %s, %s, %s, TRUE) RETURNING id
        """, (
            'PNC College of Engineering',
            'pnc-engineering',
            'university',
            'Palawan National College - College of Engineering Queue Management'
        ))
        inst_id = cur.fetchone()[0]

    # Create services for the default institution
    services = [
        (inst_id, "Dean's Office", 'A', 'Dean - College of Engineering', 'fa-user-tie', 1),
        (inst_id, 'IE Department', 'B', 'Industrial Engineering Department Chair', 'fa-industry', 2),
        (inst_id, 'CPE Department', 'C', 'Computer Engineering Department Chair', 'fa-microchip', 3),
        (inst_id, 'ECE Department', 'D', 'Electronics Engineering Department Chair', 'fa-bolt', 4),
        (inst_id, 'Other Staff', 'E', 'Other Staff/Faculty', 'fa-users', 5),
    ]
    svc_ids = {}
    for s in services:
        cur.execute("""
            INSERT INTO services (institution_id, name, prefix, description, icon, display_order)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (institution_id, prefix) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """, s)
        svc_ids[s[2]] = cur.fetchone()[0]

    # Link any existing legacy users (institution_id IS NULL, not super-admin) to this institution
    cur.execute("""
        UPDATE users SET institution_id = %s
        WHERE institution_id IS NULL AND username IS NOT NULL AND username != 'super-admin'
    """, (inst_id,))

    # Assign service_ids to legacy service admins
    legacy_prefix_map = {'A': 'dean', 'B': 'ie-chair', 'C': 'cpe-chair', 'D': 'ece-chair', 'E': 'others'}
    for prefix, uname in legacy_prefix_map.items():
        cur.execute(
            "UPDATE users SET service_id = %s WHERE username = %s AND institution_id = %s AND service_id IS NULL",
            (svc_ids[prefix], uname, inst_id)
        )

    # Fix dean to institution-admin role
    cur.execute("""
        UPDATE users SET role = 'institution-admin'
        WHERE username = 'dean' AND institution_id = %s AND role = 'service-admin'
    """, (inst_id,))

    # Super-admin: update role if legacy row exists, otherwise create
    cur.execute("SELECT id FROM users WHERE username = 'super-admin' AND institution_id IS NULL")
    if cur.fetchone():
        cur.execute("UPDATE users SET role = 'super-admin' WHERE username = 'super-admin' AND institution_id IS NULL")
    else:
        cur.execute("""
            INSERT INTO users (institution_id, username, password, name, role, icon)
            VALUES (NULL, %s, %s, %s, 'super-admin', %s)
        """, ('super-admin', hash_password('admin2026'), 'Super Admin - System Administrator', 'fa-crown'))

    # Create any missing institution users (fresh DB case) with ON CONFLICT DO NOTHING
    new_users = [
        (inst_id, 'dean', hash_password('dean2025'), 'Dean - College of Engineering', 'institution-admin', 'fa-user-tie', svc_ids['A']),
        (inst_id, 'ie-chair', hash_password('ie2025'), 'IE Department Chair', 'service-admin', 'fa-industry', svc_ids['B']),
        (inst_id, 'cpe-chair', hash_password('cpe2025'), 'CPE Department Chair', 'service-admin', 'fa-microchip', svc_ids['C']),
        (inst_id, 'ece-chair', hash_password('ece2025'), 'ECE Department Chair', 'service-admin', 'fa-bolt', svc_ids['D']),
        (inst_id, 'others', hash_password('staff2025'), 'Other Staff/Faculty', 'service-admin', 'fa-users', svc_ids['E']),
    ]
    for u in new_users:
        cur.execute("""
            INSERT INTO users (institution_id, username, password, name, role, icon, service_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, u)

    conn.commit()
    print("Default institution and users seeded.")


def ensure_schema(conn):
    """Idempotent helper — safe to call on every request."""
    init_schema(conn)
    seed_default_data(conn)


# =================================================================
# ROOT / HEALTH
# =================================================================

@app.route('/')
def root():
    return jsonify({
        "message": "Queue Management System API is running!",
        "status": "active",
        "version": "2.0 - Multi-Tenant"
    })


@app.route('/test-db')
def test_db():
    conn = get_db_connection()
    if not conn:
        return jsonify({"db_connected": False, "error": "Connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute('SELECT 1')
        r = cur.fetchone()
        conn.close()
        return jsonify({"db_connected": True, "result": r[0]})
    except Exception as e:
        return jsonify({"db_connected": False, "error": str(e)}), 500


@app.route('/init-schema', methods=['POST'])
def init_schema_endpoint():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        ensure_schema(conn)
        conn.close()
        return jsonify({"success": True, "message": "Schema initialized"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =================================================================
# INSTITUTIONS
# =================================================================

@app.route('/institutions', methods=['GET'])
def list_institutions():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        ensure_schema(conn)
        show_all = request.args.get('all', 'false') == 'true'
        if show_all:
            cur.execute("SELECT id, name, slug, type, logo_url, description, is_active, created_at FROM institutions ORDER BY name")
        else:
            cur.execute("SELECT id, name, slug, type, logo_url, description, is_active, created_at FROM institutions WHERE is_active = TRUE ORDER BY name")
        rows = cur.fetchall()
        conn.close()
        return jsonify([{
            "id": r[0], "name": r[1], "slug": r[2], "type": r[3],
            "logo_url": r[4], "description": r[5], "is_active": r[6],
            "created_at": r[7].isoformat() if r[7] else None
        } for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/institutions', methods=['POST'])
def create_institution():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        data = request.json
        name = data.get('name', '').strip()
        slug = data.get('slug', '').strip().lower()
        inst_type = data.get('type', 'other')
        logo_url = data.get('logo_url', '')
        description = data.get('description', '')

        if not name or not slug:
            return jsonify({"success": False, "error": "Name and slug are required"}), 400

        import re
        if not re.match(r'^[a-z0-9\-]+$', slug):
            return jsonify({"success": False, "error": "Slug must contain only lowercase letters, numbers, and hyphens"}), 400

        cur = conn.cursor()
        ensure_schema(conn)
        cur.execute("""
            INSERT INTO institutions (name, slug, type, logo_url, description)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (name, slug, inst_type, logo_url, description))
        inst_id = cur.fetchone()[0]
        conn.commit()
        conn.close()
        return jsonify({"success": True, "id": inst_id, "message": f"Institution '{name}' created"})
    except psycopg2.errors.UniqueViolation:
        return jsonify({"success": False, "error": "An institution with this slug already exists"}), 409
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/institutions/<int:inst_id>', methods=['GET'])
def get_institution(inst_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, slug, type, logo_url, description, is_active, settings, created_at FROM institutions WHERE id = %s", (inst_id,))
        r = cur.fetchone()
        conn.close()
        if not r:
            return jsonify({"error": "Institution not found"}), 404
        return jsonify({
            "id": r[0], "name": r[1], "slug": r[2], "type": r[3],
            "logo_url": r[4], "description": r[5], "is_active": r[6],
            "settings": r[7], "created_at": r[8].isoformat() if r[8] else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/institutions/<int:inst_id>', methods=['PUT'])
def update_institution(inst_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        data = request.json
        cur = conn.cursor()
        allowed = ['name', 'type', 'logo_url', 'description', 'is_active']
        fields, values = [], []
        for k in allowed:
            if k in data:
                fields.append(f"{k} = %s")
                values.append(data[k])
        if not fields:
            return jsonify({"success": False, "error": "No fields to update"}), 400
        values.append(inst_id)
        cur.execute(f"UPDATE institutions SET {', '.join(fields)} WHERE id = %s", values)
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Institution not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Institution updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/institutions/<int:inst_id>', methods=['DELETE'])
def delete_institution(inst_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("UPDATE institutions SET is_active = FALSE WHERE id = %s", (inst_id,))
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Institution not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Institution deactivated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =================================================================
# SERVICES
# =================================================================

@app.route('/institutions/<int:inst_id>/services', methods=['GET'])
def list_services(inst_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        ensure_schema(conn)
        cur.execute("""
            SELECT id, name, prefix, description, icon, is_active, display_order
            FROM services WHERE institution_id = %s AND is_active = TRUE
            ORDER BY display_order, prefix
        """, (inst_id,))
        rows = cur.fetchall()
        conn.close()
        return jsonify([{
            "id": r[0], "name": r[1], "prefix": r[2].strip(), "description": r[3],
            "icon": r[4], "is_active": r[5], "display_order": r[6]
        } for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/institutions/<int:inst_id>/services', methods=['POST'])
def create_service(inst_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        data = request.json
        name = data.get('name', '').strip()
        prefix = data.get('prefix', '').strip().upper()
        description = data.get('description', '')
        icon = data.get('icon', 'fa-concierge-bell')
        display_order = data.get('display_order', 0)

        if not name or not prefix or len(prefix) != 1 or not prefix.isalpha():
            return jsonify({"success": False, "error": "Name and a single-letter prefix (A-Z) are required"}), 400

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO services (institution_id, name, prefix, description, icon, display_order)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (inst_id, name, prefix, description, icon, display_order))
        sid = cur.fetchone()[0]
        conn.commit()
        conn.close()
        return jsonify({"success": True, "id": sid, "message": f"Service '{name}' created"})
    except psycopg2.errors.UniqueViolation:
        return jsonify({"success": False, "error": f"Prefix '{prefix}' already used in this institution"}), 409
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/services/<int:service_id>', methods=['PUT'])
def update_service(service_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        data = request.json
        cur = conn.cursor()
        allowed = ['name', 'description', 'icon', 'is_active', 'display_order']
        fields, values = [], []
        for k in allowed:
            if k in data:
                fields.append(f"{k} = %s")
                values.append(data[k])
        if not fields:
            return jsonify({"success": False, "error": "No fields to update"}), 400
        values.append(service_id)
        cur.execute(f"UPDATE services SET {', '.join(fields)} WHERE id = %s", values)
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Service not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Service updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/services/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("UPDATE services SET is_active = FALSE WHERE id = %s", (service_id,))
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Service not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Service deactivated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =================================================================
# USER / ADMIN MANAGEMENT
# =================================================================

@app.route('/institutions/<int:inst_id>/admins', methods=['GET'])
def list_admins(inst_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.username, u.name, u.role, u.icon, u.service_id, s.name
            FROM users u LEFT JOIN services s ON u.service_id = s.id
            WHERE u.institution_id = %s ORDER BY u.role, u.username
        """, (inst_id,))
        rows = cur.fetchall()
        conn.close()
        return jsonify({"success": True, "admins": [{
            "id": r[0], "username": r[1], "name": r[2], "role": r[3],
            "icon": r[4], "service_id": r[5], "service_name": r[6]
        } for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/institutions/<int:inst_id>/admins', methods=['POST'])
def create_admin(inst_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        role = data.get('role', 'service-admin')
        icon = data.get('icon', 'fa-user')
        service_id = data.get('service_id')

        if not username or not password or not name:
            return jsonify({"success": False, "error": "Username, password, and name are required"}), 400
        if role not in ('institution-admin', 'service-admin'):
            return jsonify({"success": False, "error": "Role must be 'institution-admin' or 'service-admin'"}), 400

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (institution_id, username, password, name, role, icon, service_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (inst_id, username, hash_password(password), name, role, icon, service_id))
        uid = cur.fetchone()[0]
        conn.commit()
        conn.close()
        return jsonify({"success": True, "id": uid, "message": f"Admin '{username}' created"})
    except psycopg2.errors.UniqueViolation:
        return jsonify({"success": False, "error": f"Username '{username}' already exists in this institution"}), 409
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admins/<int:user_id>', methods=['DELETE'])
def delete_admin(user_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "User not found"}), 404
        if row[0] == 'super-admin':
            conn.close()
            return jsonify({"success": False, "error": "Cannot delete super-admin"}), 403
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Admin deleted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =================================================================
# AUTHENTICATION
# =================================================================

@app.route('/auth/login', methods=['POST'])
def login():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        data = request.json
        institution_id = data.get('institution_id')
        username = data.get('username') or data.get('department', '')
        password = data.get('password', '')

        if not username or not password:
            return jsonify({"success": False, "error": "Username and password required"}), 400

        cur = conn.cursor()
        ensure_schema(conn)

        if institution_id:
            cur.execute("""
                SELECT u.id, u.username, u.password, u.name, u.role, u.icon,
                       u.institution_id, u.service_id,
                       i.name, i.slug
                FROM users u LEFT JOIN institutions i ON u.institution_id = i.id
                WHERE u.institution_id = %s AND u.username = %s
            """, (institution_id, username))
        else:
            # Super-admin or legacy login
            cur.execute("""
                SELECT u.id, u.username, u.password, u.name, u.role, u.icon,
                       u.institution_id, u.service_id,
                       i.name, i.slug
                FROM users u LEFT JOIN institutions i ON u.institution_id = i.id
                WHERE u.username = %s
            """, (username,))

        user = cur.fetchone()
        conn.close()

        if not user:
            return jsonify({"success": False, "error": "Invalid credentials"}), 401

        if not verify_password(password, user[2]):
            return jsonify({"success": False, "error": "Invalid credentials"}), 401

        return jsonify({
            "success": True,
            "user": {
                "id": user[0],
                "username": user[1],
                "department": user[1],          # backward compat
                "name": user[3],
                "role": user[4],
                "icon": user[5],
                "institution_id": user[6],
                "service_id": user[7],
                "institution_name": user[8],
                "institution_slug": user[9],
            }
        })
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/auth/init', methods=['GET'])
def init_auth():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        ensure_schema(conn)
        conn.close()
        return jsonify({"success": True, "message": "Auth tables initialized"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/auth/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        institution_id = request.args.get('institution_id')
        if institution_id:
            cur.execute("""
                SELECT u.username, u.name, u.icon, u.role, i.name
                FROM users u LEFT JOIN institutions i ON u.institution_id = i.id
                WHERE u.institution_id = %s AND u.role != 'super-admin' ORDER BY u.username
            """, (institution_id,))
        else:
            cur.execute("""
                SELECT u.username, u.name, u.icon, u.role, i.name
                FROM users u LEFT JOIN institutions i ON u.institution_id = i.id
                WHERE u.role != 'super-admin' ORDER BY i.name, u.username
            """)
        rows = cur.fetchall()
        conn.close()
        return jsonify({"success": True, "users": [{
            "id": r[0], "name": r[1], "icon": r[2], "role": r[3], "institution": r[4]
        } for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/auth/change-password', methods=['POST'])
def change_password():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        data = request.json
        username = data.get('department') or data.get('username', '')
        new_password = data.get('new_password', '')
        institution_id = data.get('institution_id')

        if not username or not new_password:
            return jsonify({"success": False, "error": "Username and new password required"}), 400

        cur = conn.cursor()
        hashed = hash_password(new_password)
        if institution_id:
            cur.execute("UPDATE users SET password = %s, updated_at = NOW() WHERE username = %s AND institution_id = %s",
                        (hashed, username, institution_id))
        else:
            cur.execute("UPDATE users SET password = %s, updated_at = NOW() WHERE username = %s",
                        (hashed, username))
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "error": "User not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Password updated for {username}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =================================================================
# QUEUE
# =================================================================

def _resolve_department(department, cur, institution_id=None):
    """Resolve a department string to (filter_type, filter_value).
    Returns ('service_id', int) or ('person_like', str)."""
    try:
        sid = int(department)
        return ('service_id', sid)
    except (ValueError, TypeError):
        pass
    pf = LEGACY_PERSON_FILTERS.get(department, '%')
    return ('person_like', pf)


def _queue_where(filter_type, filter_value, institution_id=None):
    """Build WHERE clause + params for queue queries."""
    clauses = []
    params = []
    if filter_type == 'service_id':
        clauses.append("service_id = %s")
        params.append(filter_value)
    else:
        clauses.append("person LIKE %s")
        params.append(filter_value)
    if institution_id:
        clauses.append("institution_id = %s")
        params.append(institution_id)
    return " AND ".join(clauses), params


@app.route('/queue/next-number/<prefix>', methods=['GET'])
def get_next_queue_number(prefix):
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        institution_id = request.args.get('institution_id')
        today = datetime.now().strftime('%Y-%m-%d')

        if institution_id:
            cur.execute("""
                SELECT MAX(CAST(SUBSTRING(number FROM 2) AS INTEGER))
                FROM queue WHERE number LIKE %s AND DATE(created_at) = %s AND institution_id = %s
            """, (f"{prefix}%", today, institution_id))
        else:
            cur.execute("""
                SELECT MAX(CAST(SUBSTRING(number FROM 2) AS INTEGER))
                FROM queue WHERE number LIKE %s AND DATE(created_at) = %s
            """, (f"{prefix}%", today))

        max_num = (cur.fetchone()[0] or 0)
        next_num = max_num + 1
        if next_num > 999:
            conn.close()
            return jsonify({"success": False, "error": f"Max queue numbers reached for {prefix} today"}), 400

        queue_number = f"{prefix}{str(next_num).zfill(3)}"
        conn.close()
        return jsonify({
            "success": True,
            "queue_number": queue_number,
            "sequence": next_num,
            "department": prefix
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/queue', methods=['POST'])
def create_queue():
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    try:
        data = request.json
        cur = conn.cursor()
        ensure_schema(conn)

        cur.execute("""
            INSERT INTO queue (id, institution_id, service_id, number, person, date, time, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['id'],
            data.get('institution_id'),
            data.get('service_id'),
            data['number'],
            data['person'],
            data['date'],
            data['time'],
            data.get('status', 'waiting')
        ))
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
        cur.execute("UPDATE queue SET accessed = TRUE, accessed_at = NOW() WHERE id = %s", (queue_id,))
        conn.commit()
        cur.execute("""
            SELECT q.id, q.number, q.person, q.date, q.time, q.status,
                   q.institution_id, q.service_id, i.name, s.name
            FROM queue q
            LEFT JOIN institutions i ON q.institution_id = i.id
            LEFT JOIN services s ON q.service_id = s.id
            WHERE q.id = %s
        """, (queue_id,))
        r = cur.fetchone()
        conn.close()
        if r:
            return jsonify({
                "id": r[0], "number": r[1], "person": r[2],
                "date": r[3], "time": r[4], "status": r[5],
                "institution_id": r[6], "service_id": r[7],
                "institution_name": r[8], "service_name": r[9]
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
        cur.execute("SELECT accessed, accessed_at FROM queue WHERE id = %s", (queue_id,))
        r = cur.fetchone()
        conn.close()
        if r:
            return jsonify({
                "accessed": r[0] if r[0] is not None else False,
                "accessed_at": r[1].isoformat() if r[1] else None
            })
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/queue/<queue_id>/status')
def get_queue_status(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT number, person, created_at, called, is_present, institution_id, service_id
            FROM queue WHERE id = %s AND completed = FALSE
        """, (queue_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "Queue not found or already completed"}), 404

        queue_number = row[0]
        is_called = row[3] if row[3] is not None else False
        is_present = row[4] if row[4] is not None else False
        prefix = queue_number[0].upper() if queue_number else 'A'
        admin_status = admin_statuses.get(prefix, 'available')

        if admin_status == 'away':
            status = {"text": "Admin Away", "class": "status-away", "priority": "low"}
        elif is_called:
            status = {"text": "You are now being called!", "class": "status-called", "priority": "high"}
        else:
            status = {"text": "Waiting", "class": "status-waiting", "priority": "low"}

        conn.close()
        return jsonify({
            "status": status, "department_prefix": prefix,
            "admin_status": admin_status, "is_called": is_called,
            "is_present": is_present, "queue_number": queue_number
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/queue/im-here/<queue_id>', methods=['POST'])
def queue_im_here(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT number FROM queue WHERE id = %s AND completed = FALSE", (queue_id,))
        q = cur.fetchone()
        if not q:
            conn.close()
            return jsonify({"success": False, "error": "Queue not found or already completed"}), 404
        cur.execute("UPDATE queue SET is_present = TRUE, present_at = NOW() WHERE id = %s", (queue_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Marked as present", "queue_number": q[0]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/queue/cancel-im-here/<queue_id>', methods=['POST'])
def cancel_queue_im_here(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT number FROM queue WHERE id = %s AND completed = FALSE", (queue_id,))
        q = cur.fetchone()
        if not q:
            conn.close()
            return jsonify({"success": False, "error": "Queue not found or already completed"}), 404
        cur.execute("UPDATE queue SET is_present = FALSE, present_at = NULL WHERE id = %s", (queue_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Cancelled present status", "queue_number": q[0]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/queue/<queue_id>/mute-status')
def get_queue_mute_status(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT is_muted, muted_at, muted_by FROM queue WHERE id = %s", (queue_id,))
        r = cur.fetchone()
        conn.close()
        if not r:
            return jsonify({"error": "Queue not found"}), 404
        return jsonify({
            "is_muted": r[0] if r[0] is not None else False,
            "muted_at": r[1].isoformat() if r[1] else None,
            "muted_by": r[2]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/queue/<queue_id>/is-previous-day')
def check_previous_day(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT created_at, date FROM queue WHERE id = %s", (queue_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "Queue not found"}), 404
        today = datetime.now().date()
        if row[0]:
            queue_date = row[0].date()
            is_prev = queue_date < today
        else:
            parsed = parse_date(row[1])
            queue_date = parsed if parsed else today
            is_prev = queue_date < today if parsed else False
        return jsonify({
            "is_previous_day": is_prev,
            "queue_date": queue_date.isoformat(),
            "today": today.isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =================================================================
# ADMIN QUEUE MANAGEMENT
# =================================================================

@app.route('/admin/queue/<department>')
def get_admin_queue(department):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        institution_id = request.args.get('institution_id')
        ft, fv = _resolve_department(department, cur, institution_id)
        where, params = _queue_where(ft, fv, institution_id)
        cur.execute(f"""
            SELECT id, number, person, date, time, status, created_at,
                   is_present, present_at, is_muted
            FROM queue WHERE {where} ORDER BY id ASC
        """, params)
        rows = cur.fetchall()
        conn.close()
        return jsonify([{
            "id": r[0], "number": r[1], "person": r[2], "date": r[3],
            "time": r[4], "status": r[5],
            "created_at": r[6].isoformat() if r[6] else None,
            "is_present": r[7] if r[7] is not None else False,
            "present_at": r[8].isoformat() if r[8] else None,
            "is_muted": r[9] if r[9] is not None else False
        } for r in rows])
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route('/admin/queue-history/<department>')
def get_admin_queue_history(department):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        institution_id = request.args.get('institution_id')
        ft, fv = _resolve_department(department, cur, institution_id)
        where, params = _queue_where(ft, fv, institution_id)
        cur.execute(f"SELECT id, number, person, date, time, status FROM queue WHERE {where} ORDER BY id ASC", params)
        rows = cur.fetchall()
        conn.close()
        return jsonify([{
            "id": r[0], "number": r[1], "person": r[2],
            "date": r[3], "time": r[4], "status": r[5]
        } for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/stats/<department>')
def get_admin_stats(department):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        institution_id = request.args.get('institution_id')
        today = datetime.now().strftime('%Y-%m-%d')
        ft, fv = _resolve_department(department, cur, institution_id)
        where, params = _queue_where(ft, fv, institution_id)

        cur.execute(f"SELECT COUNT(*) FROM queue WHERE {where} AND DATE(created_at) = %s", params + [today])
        total_today = cur.fetchone()[0] or 0
        cur.execute(f"SELECT COUNT(*) FROM queue WHERE {where} AND (completed IS NULL OR completed = FALSE)", params)
        current_queue = cur.fetchone()[0] or 0
        cur.execute(f"SELECT COUNT(*) FROM queue WHERE {where} AND completed = TRUE AND DATE(completed_at) = %s", params + [today])
        completed_today = cur.fetchone()[0] or 0
        avg_wait = max(current_queue * 5, 5)
        conn.close()
        return jsonify({
            "totalToday": total_today, "currentQueue": current_queue,
            "completedToday": completed_today, "avgWaitTime": avg_wait
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/call-queue/<queue_id>', methods=['POST'])
def call_queue(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        data = request.json
        cur = conn.cursor()
        cur.execute("""
            UPDATE queue SET called = TRUE, called_at = NOW(), called_by = %s, status = 'called'
            WHERE id = %s AND completed = FALSE
        """, (data.get('calledBy'), queue_id))
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Queue not found or already completed"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Queue called", "status": "called"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/return-queue/<queue_id>', methods=['POST'])
def return_queue(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        data = request.json
        cur = conn.cursor()
        cur.execute("""
            UPDATE queue SET called = FALSE, status = 'waiting', returned_by = %s, returned_at = NOW()
            WHERE id = %s AND called = TRUE AND completed = FALSE
        """, (data.get('returnedBy'), queue_id))
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Queue not found, not called, or already completed"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Queue returned to waiting", "status": "waiting"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/complete-queue/<queue_id>', methods=['POST'])
def complete_queue(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        data = request.json
        cur = conn.cursor()
        cur.execute("""
            UPDATE queue SET completed = TRUE, completed_at = NOW(), completed_by = %s,
            status = 'completed', called = TRUE WHERE id = %s
        """, (data.get('completedBy'), queue_id))
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Queue not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Queue completed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/activity/<department>')
def get_recent_activity(department):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        institution_id = request.args.get('institution_id')
        ft, fv = _resolve_department(department, cur, institution_id)
        where, params = _queue_where(ft, fv, institution_id)
        cur.execute(f"""
            SELECT number, person, completed_at FROM queue
            WHERE {where} AND completed = TRUE
            ORDER BY completed_at DESC LIMIT 10
        """, params)
        rows = cur.fetchall()
        conn.close()
        return jsonify([{
            "number": r[0], "person": r[1],
            "completedAt": r[2].strftime('%Y-%m-%d %H:%M') if r[2] else None
        } for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/mute-queue/<queue_id>', methods=['POST'])
def mute_queue(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT number FROM queue WHERE id = %s AND called = TRUE AND completed = FALSE", (queue_id,))
        if not cur.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "Queue not found, not called, or already completed"}), 404
        data = request.json
        cur.execute("UPDATE queue SET is_muted = TRUE, muted_at = NOW(), muted_by = %s WHERE id = %s",
                    (data.get('mutedBy'), queue_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Queue muted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/unmute-queue/<queue_id>', methods=['POST'])
def unmute_queue(queue_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT number FROM queue WHERE id = %s AND called = TRUE AND completed = FALSE", (queue_id,))
        if not cur.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "Queue not found, not called, or already completed"}), 404
        cur.execute("UPDATE queue SET is_muted = FALSE, muted_at = NULL, muted_by = NULL WHERE id = %s", (queue_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Queue unmuted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =================================================================
# ADMIN STATUS
# =================================================================

@app.route('/admin/status', methods=['POST'])
def set_admin_status():
    try:
        data = request.get_json()
        department = data.get('department', '')
        status = data.get('status')
        service_id = data.get('service_id')

        if status not in ('available', 'busy', 'away'):
            return jsonify({"success": False, "error": "Invalid status"}), 400

        if service_id:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT prefix FROM services WHERE id = %s", (service_id,))
                row = cur.fetchone()
                conn.close()
                if row:
                    admin_statuses[row[0].strip()] = status
                    return jsonify({"success": True, "department": row[0].strip(), "status": status})

        prefix = LEGACY_DEPT_MAPPING.get(department)
        if not prefix:
            return jsonify({"success": False, "error": "Invalid department"}), 400
        admin_statuses[prefix] = status
        return jsonify({"success": True, "department": prefix, "status": status})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/status/<department>', methods=['GET'])
def get_admin_status_endpoint(department):
    try:
        status = admin_statuses.get(department.upper(), 'available')
        return jsonify({"success": True, "department": department.upper(), "status": status})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =================================================================
# DELETE QUEUES
# =================================================================

@app.route('/admin/delete-all-queues', methods=['DELETE', 'POST'])
def delete_all_queues():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        institution_id = None
        if request.json:
            institution_id = request.json.get('institution_id')

        if institution_id:
            cur.execute("SELECT COUNT(*) FROM queue WHERE institution_id = %s", (institution_id,))
            total = cur.fetchone()[0] or 0
            cur.execute("DELETE FROM queue WHERE institution_id = %s", (institution_id,))
        else:
            cur.execute("SELECT COUNT(*) FROM queue")
            total = cur.fetchone()[0] or 0
            cur.execute("DELETE FROM queue")

        deleted = cur.rowcount
        conn.commit()
        conn.close()
        return jsonify({
            "success": True, "message": f"Deleted {deleted} queues",
            "deleted": deleted, "deleted_count": deleted, "total_count": total
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/delete-department/<department>', methods=['DELETE'])
def delete_department_queues(department):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        ft, fv = _resolve_department(department, cur)
        if ft == 'service_id':
            cur.execute("DELETE FROM queue WHERE service_id = %s", (fv,))
        else:
            cur.execute("DELETE FROM queue WHERE person LIKE %s", (fv,))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Deleted {deleted} queues", "deleted": deleted, "department": department})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =================================================================
# EMERGENCY AUDIO
# =================================================================

@app.route('/emergency-audio', methods=['POST'])
def emergency_audio():
    try:
        import subprocess, sys
        data = request.json
        queue_number = data.get('queue_number', 'Unknown')
        try:
            subprocess.Popen([sys.executable, 'emergency_audio.py', str(queue_number)],
                             cwd=os.path.dirname(os.path.abspath(__file__)))
            return jsonify({"success": True, "message": f"Emergency audio triggered for {queue_number}"})
        except FileNotFoundError:
            return jsonify({"success": False, "error": "Emergency audio script not found"}), 404
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =================================================================
# ANALYTICS
# =================================================================

@app.route('/analytics/hourly-queue-data')
def get_hourly_queue_data():
    try:
        now = datetime.now()
        current_hour = now.hour
        max_hour = max(current_hour + 2, 8)
        institution_id = request.args.get('institution_id')

        labels = []
        for h in range(0, max_hour + 1):
            t = now.replace(hour=h, minute=0, second=0, microsecond=0)
            labels.append(t.strftime('%I:%M %p'))

        conn = get_db_connection()
        datasets = []
        colors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']

        if conn:
            try:
                cur = conn.cursor()
                today = now.strftime('%Y-%m-%d')
                if institution_id:
                    cur.execute("SELECT id, name, prefix FROM services WHERE institution_id = %s AND is_active = TRUE ORDER BY display_order", (institution_id,))
                else:
                    cur.execute("SELECT id, name, prefix FROM services WHERE is_active = TRUE ORDER BY institution_id, display_order LIMIT 10")
                svcs = cur.fetchall()

                for idx, (sid, sname, spfx) in enumerate(svcs):
                    data_arr = [0] * (max_hour + 1)
                    for h in range(0, min(current_hour + 1, max_hour + 1)):
                        if institution_id:
                            cur.execute("""
                                SELECT COUNT(*) FROM queue
                                WHERE service_id = %s AND institution_id = %s
                                AND DATE(created_at) = %s AND EXTRACT(HOUR FROM created_at) = %s
                            """, (sid, institution_id, today, h))
                        else:
                            cur.execute("""
                                SELECT COUNT(*) FROM queue
                                WHERE service_id = %s AND DATE(created_at) = %s
                                AND EXTRACT(HOUR FROM created_at) = %s
                            """, (sid, today, h))
                        data_arr[h] = cur.fetchone()[0] or 0
                    datasets.append({
                        'label': sname,
                        'data': data_arr,
                        'borderColor': colors[idx % len(colors)],
                        'backgroundColor': 'transparent',
                        'fill': False, 'tension': 0.1, 'borderWidth': 2,
                        'pointRadius': 0, 'pointHoverRadius': 0
                    })
                conn.close()
            except Exception as e:
                print(f"Analytics error: {e}")
                if conn:
                    conn.close()

        return jsonify({'labels': labels, 'datasets': datasets})
    except Exception as e:
        return jsonify({'labels': [], 'datasets': []})


@app.route('/analytics/hourly-department-data')
def get_hourly_department_data():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        institution_id = request.args.get('institution_id')

        if institution_id:
            cur.execute("SELECT id, name, prefix FROM services WHERE institution_id = %s AND is_active = TRUE ORDER BY display_order", (institution_id,))
        else:
            cur.execute("SELECT id, name, prefix FROM services WHERE is_active = TRUE ORDER BY institution_id, display_order LIMIT 10")

        svcs = cur.fetchall()
        result = {}

        for sid, sname, spfx in svcs:
            key = spfx.strip().lower()
            hourly = [0] * 24
            total = 0
            cur.execute("""
                SELECT EXTRACT(HOUR FROM created_at), COUNT(*)
                FROM queue WHERE service_id = %s AND DATE(created_at) = %s
                GROUP BY EXTRACT(HOUR FROM created_at)
            """, (sid, today))
            for row in cur.fetchall():
                h = int(row[0]) if row[0] is not None else 0
                if 0 <= h < 24:
                    hourly[h] = row[1]
                    total += row[1]
            result[key] = {'hourlyData': hourly, 'totalToday': total, 'name': sname}

        # backward compat keys
        legacy_map = {'a': 'dean', 'b': 'ie', 'c': 'cpe', 'd': 'ece', 'e': 'others'}
        compat = {}
        for k, v in result.items():
            legacy = legacy_map.get(k, k)
            compat[legacy] = v
            if k != legacy:
                compat[k] = v

        conn.close()
        return jsonify(compat)
    except Exception as e:
        return jsonify({}), 500


# =================================================================
# DEBUG
# =================================================================

@app.route('/debug/test')
def debug_test():
    return jsonify({"success": True, "message": "API is working"}), 200


@app.route('/debug/db')
def debug_db():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Connection failed"}), 500
        cur = conn.cursor()
        cur.execute("SELECT version()")
        v = cur.fetchone()
        conn.close()
        return jsonify({"success": True, "postgres_version": v[0]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/debug/query')
def debug_query():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "Connection failed"}), 500
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'queue' ORDER BY ordinal_position
        """)
        cols = cur.fetchall()
        cur.execute("SELECT * FROM queue LIMIT 3")
        rows = cur.fetchall()
        conn.close()
        return jsonify({
            "success": True,
            "columns": [{"name": c[0], "type": c[1]} for c in cols],
            "sample_data": [str(r) for r in rows],
            "row_count": len(rows)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =================================================================
# STATIC PAGE ROUTES
# =================================================================

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
