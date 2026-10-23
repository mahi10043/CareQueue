import os
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.express as px
import streamlit as st
import db

st.set_page_config(page_title="CareQueue | Hospital Management", page_icon="🏥", layout="wide")
db.init_db()


st.markdown("""
<style>
:root {
    color-scheme: light;
    --bg: #F3F6FA;
    --surface: #FFFFFF;
    --text: #1D2B3F;
    --muted: #52657A;
    --border: #D5DEEA;
    --primary: #2563EB;
    --teal: #0F9488;
}

.stApp {
    background: var(--bg) !important;
    color: var(--text) !important;
}

.block-container {
    max-width: 1500px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

[data-testid="stSidebar"] {
    background: #17324F !important;
}

[data-testid="stSidebar"] * {
    color: #F7FAFF !important;
}

h1, h2, h3, h4 {
    color: var(--text) !important;
}

[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
.stTextInput label,
.stNumberInput label,
.stSelectbox label,
.stDateInput label,
.stTimeInput label,
.stTextArea label,
.stCheckbox label,
.stRadio label {
    color: #24364D !important;
    opacity: 1 !important;
    font-weight: 600 !important;
}

[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stTimeInput"] input,
[data-testid="stTextArea"] textarea {
    background: #FFFFFF !important;
    color: #1D2B3F !important;
    -webkit-text-fill-color: #1D2B3F !important;
    border: 1px solid #C6D2E0 !important;
    border-radius: 9px !important;
}

[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    border-color: #C6D2E0 !important;
}

[data-baseweb="select"] * {
    color: #1D2B3F !important;
}

.hero {
    background: linear-gradient(115deg, #183B63, #236B78);
    padding: 1.5rem;
    border-radius: 16px;
    color: #FFFFFF !important;
    margin-bottom: 1.25rem;
}

.hero h1 {
    color: #FFFFFF !important;
    margin: 0;
}

.hero p {
    color: #F0F7FF !important;
    line-height: 1.6;
}

.metric {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-top: 4px solid var(--teal);
    border-radius: 13px;
    padding: 15px;
    min-height: 100px;
}

.metric-label {
    color: var(--muted) !important;
    font-size: 0.86rem;
}

.metric-value {
    color: var(--text) !important;
    font-size: 1.65rem;
    font-weight: 750;
}

.small-note {
    color: var(--muted) !important;
    font-size: 0.82rem;
}

[data-testid="stForm"] {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    padding: 1.2rem !important;
}

div.stButton > button,
[data-testid="stDownloadButton"] button {
    border-radius: 9px !important;
    min-height: 2.6rem;
}

div.stButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"] {
    background: var(--primary) !important;
    border-color: var(--primary) !important;
    color: #FFFFFF !important;
}

@media (max-width: 900px) {
    .block-container {
        padding: 1rem;
    }

    .metric {
        padding: 12px;
        min-height: 90px;
    }
}

@media (max-width: 600px) {
    .block-container {
        padding-left: 0.7rem;
        padding-right: 0.7rem;
    }

    .metric-value {
        font-size: 1.35rem;
    }
}
</style>
""", unsafe_allow_html=True)

def metric(label, value, note=""):
    st.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="small-note">{note}</div></div>', unsafe_allow_html=True)

def safe_minutes(value):
    return "Not available" if value is None else f"{value:.1f} min"

def appt_frame(rows):
    data = db.rows_to_dicts(rows)
    if not data:
        return pd.DataFrame()
    frame = pd.DataFrame(data)
    if "check_in_at" in frame and "consultation_start_at" in frame:
        frame["Measured wait (min)"] = frame.apply(
            lambda r: db.minutes_between(r.get("check_in_at"), r.get("consultation_start_at")), axis=1)
    if "consultation_start_at" in frame and "consultation_end_at" in frame:
        frame["Consultation duration (min)"] = frame.apply(
            lambda r: db.minutes_between(r.get("consultation_start_at"), r.get("consultation_end_at")), axis=1)
    return frame

def export_button(frame, filename, label="Download CSV"):
    if frame is not None and not frame.empty:
        st.download_button(label, frame.to_csv(index=False).encode("utf-8-sig"), filename, "text/csv")
    else:
        st.caption("No records available to export.")

