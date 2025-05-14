import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from urllib.parse import quote_plus
from datetime import datetime

# ------------- MongoDB Secure Connection ------------------
# Encode credentials to handle special characters like @
username = quote_plus("PHDCCI_Internship")
password = quote_plus("Phd@123")  # '@' becomes '%40'

# MongoDB URI (replace 'cluster0.ht97vch.mongodb.net' if needed)
uri = f"mongodb+srv://{username}:{password}@cluster0.ht97vch.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Connect to MongoDB
try:
    client = MongoClient(uri, server_api=ServerApi('1'))
    client.admin.command('ping')
    db = client["phdcci"]
    users_col = db["users"]
    jobs_col = db["job_posts"]
    apps_col = db["applications"]
except Exception as e:
    st.error("❌ MongoDB connection failed. Please check credentials or IP access.")
    st.stop()

# ------------- Utility Functions --------------------------
def register_user(username, password, role):
    if users_col.find_one({"username": username}):
        return False, "Username already exists."
    users_col.insert_one({"username": username, "password": password, "role": role})
    return True, "Registration successful."

def authenticate_user(username, password):
    return users_col.find_one({"username": username, "password": password})

def post_job(company, title, description):
    jobs_col.insert_one({
        "company": company,
        "title": title,
        "description": description,
        "posted_at": datetime.now()
    })

def get_all_jobs():
    return list(jobs_col.find())

def apply_to_job(student, job_id):
    apps_col.insert_one({
        "student": student,
        "job_id": job_id,
        "applied_at": datetime.now()
    })

def get_student_applications(student):
    return list(apps_col.find({"student": student}))

# ------------- Streamlit App --------------------------
def main():
    st.set_page_config("Internship & Placement Portal", layout="wide")
    st.title("🎓 Internship & Placement Portal")

    menu = ["Login", "Register"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Register":
        st.subheader("Create a New Account")
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
                st.session_state.user = user
                st.success(f"Welcome, {user['username']} ({user['role']})")
            else:
                st.error("Invalid username or password.")

    # ----------- Dashboard After Login ------------
    if "user" in st.session_state:
        user = st.session_state.user
        role = user["role"]

        if st.button("Logout"):
            del st.session_state.user
            st.experimental_rerun()

        st.header(f"{role} Dashboard")

        if role == "Student":
            st.subheader("Available Jobs")
            jobs = get_all_jobs()
            for job in jobs:
                with st.expander(f"{job['title']} at {job['company']}"):
                    st.write(job["description"])
                    if st.button(f"Apply for {job['title']}", key=str(job["_id"])):
                        apply_to_job(user["username"], job["_id"])
                        st.success("Applied successfully!")

            st.subheader("Your Applications")
            apps = get_student_applications(user["username"])
            for app in apps:
                job = jobs_col.find_one({"_id": app["job_id"]})
                st.write(f"- {job['title']} at {job['company']} (Applied on {app['applied_at'].strftime('%Y-%m-%d')})")

        elif role == "Company":
            st.subheader("Post a Job")
            title = st.text_input("Job Title")
            desc = st.text_area("Job Description")
            if st.button("Post Job"):
                post_job(user["username"], title, desc)
                st.success("Job posted successfully.")

            st.subheader("Your Posted Jobs")
            posted_jobs = jobs_col.find({"company": user["username"]})
            for job in posted_jobs:
                st.write(f"- {job['title']} — {job['description']}")

        elif role == "Admin":
            st.subheader("All Users")
            for u in users_col.find():
                st.write(f"- {u['username']} ({u['role']})")

            st.subheader("All Jobs")
            for job in get_all_jobs():
                st.write(f"- {job['title']} at {job['company']}")

            st.subheader("All Applications")
            for app in apps_col.find():
                job = jobs_col.find_one({"_id": app["job_id"]})
                if job:
                    st.write(f"{app['student']} applied to {job['title']} at {job['company']}")

if __name__ == "__main__":
    main()
