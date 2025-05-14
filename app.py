import streamlit as st
import sqlite3
from datetime import datetime

# ----------- SQLite DB Setup --------------
conn = sqlite3.connect('phdcci.db', check_same_thread=False)
cursor = conn.cursor()

# ----------- Tables Initialization --------
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
    applied_at TEXT
)''')
conn.commit()

# ---------- Utility Functions -------------
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

def get_all_jobs():
    cursor.execute("SELECT * FROM job_posts")
    return cursor.fetchall()

def apply_to_job(student, job_id):
    cursor.execute("INSERT INTO applications (student, job_id, applied_at) VALUES (?, ?, ?)",
                   (student, job_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def get_student_applications(student):
    cursor.execute("SELECT job_id, applied_at FROM applications WHERE student = ?", (student,))
    return cursor.fetchall()

# ------------- Streamlit UI ---------------
def main():
    st.set_page_config("Internship & Placement Portal", layout="wide")
    st.title("🎓 Internship & Placement Portal")

    menu = ["Login", "Register"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Register":
        st.subheader("Create Account")
        new_user = st.text_input("Username")
        new_pass = st.text_input("Password", type="password")
        role = st.selectbox("Role", ["Student", "Company", "Admin"])
        if st.button("Register"):
            success, msg = register_user(new_user, new_pass, role)
            st.success(msg) if success else st.error(msg)

    elif choice == "Login":
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = authenticate_user(username, password)
            if user:
                st.session_state.user = {
                    "username": user[0],
                    "role": user[2]
                }
                st.success(f"Welcome {user[0]} ({user[2]})")
            else:
                st.error("Invalid login credentials.")

    # ---- Dashboard ----
    if "user" in st.session_state:
        user = st.session_state.user
        st.header(f"{user['role']} Dashboard")

        if st.button("Logout"):
            del st.session_state.user
            st.experimental_rerun()

        if user["role"] == "Student":
            st.subheader("Browse Jobs")
            jobs = get_all_jobs()
            for job in jobs:
                st.markdown(f"**{job[2]}** at *{job[1]}*")
                st.write(job[3])
                if st.button(f"Apply to {job[2]}", key=f"apply_{job[0]}"):
                    apply_to_job(user["username"], job[0])
                    st.success("Applied successfully!")

            st.subheader("Your Applications")
            for job_id, applied_at in get_student_applications(user["username"]):
                cursor.execute("SELECT title, company FROM job_posts WHERE id = ?", (job_id,))
                job = cursor.fetchone()
                if job:
                    st.write(f"✔ Applied to **{job[0]}** at *{job[1]}* on {applied_at}")

        elif user["role"] == "Company":
            st.subheader("Post a Job")
            title = st.text_input("Job Title")
            description = st.text_area("Job Description")
            if st.button("Post Job"):
                post_job(user["username"], title, description)
                st.success("Job posted.")

            st.subheader("Your Posted Jobs")
            cursor.execute("SELECT title, description FROM job_posts WHERE company = ?", (user["username"],))
            jobs = cursor.fetchall()
            for j in jobs:
                st.write(f"- {j[0]} — {j[1]}")

        elif user["role"] == "Admin":
            st.subheader("All Users")
            cursor.execute("SELECT * FROM users")
            for u in cursor.fetchall():
                st.write(f"- {u[0]} ({u[2]})")

            st.subheader("All Job Posts")
            for job in get_all_jobs():
                st.write(f"- {job[2]} at {job[1]}")

            st.subheader("All Applications")
            cursor.execute("SELECT student, job_id FROM applications")
            for a in cursor.fetchall():
                cursor.execute("SELECT title, company FROM job_posts WHERE id = ?", (a[1],))
                job = cursor.fetchone()
                if job:
                    st.write(f"{a[0]} applied to {job[0]} at {job[1]}")

if __name__ == '__main__':
    main()