def require_staff():
    if not st.session_state.get("staff"):
        st.warning("Please sign in to access patient information and staff operations.")
        st.stop()

def login_page():
    st.markdown('<div class="hero"><h1>CareQueue</h1><p>Hospital Appointment and Queue Management System</p></div>', unsafe_allow_html=True)
    st.info("Staff sign-in is enabled. Configure an initial administrator before launching; see README.md.")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        user = db.authenticate(username, password)
        if user:
            st.session_state.staff = user
            st.session_state.login_at = datetime.now().isoformat(timespec="seconds")
            st.rerun()
        else:
            st.error("Sign-in failed. Check your credentials.")
    st.caption("Educational prototype only. Do not use real patient data in an unsecured deployment.")

if not st.session_state.get("staff"):
    login_page()
    st.stop()

# Simple idle timeout: Streamlit checks this whenever the app reruns.
# For production, enforce session expiry server-side as well.
login_at = st.session_state.get("login_at")
if login_at:
    try:
        if (datetime.now() - datetime.fromisoformat(login_at)).total_seconds() > 15 * 60:
            st.session_state.clear()
            st.warning("Your session expired after 15 minutes. Please sign in again.")
            st.rerun()
    except ValueError:
        st.session_state.clear()
        st.rerun()

with st.sidebar:
    st.markdown("## 🏥 CareQueue")
    st.caption(f"Signed in: {st.session_state.staff['username']} ({st.session_state.staff['role']})")
    page = st.radio("NAVIGATION", ["Dashboard", "Register Patient", "Appointments", "Patient Queue", "Analytics", "Patient Records"])
    st.divider()
    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    st.caption("Prototype • Use fictional data")

st.markdown(f'<div class="hero"><h1>CareQueue</h1><p>Hospital Appointment and Queue Management System · {page}</p></div>', unsafe_allow_html=True)

today = date.today().isoformat()
all_rows = db.get_appointments()
all_df = appt_frame(all_rows)

if page == "Dashboard":
    counts = db.table_counts()
    c = st.columns(5)
    with c[0]: metric("Appointments today", counts["today"])
    with c[1]: metric("Patients waiting", counts["waiting"])
    with c[2]: metric("In consultation", counts["in_consult"])
    with c[3]: metric("Completed today", counts["completed_today"])
    with c[4]: metric("Average measured wait", safe_minutes(counts["avg_wait"]), f"{counts['measured_wait_count']} measured visits")
    st.subheader("Today's appointments")
    today_rows = db.get_appointments({"date": today})
    today_df = appt_frame(today_rows)
    if today_df.empty:
        st.info("No appointments are scheduled for today.")
    else:
        cols = [c for c in ["appointment_id","full_name","department","doctor","appointment_time","status","queue_number"] if c in today_df.columns]
        st.dataframe(today_df[cols].rename(columns={"appointment_id":"Appointment ID","full_name":"Patient","department":"Department","doctor":"Doctor","appointment_time":"Time","status":"Status","queue_number":"Queue #"}), use_container_width=True, hide_index=True)
    left, right = st.columns(2)
    if all_df.empty:
        st.info("Charts will appear after appointments are added.")
    else:
        with left:
            dept = all_df.groupby("department", dropna=False).size().reset_index(name="Appointments")
            st.plotly_chart(px.bar(dept, x="department", y="Appointments", title="Appointments by department", color_discrete_sequence=["#0d9488"]), use_container_width=True)
        with right:
            statuses = all_df.groupby("status", dropna=False).size().reset_index(name="Patients")
            st.plotly_chart(px.pie(statuses, names="status", values="Patients", title="Appointments by status", hole=.45), use_container_width=True)
        trend = all_df.groupby("appointment_date").size().reset_index(name="Appointments").sort_values("appointment_date")
        st.plotly_chart(px.line(trend, x="appointment_date", y="Appointments", markers=True, title="Daily appointment trend"), use_container_width=True)
        if "Measured wait (min)" in all_df and all_df["Measured wait (min)"].notna().any():
            wait_dept = all_df.dropna(subset=["Measured wait (min)"]).groupby("department")["Measured wait (min)"].mean().reset_index()
            st.plotly_chart(px.bar(wait_dept, x="department", y="Measured wait (min)", title="Average measured waiting time by department"), use_container_width=True)
        else:
            st.info("Department waiting-time chart needs completed check-in and consultation-start timestamps.")

