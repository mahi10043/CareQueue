"""SQLite data layer for CareQueue. UI code should call these functions."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date, time
from pathlib import Path
import hashlib
import hmac
import secrets

DB_PATH = os.environ.get("CAREQUEUE_DB_PATH", str(Path(__file__).with_name("carequeue.db")))
STATUSES = ("Scheduled", "Waiting", "In Consultation", "Completed", "Cancelled")
DEPARTMENTS = ("General Medicine", "Cardiology", "Dermatology", "ENT", "Orthopedics", "Pediatrics", "Neurology", "Dental", "Ophthalmology", "Other")

def now_iso():
    return datetime.now().replace(microsecond=0).isoformat(timespec="seconds")

@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def setting(name, default=""):
    """Read a deployment setting from environment or Streamlit secrets."""
    value = os.environ.get(name)
    if value is not None:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, default))
    except Exception:
        return default

def init_db():
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with connection() as conn:
        conn.executescript(schema)
        # Create a local default staff account only when explicitly configured.
        # Set CAREQUEUE_ADMIN_USERNAME and CAREQUEUE_ADMIN_PASSWORD before first run.
        username = setting("CAREQUEUE_ADMIN_USERNAME", "").strip()
        password = setting("CAREQUEUE_ADMIN_PASSWORD", "")
        if username and password:
            exists = conn.execute("SELECT 1 FROM staff WHERE username = ?", (username,)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO staff(username,password_hash,role) VALUES(?,?,?)",
                    (username, hash_password(password), "admin")
                )

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
    return f"{salt}${digest}"

def verify_password(password, stored):
    try:
        salt, expected = stored.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False

def authenticate(username, password):
    with connection() as conn:
        row = conn.execute(
            "SELECT staff_id, username, password_hash, role FROM staff WHERE username=? AND active=1",
            (username.strip(),)
        ).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return {"staff_id": row["staff_id"], "username": row["username"], "role": row["role"]}
    return None

def create_staff(username, password, role="staff"):
    if not username.strip() or len(password) < 10:
        raise ValueError("Username is required and password must contain at least 10 characters.")
    if role not in ("admin", "staff"):
        raise ValueError("Invalid role.")
    with connection() as conn:
        conn.execute("INSERT INTO staff(username,password_hash,role) VALUES(?,?,?)",
                     (username.strip(), hash_password(password), role))

def add_patient(full_name, age, gender, phone):
    full_name = full_name.strip()
    phone = phone.strip()
    if not full_name:
        raise ValueError("Patient name is required.")
    if not str(age).isdigit() or not 0 <= int(age) <= 120:
        raise ValueError("Age must be between 0 and 120.")
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 7 or len(digits) > 15:
        raise ValueError("Enter a valid phone number containing 7–15 digits.")
    with connection() as conn:
        cur = conn.execute(
            "INSERT INTO patients(full_name,age,gender,phone) VALUES(?,?,?,?)",
            (full_name, int(age), gender, phone)
        )
        return cur.lastrowid

def update_patient(patient_id, full_name, age, gender, phone):
    full_name = full_name.strip()
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not full_name or not str(age).isdigit() or not 0 <= int(age) <= 120:
        raise ValueError("Enter a valid name and age (0–120).")
    if not 7 <= len(digits) <= 15:
        raise ValueError("Enter a valid phone number containing 7–15 digits.")
    with connection() as conn:
        conn.execute("UPDATE patients SET full_name=?,age=?,gender=?,phone=? WHERE patient_id=?",
                     (full_name, int(age), gender, phone.strip(), int(patient_id)))

def create_appointment(patient_id, department, doctor, appt_date, appt_time, reason=""):
    d = date.fromisoformat(str(appt_date))
    t = time.fromisoformat(str(appt_time))
    if d < date.today():
        raise ValueError("Appointment date cannot be in the past.")
    if not department.strip() or not doctor.strip():
        raise ValueError("Department and doctor are required.")
    with connection() as conn:
        # Prevent an exact duplicate active appointment for the same patient/doctor/time.
        duplicate = conn.execute("""
            SELECT appointment_id FROM appointments
            WHERE patient_id=? AND doctor=? AND appointment_date=? AND appointment_time=?
              AND status <> 'Cancelled'
        """, (int(patient_id), doctor.strip(), d.isoformat(), t.strftime("%H:%M"))).fetchone()
        if duplicate:
            raise ValueError(f"A matching appointment already exists (ID {duplicate['appointment_id']}).")
        cur = conn.execute("""
            INSERT INTO appointments(patient_id,department,doctor,appointment_date,appointment_time,reason)
            VALUES(?,?,?,?,?,?)
        """, (int(patient_id), department.strip(), doctor.strip(), d.isoformat(), t.strftime("%H:%M"), reason.strip()))
        return cur.lastrowid

def get_patients(search=""):
    with connection() as conn:
        return conn.execute("""
            SELECT patient_id,full_name,age,gender,phone,created_at FROM patients
            WHERE full_name LIKE ? OR CAST(patient_id AS TEXT) LIKE ?
            ORDER BY full_name COLLATE NOCASE
        """, (f"%{search.strip()}%", f"%{search.strip()}%")).fetchall()

def get_patient(patient_id):
    with connection() as conn:
        return conn.execute("SELECT * FROM patients WHERE patient_id=?", (int(patient_id),)).fetchone()

def get_appointments(filters=None):
    filters = filters or {}
    clauses, params = [], []
    for key, col in (("date", "a.appointment_date"), ("department", "a.department"),
                     ("doctor", "a.doctor"), ("status", "a.status")):
        val = filters.get(key)
        if val and val != "All":
            clauses.append(f"{col} = ?")
            params.append(val)
    search = filters.get("search", "").strip()
    if search:
        clauses.append("(p.full_name LIKE ? OR CAST(a.appointment_id AS TEXT) LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT a.*, p.full_name, p.age, p.gender, p.phone
        FROM appointments a JOIN patients p ON p.patient_id=a.patient_id
        {where}
        ORDER BY a.appointment_date DESC, a.appointment_time ASC, a.appointment_id ASC
    """
    with connection() as conn:
        return conn.execute(sql, params).fetchall()

