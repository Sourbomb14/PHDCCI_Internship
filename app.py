import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from urllib.parse import quote_plus
from datetime import datetime

# --------- MongoDB Setup (Safe URI) ---------
username = quote_plus("PHDCCI_Internship")
password = quote_plus("Phd@123")  # Special characters safely encoded

uri = f"mongodb+srv://{username}:{password}@cluster0.ht97vch.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Connect to MongoDB
client = MongoClient(uri, server_api=ServerApi('1'))
try:
    client.admin.command('ping')
except Exception as e:
    st.error("❌ MongoDB connection failed.")
    st.stop()

db = client["phdcci"]
users_col = db["users"]
jobs_col = db["job_posts"]
apps_col = db["applications"]

# --------- Authentication ---------
def register_user(username, password, role):
    if users_col.find_one({"username": username}):
        return False, "User already exists."
    users_col.insert_one({"username": username, "password": password, "role": role})
    return True, "Registration successful!"

def authenticate(username, password):
    user = users_col.find_one({"username": username, "password": password})
    return user

# --------- Job Functions ---------
def post_job(company, title, description):
    jobs_col.insert_one({
        "company": company,
        "title": title,
        "description": description,
        "posted_at": datetime.now()
    })

def get_all_jobs():
    return list(jobs_col.find())

def apply_for_job(student, job_id):
    apps_col.insert_one({
        "student": student,
        "job_id": job_id,
        "applied_at": datetime.now()
    })

def get_applications_by_student(student):
    return list(apps_col.find({"student": student}))

# --------- UI ---------
def main():
    st.set_page_config("Internship & Placement Portal", layout="wide")
    st.title("📘 Internship & Placement Portal")

    menu = ["Login", "Register"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Register":
        st.subheader("Create New Account")
        new_user = st.text_input("Username")
        new_pass = st.text_input("Password", type="password")
        role = st.selectbox("Register as", ["Student", "Company", "Admin"])
        if st.button("Register"):
            success, msg = register_user(new_user, new_pass, role)
            st.success(msg) if success else st.error(msg)

    elif choice == "Login":
        st.subheader("Login to your Account")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = authenticate(username, password)
            if user:
                st.session_state.user = user
                st.success(f"Logged in as {user['username']} ({user['role']})")
            else:
                st.error("Invalid credentials")

    # ---------- Dashboards ----------
    if "user" in st.session_state:
        user = st.session_state.user
        role = user["role"]

        if st.button("Logout"):
            del st.session_state.user
            st.experimental_rerun()

        st.header(f"{role} Dashboard")

        if role == "Student":
            jobs = get_all_jobs()
            st.subheader("Available Jobs")
            for job in jobs:
                with st.expander(f"{job['title']} at {job['company']}"):
                    st.write(job["description"])
                    if st.button(f"Apply for {job['title']}", key=str(job["_id"])):
                        apply_for_job(user["username"], job["_id"])
                        st.success("Applied successfully!")

            st.subheader("Your Applications")
            apps = get_applications_by_student(user["username"])
            for app in apps:
                job = jobs_col.find_one({"_id": app["job_id"]})
                st.write(f"- {job['title']} at {job['company']} (Applied on {app['applied_at']})")

        elif role == "Company":
            st.subheader("Post a Job")
            title = st.text_input("Job Title")
            desc = st.text_area("Job Description")
            if st.button("Post Job"):
                post_job(user["username"], title, desc)
                st.success("Job posted!")

            st.subheader("Your Posted Jobs")
            posted = jobs_col.find({"company": user["username"]})
            for job in posted:
                st.markdown(f"**{job['title']}** — {job['description']}")

        elif role == "Admin":
            st.subheader("User List")
            users = users_col.find()
            for u in users:
                st.write(f"- {u['username']} ({u['role']})")

            st.subheader("All Job Posts")
            jobs = get_all_jobs()
            for job in jobs:
                st.write(f"- {job['title']} at {job['company']}")

            st.subheader("All Applications")
            apps = apps_col.find()
            for app in apps:
                st.write(f"{app['student']} applied to job ID {app['job_id']}")

if __name__ == "__main__":
    main()