elif page == "Register Patient":
    st.subheader("Register a patient and optionally schedule an appointment")
    with st.form("register_patient_form", clear_on_submit=True):
        name = st.text_input("Patient full name *")
        col1, col2 = st.columns(2)
        age = col1.number_input("Age *", min_value=0, max_value=120, value=18, step=1)
        gender = col2.selectbox("Gender", ["Prefer not to say", "Female", "Male", "Non-binary", "Other"])
        phone = st.text_input("Phone number *")
        schedule = st.checkbox("Schedule an appointment now", value=True)
        department, doctor = "", ""
        appt_date, appt_time, reason = date.today(), datetime.now().replace(minute=0, second=0, microsecond=0).time(), ""
        if schedule:
            col3, col4 = st.columns(2)
            department = col3.selectbox("Department *", db.DEPARTMENTS)
            doctor = col4.text_input("Doctor name *")
            col5, col6 = st.columns(2)
            appt_date = col5.date_input("Appointment date *", min_value=date.today(), value=date.today())
            appt_time = col6.time_input("Appointment time *", value=appt_time)
            reason = st.text_area("Reason for visit (optional)", max_chars=500)
        submit = st.form_submit_button("Save patient", type="primary", use_container_width=True)
    if submit:
        try:
            patient_id = db.add_patient(name, age, gender, phone)
            appointment_id = None
            if schedule:
                if not doctor.strip():
                    st.error("Doctor name is required when scheduling.")
                else:
                    appointment_id = db.create_appointment(patient_id, department, doctor, appt_date, appt_time, reason)
            st.success(f"Patient saved. Patient ID: {patient_id}" + (f" · Appointment ID: {appointment_id}" if appointment_id else ""))
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save the registration: {exc}")

