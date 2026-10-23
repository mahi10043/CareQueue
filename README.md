# CareQueue — Hospital Appointment and Queue Management System

CareQueue is an educational Streamlit prototype for patient registration, appointment management, consultation queues, and timestamp-based waiting-time analytics. Use fictional data only.

## Features

- Staff login using a PBKDF2 password hash; no default password is embedded in the source.
- SQLite database and schema initialization at startup.
- Patient registration and editing.
- Appointment creation, search, filtering, editing, cancellation, and CSV export.
- Check-in queue with queue numbers, consultation start/end timestamps, and guarded status transitions.
- Analytics and charts calculated from saved records.
- Responsive Streamlit interface with a healthcare-inspired theme.
- Basic 15-minute idle timeout checked on app reruns.

## Requirements

- Python 3.13 (64-bit recommended)
- Windows Command Prompt or a compatible terminal

## Windows installation

Open Command Prompt and run:

```bat
py -3.13 --version
mkdir CareQueue
cd CareQueue
```

Extract the full ZIP, including the `.streamlit` folder. Keep `.streamlit/config.toml` beside the project files so the light theme and readable form labels are applied. Then:

```bat
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configure the first administrator in the same Command Prompt window **before the first launch**:

```bat
set CAREQUEUE_ADMIN_USERNAME=admin
set CAREQUEUE_ADMIN_PASSWORD=Choose-A-Long-Unique-Password
```

Use a private password with at least 10 characters. Do not share it or commit it. The staff account is created only if the username does not already exist. Environment variables are local to that Command Prompt session.

Run:

```bat
python -m streamlit run app.py
```

Streamlit normally opens the dashboard automatically. If not, open the local URL shown in the terminal, typically `http://localhost:8501`.

To stop the server, press `Ctrl+C`. The local `carequeue.db` file is created automatically in the project directory and persists across restarts on that computer.

## Testing checklist

Use fictional test patients only.

1. Sign in using the administrator credentials configured above.
2. Register a fictional patient and create an appointment for today.
3. Confirm that the appointment appears on Dashboard and Appointments.
4. Open Patient Queue and check in the appointment.
5. Start the consultation, then complete it.
6. Confirm that timestamps and measured waiting time appear in analytics/history.
7. Try a duplicate patient/doctor/date/time appointment and confirm it is rejected.
8. Try cancelling a completed appointment and confirm the status guard rejects it.
9. Export filtered appointments and open the CSV.
10. Restart the app and verify local records remain available.

These are manual test instructions, not a claim that automated tests have been run.

## Common Windows troubleshooting

- **`py` is not recognized:** install Python 3.13 from the official Python website and enable the Python Launcher / PATH option.
- **`No module named streamlit`:** activate `.venv` and run `pip install -r requirements.txt`.
- **`streamlit` is not recognized:** use `python -m streamlit run app.py`.
- **Port 8501 is busy:** run `python -m streamlit run app.py --server.port 8502`.
- **Database locked:** close other app processes using the same database and retry. SQLite is not designed for heavy concurrent writes.
- **Login does not work:** set the environment variables before the first launch, then check that the username and password were entered correctly. The configured account is inserted only once.
- **Forgotten local administrator password:** for this prototype, arrange a controlled local recovery process rather than publishing or exposing credentials. Do not delete a database containing records merely to reset access.

## GitHub upload

Create an empty GitHub repository, then from the project folder:

```bat
git init
git add app.py db.py schema.sql requirements.txt .gitignore README.md
git commit -m "Initial CareQueue application"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Replace the example remote URL with your repository URL. Never use `git add .` without checking `git status` first; the database and secret files must remain untracked.

## Streamlit Community Cloud

1. Push the source files to GitHub.
2. Sign in to Streamlit Community Cloud and create a new app.
3. Select the repository, branch `main`, and main file `app.py`.
4. Deploy the app.
5. In the app's settings, open **Secrets** and add the following TOML values for the initial staff account (choose your own strong password). Do not commit secrets to GitHub:

```toml
CAREQUEUE_ADMIN_USERNAME = "admin"
CAREQUEUE_ADMIN_PASSWORD = "replace-with-a-long-unique-password"
```

The account is created on the first app startup when these values are present and the username does not already exist. Changing the secret later does not automatically change an existing account's password.
6. Configure `CAREQUEUE_DB_PATH` only if the selected host provides a suitable writable persistent mount.

**Important persistence warning:** a SQLite file on an ephemeral cloud filesystem may be reset when the app restarts or redeploys. A single local SQLite file is not a reliable shared database for multi-user cloud hosting. For durable cloud use, migrate to a managed database such as PostgreSQL and configure secure database credentials through the host's secrets manager. Do not store real patient data in a public demonstration deployment.

## Data model

- `patients`: demographics and contact information.
- `appointments`: department, doctor, appointment schedule, status, queue number, and event timestamps.
- `staff`: usernames, salted password hashes, role, and active flag.

Foreign keys link appointments to patients. SQL statements use placeholders for user-supplied values. Database schema initialization is performed automatically by `db.init_db()`.

## Waiting-time definitions

- **Measured waiting time:** `consultation_start_at - check_in_at`, in minutes, when both timestamps exist.
- **Consultation duration:** `consultation_end_at - consultation_start_at`, in minutes, when both timestamps exist.
- No waiting-time value is fabricated for appointments that lack the required timestamps. Appointment time is not treated as a measured check-in time.

## Security limitations

This is not a certified clinical or hospital system. The 15-minute timeout is checked when Streamlit reruns; it is not a robust server-side session-management system. Role-based access is basic, and this sample does not implement a full audit log, password reset, CSRF/session hardening, encryption-at-rest, backups, consent management, or regulatory compliance. Before any real use, obtain professional security and privacy review, use a managed database and secure authentication, implement auditing and backups, minimize access to patient information, and comply with applicable laws and institutional policies.
