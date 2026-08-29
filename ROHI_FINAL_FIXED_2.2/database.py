import os
import sqlite3
import time
import logging

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance.db")
DB_TIMEOUT = 15.0
logger = logging.getLogger("ROHIApp")


def _connect():
    """Open SQLite with Android-safe timeout and WAL/busy settings."""
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _is_locked_error(exc):
    return isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower()


def _run_write(operation, retries=4):
    """Run a write transaction and retry transient Android SQLite locks."""
    last_error = None
    for attempt in range(retries):
        conn = None
        try:
            conn = _connect()
            cursor = conn.cursor()
            result = operation(cursor)
            conn.commit()
            return result
        except sqlite3.OperationalError as exc:
            last_error = exc
            if _is_locked_error(exc) and attempt < retries - 1:
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                time.sleep(0.25 * (attempt + 1))
                continue
            raise
        finally:
            if conn:
                conn.close()
    raise last_error


def create_table():
    """Create/migrate all local tables safely."""
    conn = _connect()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT,
                sex TEXT,
                dob TEXT,
                blood_group TEXT,
                marital_status TEXT,
                nationality TEXT,
                state_origin TEXT,
                lga TEXT,
                address TEXT,
                next_of_kin TEXT,
                next_of_kin_phone TEXT,
                employment_type TEXT,
                state_office TEXT,
                cluster TEXT,
                department TEXT,
                section TEXT,
                position TEXT,
                staff_number TEXT UNIQUE,
                phone TEXT,
                email TEXT UNIQUE,
                facebook TEXT,
                twitter TEXT,
                instagram TEXT,
                telegram TEXT,
                linkedin TEXT,
                gps_coordinate TEXT,
                photo TEXT,
                password TEXT,
                unique_id TEXT UNIQUE
            )
        """)
        migrations = [
            ("cluster", "TEXT"),
            ("unique_id", "TEXT"),
            ("synced", "INTEGER DEFAULT 0"),
            ("genotype", "TEXT"),
            ("reintegration_status", "TEXT"),
        ]
        for column, col_type in migrations:
            try:
                cursor.execute(f"ALTER TABLE staff ADD COLUMN {column} {col_type}")
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
        conn.commit()
    finally:
        conn.close()

    create_attendance_table()
    create_leave_table()
    create_cfm_table()


def create_attendance_table():
    """Create/migrate the attendance table."""
    conn = _connect()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                check_in_time TEXT,
                check_out_time TEXT,
                late_duration TEXT,
                attendance_status TEXT,
                gps_location TEXT,
                check_out_gps_location TEXT,
                current_state_office TEXT,
                synced INTEGER DEFAULT 0
            )
        """)
        for column, col_type in (
            ("check_in_time", "TEXT"),
            ("check_out_time", "TEXT"),
            ("late_duration", "TEXT"),
            ("attendance_status", "TEXT"),
            ("gps_location", "TEXT"),
            ("check_out_gps_location", "TEXT"),
            ("current_state_office", "TEXT"),
            ("synced", "INTEGER DEFAULT 0"),
            ("gform_synced", "INTEGER DEFAULT 0"),
        ):
            try:
                cursor.execute(f"ALTER TABLE attendance ADD COLUMN {column} {col_type}")
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
        conn.commit()
    finally:
        conn.close()


