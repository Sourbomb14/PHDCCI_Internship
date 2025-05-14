import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Database connection
conn = sqlite3.connect('phdcci.db', check_same_thread=False)
cursor = conn.cursor()

# Initialize tables
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT,
    role TEXT
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS job_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT,
    title TEXT,
    description TEXT,
    posted_at TEXT
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student TEXT,
    job_id INTEGER,
    applied_at TEXT,
    approved TEXT DEFAULT 'Pending'
)''')
conn.commit()

# Helper functions
def register_user(username, password, role):
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        return False, "Username already exists."
    cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (username, password, role))
    conn.commit()
    return True, "Registration successful."

def authenticate_user(username, password):
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    return cursor.fetchone()

def post_job(company, title, description):
    cursor.execute("INSERT INTO job_posts (company, title, description, posted_at) VALUES (?, ?, ?, ?)",
                   (company, title, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def get_jobs():
    cursor.execute("SELECT * FROM job_posts")
    return cursor.fetchall()

def apply_to_job(student, job_id):
    cursor.execute("INSERT INTO applications (student, job_id, applied_at) VALUES (?, ?, ?)",
                   (student, job_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def get_student_applications(student):
    cursor.execute("SELECT job_id, approved, applied_at FROM applications WHERE student = ?", (student,))
    return cursor.fetchall()

def get_applications_for_company(company):
    cursor.execute("SELECT a.id, a.student, a.job_id, a.approved, j.title FROM applications a JOIN job_posts j ON a.job_id = j.id WHERE j.company = ?", (company,))
    return cursor.fetchall()

def get_all_applications():
    cursor.execute("SELECT * FROM applications")
    return cursor.fetchall()

def approve_application(app_id):
    cursor.execute("UPDATE applications SET approved = 'Approved' WHERE id = ?", (app_id,))
    conn.commit()

def export_to_excel():
    query = '''
    SELECT a.id, a.student, a.job_id, j.title, j.company, a.approved, a.applied_at
    FROM applications a
    JOIN job_posts j ON a.job_id = j.id
    '''
    df = pd.read_sql_query(query, conn)
    df.to_excel("phdcci_export.xlsx", index=False)
    return "phdcci_export.xlsx"

# Streamlit App
def main():
    st.set_page_config("Internship & Placement Portal", layout="wide")
    st.title("🎓 Internship & Placement Portal")

    if "user" not in st.session_state:
        st.subheader("Login or Register")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Student Login"):
                st.session_state.login_role = "Student"
        with col2:
            if st.button("Company Login"):
                st.session_state.login_role = "Company"
        with col3:
            if st.button("Admin Login"):
                st.session_state.login_role = "Admin"
        with col4:
            if st.button("Register"):
                st.session_state.login_role = "Register"

    if "login_role" in st.session_state:
        role = st.session_state.login_role
        st.subheader(f"{role} Portal")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if role == "Register":
            reg_role = st.selectbox("Register as", ["Student", "Company"])
            if st.button("Register"):
                success, msg = register_user(username, password, reg_role)
                st.success(msg) if success else st.error(msg)
        else:
            if st.button("Login"):
                user = authenticate_user(username, password)
                if user and user[2] == role:
                    st.session_state.user = {"username": user[0], "role": user[2]}
                    del st.session_state["login_role"]
                    st.success("Login successful.")
                else:
                    st.error("Invalid credentials or role mismatch.")

    # User Logged In
    if "user" in st.session_state:
        user = st.session_state.user
        st.subheader(f"Welcome, {user['username']} ({user['role']})")

        if st.button("Logout"):
            del st.session_state["user"]
            st.experimental_rerun()

        # Student View
        if user["role"] == "Student":
            jobs = get_jobs()
            st.subheader("Available Internships")
            for job in jobs:
                st.markdown(f"**{job[2]}** at *{job[1]}*")
                st.write(job[3])
                if st.button(f"Apply to {job[2]}", key=f"apply_{job[0]}"):
                    apply_to_job(user["username"], job[0])
                    st.success("Applied successfully.")

            st.subheader("Your Applications")
            for job_id, approved, date in get_student_applications(user["username"]):
                cursor.execute("SELECT title FROM job_posts WHERE id = ?", (job_id,))
                job = cursor.fetchone()
                if job:
                    st.write(f"{job[0]} — Status: {approved} on {date}")

        # Company View
        elif user["role"] == "Company":
            st.subheader("Post New Internship")
            title = st.text_input("Job Title")
            description = st.text_area("Job Description")
            if st.button("Post Job"):
                post_job(user["username"], title, description)
                st.success("Posted successfully.")

            st.subheader("Applications to Your Jobs")
            apps = get_applications_for_company(user["username"])
            for app_id, student, job_id, approved, title in apps:
                st.write(f"{student} applied to {title} — Status: {approved}")
                if approved == "Pending" and st.button(f"Approve #{app_id}", key=f"approve_{app_id}"):
                    approve_application(app_id)
                    st.success(f"Application #{app_id} approved.")
                    st.experimental_rerun()

        # Admin View
        elif user["role"] == "Admin":
            st.subheader("Review Applications")
            apps = get_all_applications()
            for app in apps:
                app_id, student, job_id, applied_at, approved = app
                cursor.execute("SELECT title, company FROM job_posts WHERE id = ?", (job_id,))
                job = cursor.fetchone()
                if job:
                    st.write(f"{student} -> {job[0]} at {job[1]} | Status: {approved}")
                    if approved == "Pending":
                        if st.button(f"Approve #{app_id}", key=f"approve_{app_id}"):
                            approve_application(app_id)
                            st.success(f"Application #{app_id} approved.")
                            st.experimental_rerun()

            st.subheader("Download Full Database")
            if st.button("Export to Excel"):
                file_path = export_to_excel()
                with open(file_path, "rb") as f:
                    st.download_button("Download Excel", f, file_name="phdcci_applications.xlsx")

if __name__ == "__main__":
    main()