def get_appointment(appointment_id):
    with connection() as conn:
        return conn.execute("""
            SELECT a.*,p.full_name,p.age,p.gender,p.phone FROM appointments a
            JOIN patients p ON p.patient_id=a.patient_id WHERE a.appointment_id=?
        """, (int(appointment_id),)).fetchone()

def update_appointment(appointment_id, department, doctor, appt_date, appt_time, reason):
    d, t = date.fromisoformat(str(appt_date)), time.fromisoformat(str(appt_time))
    row = get_appointment(appointment_id)
    if not row:
        raise ValueError("Appointment was not found.")
    if row["status"] in ("Completed", "Cancelled", "In Consultation"):
        raise ValueError("This appointment can no longer be edited.")
    if d < date.today():
        raise ValueError("Appointment date cannot be in the past.")
    with connection() as conn:
        duplicate = conn.execute("""
            SELECT appointment_id FROM appointments
            WHERE patient_id=? AND doctor=? AND appointment_date=? AND appointment_time=?
              AND status <> 'Cancelled' AND appointment_id <> ?
        """, (row["patient_id"], doctor.strip(), d.isoformat(), t.strftime("%H:%M"), int(appointment_id))).fetchone()
        if duplicate:
            raise ValueError(f"A matching appointment already exists (ID {duplicate['appointment_id']}).")
        conn.execute("""
            UPDATE appointments SET department=?,doctor=?,appointment_date=?,appointment_time=?,
              reason=?,updated_at=? WHERE appointment_id=?
        """, (department.strip(), doctor.strip(), d.isoformat(), t.strftime("%H:%M"),
              reason.strip(), now_iso(), int(appointment_id)))

def cancel_appointment(appointment_id):
    row = get_appointment(appointment_id)
    if not row:
        raise ValueError("Appointment was not found.")
    if row["status"] in ("Completed", "Cancelled", "In Consultation"):
        raise ValueError(f"Cannot cancel an appointment with status {row['status']}.")
    with connection() as conn:
        conn.execute("UPDATE appointments SET status='Cancelled',updated_at=? WHERE appointment_id=?",
                     (now_iso(), int(appointment_id)))