def get_pending_gform_attendance(limit=50):
    """Completed attendance rows (checked out) not yet pushed to the Google
    Form, joined with the staff record for name/department/etc. Only rows
    with a check_out_time are returned - a check-in-only row is submitted
    once, as a single complete record, after the person checks out."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT a.id, a.email, a.check_in_time, a.check_out_time, a.gps_location,
                   a.check_out_gps_location, a.current_state_office, s.fullname, s.staff_number, s.department,
                   s.section, s.position
            FROM attendance a
            LEFT JOIN staff s ON s.email = a.email
            WHERE a.check_out_time IS NOT NULL AND a.check_out_time != ''
              AND (a.gform_synced IS NULL OR a.gform_synced = 0)
            ORDER BY a.id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows
    finally:
        conn.close()


def mark_gform_synced(attendance_id):
    def operation(cursor):
        cursor.execute("UPDATE attendance SET gform_synced = 1 WHERE id = ?", (attendance_id,))
    return _run_write(operation)



def create_cfm_table():
    """Create the local Complaints & Feedback Mechanism case table."""
    conn = _connect()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cfm_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference_no TEXT UNIQUE,
                date_received TEXT,
                location_level TEXT,
                submission_method TEXT,
                complainant_name TEXT,
                complainant_phone TEXT,
                complainant_sex TEXT,
                community_location TEXT,
                anonymous INTEGER DEFAULT 0,
                preferred_contact TEXT,
                case_type TEXT,
                category TEXT,
                description TEXT,
                incident_location TEXT,
                programme_project TEXT,
                incident_datetime TEXT,
                desired_solution TEXT,
                urgency TEXT,
                assigned_to TEXT,
                target_response_date TEXT,
                status TEXT DEFAULT 'Open',
                referral_required INTEGER DEFAULT 0,
                referral_person TEXT,
                action_taken TEXT,
                response_date TEXT,
                complainant_informed INTEGER DEFAULT 0,
                complainant_satisfied TEXT,
                further_action_required INTEGER DEFAULT 0,
                closed_date TEXT,
                closed_by TEXT,
                remarks TEXT,
                cfm_office_name TEXT,
                noted TEXT,
                case_document TEXT,
                review_by_management TEXT,
                submitted_by_email TEXT,
                created_at TEXT
            )
        """)
        # Normalize legacy status labels to the three active CFM states.
        cursor.execute("UPDATE cfm_cases SET status = 'Open' WHERE status IS NULL OR status = '' OR status IN ('Received', 'Referred')")
        cursor.execute("UPDATE cfm_cases SET status = 'Closed' WHERE status = 'Resolved'")
        # Safe schema migration for existing installations. These ALTERs only add
        # missing columns; no CFM records are deleted or cleared.
        existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(cfm_cases)").fetchall()}
        for col, definition in (
            ('cfm_office_name', 'TEXT'),
            ('noted', 'TEXT'),
            ('case_document', 'TEXT'),
            ('review_by_management', 'TEXT'),
        ):
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE cfm_cases ADD COLUMN {col} {definition}")
        conn.commit()
    finally:
        conn.close()