elif page == "Appointments":
    st.subheader("Appointment management")
    with st.expander("Create an appointment for an existing patient", expanded=False):
        patients = db.get_patients()
        if not patients:
            st.info("Register a patient first.")
        else:
            options = {f"#{p['patient_id']} — {p['full_name']}": p["patient_id"] for p in patients}
            with st.form("new_appointment_form"):
                patient_label = st.selectbox("Patient", list(options))
                col1, col2 = st.columns(2)
                department = col1.selectbox("Department", db.DEPARTMENTS)
                doctor = col2.text_input("Doctor name")
                col3, col4 = st.columns(2)
                appt_date = col3.date_input("Appointment date", min_value=date.today(), value=date.today())
                appt_time = col4.time_input("Appointment time")
                reason = st.text_area("Reason (optional)", max_chars=500)
                submitted = st.form_submit_button("Create appointment", type="primary")
            if submitted:
                try:
                    aid = db.create_appointment(options[patient_label], department, doctor, appt_date, appt_time, reason)
                    st.success(f"Appointment #{aid} created.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
    with st.expander("Search and filter appointments", expanded=True):
        f1, f2, f3 = st.columns(3)
        search = f1.text_input("Search name or appointment ID")
        selected_date = f2.date_input("Date filter (optional)", value=None)
        dept_options = ["All"] + db.DEPARTMENTS
        selected_dept = f3.selectbox("Department", dept_options)
        f4, f5 = st.columns(2)
        doctor_options = ["All"] + db.doctors()
        selected_doctor = f4.selectbox("Doctor", doctor_options)
        selected_status = f5.selectbox("Status", ["All", *db.STATUSES])
    filters = {"search":search, "date":selected_date.isoformat() if selected_date else None, "department":selected_dept, "doctor":selected_doctor, "status":selected_status}
    rows = db.get_appointments(filters)
    frame = appt_frame(rows)
    if frame.empty:
        st.info("No appointments match these filters.")
    else:
        display_cols = ["appointment_id","full_name","department","doctor","appointment_date","appointment_time","status","queue_number"]
        st.dataframe(frame[[c for c in display_cols if c in frame]].rename(columns={"appointment_id":"ID","full_name":"Patient","department":"Department","doctor":"Doctor","appointment_date":"Date","appointment_time":"Time","status":"Status","queue_number":"Queue #"}), use_container_width=True, hide_index=True)
        export_button(frame, "carequeue_appointments.csv", "Export filtered appointments")
    st.divider()
    st.subheader("Edit or cancel an appointment")
    editable = [r for r in rows if r["status"] in ("Scheduled","Waiting")]
    if not editable:
        st.caption("No editable appointments in the current filtered results.")
    else:
        labels = {f"#{r['appointment_id']} · {r['full_name']} · {r['appointment_date']} {r['appointment_time']}":r for r in editable}
        chosen_label = st.selectbox("Choose appointment", list(labels))
        chosen = labels[chosen_label]
        with st.form("edit_appointment_form"):
            e1,e2 = st.columns(2)
            new_dept = e1.selectbox("Department", db.DEPARTMENTS, index=db.DEPARTMENTS.index(chosen["department"]) if chosen["department"] in db.DEPARTMENTS else 0)
            new_doctor = e2.text_input("Doctor", value=chosen["doctor"])
            e3,e4 = st.columns(2)
            new_date = e3.date_input("Date", value=date.fromisoformat(chosen["appointment_date"]), min_value=date.today())
            new_time = e4.time_input("Time", value=datetime.strptime(chosen["appointment_time"], "%H:%M").time())
            new_reason = st.text_area("Reason", value=chosen["reason"] or "")
            save_edit = st.form_submit_button("Save changes")
        b1,b2 = st.columns(2)
        with b1:
            if save_edit:
                try:
                    db.update_appointment(chosen["appointment_id"], new_dept, new_doctor, new_date, new_time, new_reason)
                    st.success("Appointment updated.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        with b2:
            if st.button("Cancel selected appointment", type="secondary"):
                try:
                    db.cancel_appointment(chosen["appointment_id"])
                    st.success("Appointment cancelled.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

elif page == "Patient Queue":
    st.subheader("Today's consultation queue")
    st.caption("Queue order is assigned at check-in. Only checked-in patients enter the active queue.")
    queue_rows = db.get_appointments({"date": today})
    queue = [r for r in queue_rows if r["status"] in ("Waiting","In Consultation")]
    queue.sort(key=lambda r: (r["status"] != "In Consultation", r["queue_number"] or 999999, r["appointment_time"]))
    active = [r for r in queue if r["status"] == "In Consultation"]
    if active:
        r = active[0]
        st.success(f"Currently consulting: #{r['appointment_id']} — {r['full_name']} · {r['department']} · Dr. {r['doctor']}")
    else:
        st.info("No consultation is currently in progress.")
    if not queue:
        st.info("No patients are currently in the active queue.")
    else:
        qdf = appt_frame(queue)
        cols = ["queue_number","appointment_id","full_name","department","doctor","appointment_time","status","check_in_at","consultation_start_at"]
        st.dataframe(qdf[[c for c in cols if c in qdf]].rename(columns={"queue_number":"Queue #","appointment_id":"Appointment ID","full_name":"Patient","department":"Department","doctor":"Doctor","appointment_time":"Appointment time","status":"Status","check_in_at":"Checked in at","consultation_start_at":"Consultation started"}), use_container_width=True, hide_index=True)
    st.divider()
    todays_scheduled = [r for r in queue_rows if r["status"] == "Scheduled"]
    st.subheader("Check in a scheduled patient")
    if todays_scheduled:
        options = {f"#{r['appointment_id']} · {r['full_name']} · {r['appointment_time']}":r for r in todays_scheduled}
        selected = st.selectbox("Scheduled appointment", list(options))
        if st.button("Check in patient", type="primary"):
            try:
                db.check_in(options[selected]["appointment_id"])
                st.success("Patient checked in and added to the queue.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    else:
        st.caption("No scheduled appointments available for check-in today.")
    waiting = [r for r in queue if r["status"] == "Waiting"]
    st.subheader("Call next eligible patient")
    if waiting:
        waiting.sort(key=lambda r: (r["queue_number"] or 999999, r["appointment_time"]))
        next_patient = waiting[0]
        st.write(f"Next: **#{next_patient['appointment_id']} — {next_patient['full_name']}** (Queue #{next_patient['queue_number']})")
        if st.button("Start next consultation", type="primary"):
            try:
                db.start_consultation(next_patient["appointment_id"])
                st.success("Consultation started.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    else:
        st.caption("No checked-in patients are waiting.")
    if active:
        st.subheader("Complete consultation")
        current = active[0]
        st.write(f"Current patient: **{current['full_name']}**")
        if st.button("Mark consultation completed", type="primary"):
            try:
                db.complete_consultation(current["appointment_id"])
                st.success("Consultation completed and end time recorded.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.divider()
    st.subheader("Upcoming appointment check-in reminder")
    upcoming = [r for r in queue_rows if r["status"] == "Scheduled"]
    if upcoming:
        st.dataframe(pd.DataFrame([dict(r) for r in upcoming])[["appointment_id","full_name","appointment_time","department","doctor"]].rename(columns={"appointment_id":"ID","full_name":"Patient","appointment_time":"Time","department":"Department","doctor":"Doctor"}), use_container_width=True, hide_index=True)
    else:
        st.caption("No scheduled appointments remain for today.")

elif page == "Analytics":
    st.subheader("Operational analytics")
    a1,a2 = st.columns(2)
    start_date = a1.date_input("From date", value=date.today()-timedelta(days=30))
    end_date = a2.date_input("To date", value=date.today())
    if start_date > end_date:
        st.error("Start date must be on or before end date.")
        st.stop()
    rows = db.get_appointments()
    df = appt_frame(rows)
    if not df.empty:
        df = df[(df["appointment_date"] >= start_date.isoformat()) & (df["appointment_date"] <= end_date.isoformat())]
    if df.empty:
        st.info("No appointments are available for the selected period.")
    else:
        total = len(df)
        completed = int((df["status"] == "Completed").sum())
        cancelled = int((df["status"] == "Cancelled").sum())
        active_count = int(df["status"].isin(["Waiting","In Consultation"]).sum())
        rate = (completed / total * 100) if total else None
        c = st.columns(5)
        with c[0]: metric("Registered patients", db.table_counts()["total_patients"])
        with c[1]: metric("Appointments in range", total)
        with c[2]: metric("Completed", completed)
        with c[3]: metric("Cancelled", cancelled)
        with c[4]: metric("Completion rate", f"{rate:.1f}%" if rate is not None else "N/A")
        st.write(f"**Active queue records in selected period:** {active_count}")
        measured = df.dropna(subset=["Measured wait (min)"]) if "Measured wait (min)" in df else pd.DataFrame()
        durations = df.dropna(subset=["Consultation duration (min)"]) if "Consultation duration (min)" in df else pd.DataFrame()
        x1,x2 = st.columns(2)
        with x1:
            st.metric("Average measured waiting time", safe_minutes(measured["Measured wait (min)"].mean() if not measured.empty else None))
        with x2:
            st.metric("Average consultation duration", safe_minutes(durations["Consultation duration (min)"].mean() if not durations.empty else None))
        p1,p2 = st.columns(2)
        with p1:
            dept = df.groupby(["department","status"]).size().reset_index(name="Appointments")
            st.plotly_chart(px.bar(dept, x="department", y="Appointments", color="status", barmode="stack", title="Department-wise appointment status"), use_container_width=True)
        with p2:
            daily = df.groupby("appointment_date").size().reset_index(name="Appointments")
            st.plotly_chart(px.line(daily, x="appointment_date", y="Appointments", markers=True, title="Daily appointment trend"), use_container_width=True)
        df["month"] = df["appointment_date"].str.slice(0,7)
        monthly = df.groupby("month").size().reset_index(name="Appointments")
        st.plotly_chart(px.bar(monthly, x="month", y="Appointments", title="Monthly appointment trend"), use_container_width=True)
        if not measured.empty:
            wait_dept = measured.groupby("department")["Measured wait (min)"].mean().reset_index()
            st.plotly_chart(px.bar(wait_dept, x="department", y="Measured wait (min)", title="Average measured waiting time by department"), use_container_width=True)
        else:
            st.info("Waiting-time analytics need records with both check-in and consultation-start timestamps.")
        export_button(df, "carequeue_analytics.csv", "Download analytics CSV")

elif page == "Patient Records":
    st.subheader("Patient records")
    search = st.text_input("Search by patient name or patient ID")
    patients = db.get_patients(search)
    if not patients:
        st.info("No patient records found.")
    else:
        p_df = pd.DataFrame(db.rows_to_dicts(patients))
        # Hide phone number from the overview; reveal only for a selected patient.
        st.dataframe(p_df[["patient_id","full_name","age","gender","created_at"]].rename(columns={"patient_id":"Patient ID","full_name":"Patient","age":"Age","gender":"Gender","created_at":"Registered at"}), use_container_width=True, hide_index=True)
        export_button(p_df[["patient_id","full_name","age","gender","created_at"]], "carequeue_patient_index.csv", "Export patient index")
        options = {f"#{p['patient_id']} — {p['full_name']}":p for p in patients}
        chosen_label = st.selectbox("View or update a patient", list(options))
        chosen = options[chosen_label]
        st.caption(f"Patient ID: {chosen['patient_id']} · Phone: {chosen['phone']}")
        with st.form("edit_patient_form"):
            new_name = st.text_input("Full name", value=chosen["full_name"])
            col1,col2 = st.columns(2)
            new_age = col1.number_input("Age", min_value=0, max_value=120, value=int(chosen["age"]))
            genders = ["Prefer not to say", "Female", "Male", "Non-binary", "Other"]
            new_gender = col2.selectbox("Gender", genders, index=genders.index(chosen["gender"]) if chosen["gender"] in genders else 0)
            new_phone = st.text_input("Phone number", value=chosen["phone"])
            update = st.form_submit_button("Update patient details")
        if update:
            try:
                db.update_patient(chosen["patient_id"], new_name, new_age, new_gender, new_phone)
                st.success("Patient details updated.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        history = [r for r in db.get_appointments() if r["patient_id"] == chosen["patient_id"]]
        st.subheader("Appointment history")
        if history:
            hist_df = appt_frame(history)
            cols = ["appointment_id","appointment_date","appointment_time","department","doctor","status","check_in_at","consultation_start_at","consultation_end_at","Measured wait (min)","Consultation duration (min)"]
            st.dataframe(hist_df[[c for c in cols if c in hist_df]].rename(columns={"appointment_id":"Appointment ID","appointment_date":"Date","appointment_time":"Time","department":"Department","doctor":"Doctor","status":"Status","check_in_at":"Checked in","consultation_start_at":"Consultation started","consultation_end_at":"Consultation ended"}), use_container_width=True, hide_index=True)
            export_button(hist_df, f"patient_{chosen['patient_id']}_history.csv", "Export selected patient's history")
        else:
            st.caption("No appointments recorded for this patient.")

st.divider()
st.caption("CareQueue educational prototype. Waiting times are measured only when both check-in and consultation-start timestamps exist. Times use the server's local clock.")
@st.cache_data
def load_data():
    return pd.read_csv("sample_patients.csv")

df = load_data()
today = pd.Timestamp.today().date()

df["appointment_date"] = pd.to_datetime(
    df["appointment_date"]
).dt.date

today_df = df[df["appointment_date"] == today]

col1, col2, col3, col4 = st.columns(4)

col1.metric("Today's Appointments", len(today_df))

col2.metric(
    "Waiting Patients",
    len(today_df[today_df["status"] == "Checked In"])
)

col3.metric(
    "Completed",
    len(today_df[today_df["status"] == "Completed"])
)

col4.metric(
    "Urgent Cases",
    len(today_df[today_df["priority"] == "Urgent"])
)
st.subheader("Appointments by Department")

department_counts = df["department"].value_counts()
st.bar_chart(department_counts)

st.subheader("Appointment Status")

status_counts = df["status"].value_counts()
st.bar_chart(status_counts)

st.subheader("Patient Records")

st.dataframe(df, use_container_width=True, hide_index=True)

st.download_button(
    "Download Patient Data",
    data=df.to_csv(index=False),
    file_name="patient_records.csv",
    mime="text/csv"
)