def check_in(appointment_id):
    row = get_appointment(appointment_id)
    if not row or row["status"] != "Scheduled":
        raise ValueError("Only scheduled appointments can be checked in.")
    if row["appointment_date"] != date.today().isoformat():
        raise ValueError("Only today's appointments can be checked in.")
    with connection() as conn:
        queue = conn.execute("""
            SELECT COALESCE(MAX(queue_number),0)+1 AS next_no FROM appointments
            WHERE appointment_date=? AND queue_number IS NOT NULL
        """, (date.today().isoformat(),)).fetchone()["next_no"]
        conn.execute("""
            UPDATE appointments SET status='Waiting',check_in_at=?,queue_number=?,updated_at=?
            WHERE appointment_id=? AND status='Scheduled'
        """, (now_iso(), queue, now_iso(), int(appointment_id)))

def start_consultation(appointment_id):
    row = get_appointment(appointment_id)
    if not row or row["status"] != "Waiting":
        raise ValueError("Only waiting patients can start a consultation.")
    with connection() as conn:
        active = conn.execute("SELECT appointment_id FROM appointments WHERE status='In Consultation'").fetchone()
        if active:
            raise ValueError(f"Appointment {active['appointment_id']} is already in consultation. Complete it first.")
        conn.execute("""
            UPDATE appointments SET status='In Consultation',consultation_start_at=?,updated_at=?
            WHERE appointment_id=? AND status='Waiting'
        """, (now_iso(), now_iso(), int(appointment_id)))

def complete_consultation(appointment_id):
    row = get_appointment(appointment_id)
    if not row or row["status"] != "In Consultation":
        raise ValueError("Only patients currently in consultation can be completed.")
    with connection() as conn:
        conn.execute("""
            UPDATE appointments SET status='Completed',consultation_end_at=?,updated_at=?
            WHERE appointment_id=? AND status='In Consultation'
        """, (now_iso(), now_iso(), int(appointment_id)))

def manual_status(appointment_id, status):
    if status == "Waiting":
        return check_in(appointment_id)
    if status == "In Consultation":
        return start_consultation(appointment_id)
    if status == "Completed":
        return complete_consultation(appointment_id)
    if status == "Cancelled":
        return cancel_appointment(appointment_id)
    raise ValueError("Status cannot be changed directly to Scheduled.")

def minutes_between(start, end):
    if not start or not end:
        return None
    try:
        return max(0.0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 60)
    except (ValueError, TypeError):
        return None

def rows_to_dicts(rows):
    return [dict(r) for r in rows]

def table_counts():
    today = date.today().isoformat()
    with connection() as conn:
        total_today = conn.execute("SELECT COUNT(*) FROM appointments WHERE appointment_date=?", (today,)).fetchone()[0]
        waiting = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='Waiting' AND appointment_date=?", (today,)).fetchone()[0]
        in_consult = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='In Consultation'").fetchone()[0]
        completed_today = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='Completed' AND appointment_date=?", (today,)).fetchone()[0]
        total_patients = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        total_appts = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        cancelled = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='Cancelled'").fetchone()[0]
        active_queue = conn.execute("SELECT COUNT(*) FROM appointments WHERE status IN ('Waiting','In Consultation') AND appointment_date=?", (today,)).fetchone()[0]
        measured = conn.execute("""
            SELECT check_in_at,consultation_start_at FROM appointments
            WHERE check_in_at IS NOT NULL AND consultation_start_at IS NOT NULL
        """).fetchall()
        durations = conn.execute("""
            SELECT consultation_start_at,consultation_end_at FROM appointments
            WHERE consultation_start_at IS NOT NULL AND consultation_end_at IS NOT NULL
        """).fetchall()
    waits = [minutes_between(r["check_in_at"], r["consultation_start_at"]) for r in measured]
    waits = [v for v in waits if v is not None]
    consults = [minutes_between(r["consultation_start_at"], r["consultation_end_at"]) for r in durations]
    consults = [v for v in consults if v is not None]
    return {
        "today": total_today, "waiting": waiting, "in_consult": in_consult,
        "completed_today": completed_today, "total_patients": total_patients,
        "total_appointments": total_appts, "cancelled": cancelled, "active_queue": active_queue,
        "avg_wait": sum(waits)/len(waits) if waits else None,
        "avg_consult": sum(consults)/len(consults) if consults else None,
        "measured_wait_count": len(waits)
    }

def departments():
    with connection() as conn:
        rows = conn.execute("SELECT DISTINCT department FROM appointments ORDER BY department").fetchall()
    return [r[0] for r in rows]

def doctors():
    with connection() as conn:
        rows = conn.execute("SELECT DISTINCT doctor FROM appointments ORDER BY doctor").fetchall()
    return [r[0] for r in rows]