def create_cfm_case(data):
    """Save a CFM complaint/feedback case and return its reference number."""
    def operation(cursor):
        cursor.execute("SELECT COUNT(*) FROM cfm_cases")
        count = int(cursor.fetchone()[0] or 0) + 1
        ref = data.get("reference_no") or f"ROHI-CFM-{time.strftime('%Y')}-{count:04d}"
        cursor.execute("""
            INSERT INTO cfm_cases (
                reference_no, date_received, location_level, submission_method,
                complainant_name, complainant_phone, complainant_sex, community_location,
                anonymous, preferred_contact, case_type, category, description,
                incident_location, programme_project, incident_datetime, desired_solution,
                urgency, assigned_to, target_response_date, status, referral_required,
                referral_person, action_taken, response_date, complainant_informed,
                complainant_satisfied, further_action_required, closed_date, closed_by,
                remarks, submitted_by_email, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            ref, data.get("date_received"), data.get("location_level"), data.get("submission_method"),
            data.get("complainant_name"), data.get("complainant_phone"), data.get("complainant_sex"),
            data.get("community_location"), int(bool(data.get("anonymous"))), data.get("preferred_contact"),
            data.get("case_type"), data.get("category"), data.get("description"), data.get("incident_location"),
            data.get("programme_project"), data.get("incident_datetime"), data.get("desired_solution"),
            data.get("urgency") or "Normal", data.get("assigned_to"), data.get("target_response_date"),
            data.get("status") or "Open", int(bool(data.get("referral_required"))), data.get("referral_person"),
            data.get("action_taken"), data.get("response_date"), int(bool(data.get("complainant_informed"))),
            data.get("complainant_satisfied"), int(bool(data.get("further_action_required"))), data.get("closed_date"),
            data.get("closed_by"), data.get("remarks"), data.get("submitted_by_email"), data.get("created_at")
        ))
        return ref
    return _run_write(operation)


def datetime_now_date():
    return time.strftime("%Y%m%d")


def get_cfm_counts():
    conn = _connect()
    try:
        rows = conn.execute("SELECT status, COUNT(*) FROM cfm_cases GROUP BY status").fetchall()
        counts = {"Total": 0, "Open": 0, "Under Review": 0, "Closed": 0}
        for status, count in rows:
            n = int(count or 0)
            counts["Total"] += n
            key = str(status or "Open").strip().lower()
            if key == "closed":
                counts["Closed"] += n
            elif key in ("under review", "under_review", "review"):
                counts["Under Review"] += n
            else:
                counts["Open"] += n
        return counts
    finally:
        conn.close()


def get_cfm_cases(limit=50):
    conn = _connect()
    try:
        return conn.execute("""
            SELECT id, reference_no, date_received, location_level, case_type, category,
                   urgency, status, complainant_name, anonymous, community_location, created_at
            FROM cfm_cases ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
    finally:
        conn.close()


def update_cfm_case_details(reference_no, data):
    """Update the staff-use/follow-up/closure fields for a CFM case."""
    def operation(cursor):
        cursor.execute("""
            UPDATE cfm_cases SET
                date_received=?, assigned_to=?, target_response_date=?, status=?,
                referral_required=?, referral_person=?, action_taken=?, response_date=?,
                complainant_informed=?, complainant_satisfied=?, further_action_required=?,
                closed_date=?, closed_by=?, remarks=?, cfm_office_name=?, noted=?,
                case_document=?, review_by_management=?
            WHERE reference_no=?
        """, (
            data.get("date_received"), data.get("assigned_to"), data.get("target_response_date"),
            data.get("status") or "Open", int(bool(data.get("referral_required"))),
            data.get("referral_person"), data.get("action_taken"), data.get("response_date"),
            int(bool(data.get("complainant_informed"))), data.get("complainant_satisfied"),
            int(bool(data.get("further_action_required"))), data.get("closed_date"),
            data.get("closed_by"), data.get("remarks"), data.get("cfm_office_name"),
            data.get("noted"), data.get("case_document"), data.get("review_by_management"), reference_no
        ))
        return cursor.rowcount
    return _run_write(operation)


def update_cfm_case_status(reference_no, status, action_taken="", closed_by=""):
    closed_date = time.strftime("%Y-%m-%d %H:%M:%S") if str(status).lower() == "closed" else ""
    def operation(cursor):
        cursor.execute("""
            UPDATE cfm_cases
               SET status=?, action_taken=CASE WHEN ? != '' THEN ? ELSE action_taken END,
                   closed_date=CASE WHEN ?='Closed' THEN ? ELSE closed_date END,
                   closed_by=CASE WHEN ?='Closed' THEN ? ELSE closed_by END
             WHERE reference_no=?
        """, (status, action_taken, action_taken, status, closed_date, status, closed_by, reference_no))
        return cursor.rowcount
    return _run_write(operation)



def sync_cfm_remote_status(reference_no, status, action_taken="", closed_date="", closed_by="", remarks=""):
    """Apply a status update received from the central CFM Google Sheet."""
    def operation(cursor):
        cursor.execute("""
            UPDATE cfm_cases
               SET status=?,
                   action_taken=CASE WHEN ? != '' THEN ? ELSE action_taken END,
                   closed_date=CASE WHEN ? != '' THEN ? ELSE closed_date END,
                   closed_by=CASE WHEN ? != '' THEN ? ELSE closed_by END,
                   remarks=CASE WHEN ? != '' THEN ? ELSE remarks END
             WHERE reference_no=?
        """, (status, action_taken, action_taken, closed_date, closed_date,
              closed_by, closed_by, remarks, remarks, reference_no))
        return cursor.rowcount
    return _run_write(operation)

def email_exists(email, exclude_id=None):
    """Case-insensitive email check before INSERT/UPDATE."""
    value = (email or "").strip().lower()
    if not value:
        return False
    conn = _connect()
    try:
        if exclude_id is None:
            row = conn.execute(
                "SELECT id FROM staff WHERE LOWER(TRIM(email)) = ? LIMIT 1",
                (value,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM staff WHERE LOWER(TRIM(email)) = ? AND id <> ? LIMIT 1",
                (value, exclude_id),
            ).fetchone()
        return row is not None
    finally:
        conn.close()


def staff_number_exists(staff_number, exclude_id=None):
    value = (staff_number or "").strip().lower()
    if not value:
        return False
    conn = _connect()
    try:
        if exclude_id is None:
            row = conn.execute(
                "SELECT id FROM staff WHERE LOWER(TRIM(staff_number)) = ? LIMIT 1",
                (value,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM staff WHERE LOWER(TRIM(staff_number)) = ? AND id <> ? LIMIT 1",
                (value, exclude_id),
            ).fetchone()
        return row is not None
    finally:
        conn.close()


def insert_staff(staff_data):
    """Insert a staff record with transient-lock retry."""
    def operation(cursor):
        cursor.execute("""
            INSERT INTO staff (
                fullname, sex, dob, blood_group, marital_status, nationality,
                state_origin, lga, address, next_of_kin, next_of_kin_phone,
                employment_type, state_office, cluster, department, section,
                position, staff_number, phone, email, facebook, twitter,
                instagram, telegram, linkedin, gps_coordinate, photo, password,
                unique_id, synced, genotype, reintegration_status
            ) VALUES (
                :fullname, :sex, :dob, :blood_group, :marital_status, :nationality,
                :state_origin, :lga, :address, :next_of_kin, :next_of_kin_phone,
                :employment_type, :state_office, :cluster, :department, :section,
                :position, :staff_number, :phone, :email, :facebook, :twitter,
                :instagram, :telegram, :linkedin, :gps_coordinate, :photo, :password,
                :unique_id, 0, :genotype, :reintegration_status
            )
        """, staff_data)
    return _run_write(operation)


def update_staff(staff_id, staff_data):
    """Update an existing staff record with transient-lock retry."""
    data = dict(staff_data)
    data["id"] = staff_id

    def operation(cursor):
        cursor.execute("""
            UPDATE staff SET
                synced = 0,
                fullname = :fullname,
                sex = :sex,
                dob = :dob,
                blood_group = :blood_group,
                marital_status = :marital_status,
                nationality = :nationality,
                state_origin = :state_origin,
                lga = :lga,
                address = :address,
                next_of_kin = :next_of_kin,
                next_of_kin_phone = :next_of_kin_phone,
                employment_type = :employment_type,
                state_office = :state_office,
                cluster = :cluster,
                department = :department,
                section = :section,
                position = :position,
                staff_number = :staff_number,
                phone = :phone,
                email = :email,
                facebook = :facebook,
                twitter = :twitter,
                instagram = :instagram,
                telegram = :telegram,
                linkedin = :linkedin,
                gps_coordinate = :gps_coordinate,
                photo = :photo,
                password = :password,
                genotype = :genotype,
                reintegration_status = :reintegration_status
            WHERE id = :id
        """, data)
    return _run_write(operation)


def get_staff_by_id(staff_id):
    conn = _connect()
    try:
        return conn.execute("SELECT * FROM staff WHERE id = ?", (staff_id,)).fetchone()
    finally:
        conn.close()


def get_staff_count():
    """Return how many staff records exist in the local database. Used to
    enforce a single on-device registration (one phone = one staff account)."""
    conn = _connect()
    try:
        row = conn.execute("SELECT COUNT(*) FROM staff").fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def clear_all_staff():
    """Remove all existing staff records from the local database. Called
    before saving a brand new registration so a phone never ends up
    holding more than one staff registration at a time."""
    def operation(cursor):
        cursor.execute("DELETE FROM staff")
    return _run_write(operation)


def verify_login(email_or_staff_num, password):
    conn = _connect()
    try:
        identifier = (email_or_staff_num or "").strip().lower()
        return conn.execute("""
            SELECT * FROM staff
            WHERE (LOWER(TRIM(email)) = ? OR LOWER(TRIM(staff_number)) = ?)
              AND password = ?
        """, (identifier, identifier, password)).fetchone()
    finally:
        conn.close()


def create_leave_table():
    """Create the leave request table used by the Leave Management module."""
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leave_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_email TEXT NOT NULL,
                staff_name TEXT,
                leave_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                days INTEGER NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'Pending',
                manager_email TEXT,
                manager_comment TEXT,
                manager_signature TEXT,
                submitted_at TEXT,
                reviewed_at TEXT,
                synced INTEGER DEFAULT 0
            )
        """)
        conn.commit()
    finally:
        conn.close()


def create_leave_request(data):
    """Save a new leave request locally and mark it pending."""
    def operation(cursor):
        cursor.execute("""
            INSERT INTO leave_requests (
                staff_email, staff_name, leave_type, start_date, end_date,
                days, reason, status, submitted_at, synced
            ) VALUES (
                :staff_email, :staff_name, :leave_type, :start_date, :end_date,
                :days, :reason, 'Pending', :submitted_at, 0
            )
        """, data)
        return cursor.lastrowid
    return _run_write(operation)


def get_leave_requests(staff_email):
    conn = _connect()
    try:
        return conn.execute("""
            SELECT id, leave_type, start_date, end_date, days, reason,
                   status, manager_comment, submitted_at
            FROM leave_requests
            WHERE LOWER(TRIM(staff_email)) = LOWER(TRIM(?))
            ORDER BY id DESC
        """, (staff_email or "",)).fetchall()
    finally:
        conn.close()



def get_leave_status_counts(staff_email):
    """Return pending, approved and rejected leave request counts for a staff member."""
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT status, COUNT(*)
            FROM leave_requests
            WHERE LOWER(TRIM(staff_email)) = LOWER(TRIM(?))
            GROUP BY status
        """, (staff_email or "",)).fetchall()
        counts = {"Pending": 0, "Approved": 0, "Rejected": 0}
        for status, count in rows:
            key = str(status or "Pending").strip().title()
            if key in counts:
                counts[key] = int(count or 0)
        return counts
    finally:
        conn.close()

def get_leave_usage(staff_email, leave_type, year):
    """Return approved leave days used for a leave type in a year."""
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT COALESCE(SUM(days), 0)
            FROM leave_requests
            WHERE LOWER(TRIM(staff_email)) = LOWER(TRIM(?))
              AND leave_type = ?
              AND status = 'Approved'
              AND substr(start_date, 1, 4) = ?
        """, (staff_email or "", leave_type, str(year))).fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()
