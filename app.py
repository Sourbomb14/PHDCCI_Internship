import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import os
import logging
from datetime import datetime
from io import BytesIO
import re
import base64
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("phdcci-portal")

# Create data directory if it doesn't exist
data_dir = Path("data")
data_dir.mkdir(exist_ok=True)

# Database connection with proper error handling
def get_db_connection():
    try:
        conn = sqlite3.connect(data_dir / 'phdcci.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        st.error(f"Database error: {e}")
        return None

# Initialize database schema
def init_db():
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Users table with hashed passwords and additional fields
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT UNIQUE,
            full_name TEXT,
            organization TEXT,
            created_at TEXT,
            last_login TEXT
        )''')
        
        # Job posts with more detailed information
        cursor.execute('''CREATE TABLE IF NOT EXISTS job_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT,
            job_type TEXT,
            duration TEXT,
            stipend TEXT,
            requirements TEXT,
            deadline TEXT,
            posted_at TEXT,
            status TEXT DEFAULT 'Active'
        )''')
        
        # Applications with more detailed tracking
        cursor.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            resume_path TEXT,
            cover_letter TEXT,
            skills TEXT,
            applied_at TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            feedback TEXT,
            reviewed_at TEXT,
            reviewed_by TEXT,
            FOREIGN KEY (student) REFERENCES users (username),
            FOREIGN KEY (job_id) REFERENCES job_posts (id)
        )''')
        
        # Create admin user if it doesn't exist
        default_admin_pw = "admin123"  # Would be set via environment variable in production
        admin_hash = hashlib.sha256(default_admin_pw.encode()).hexdigest()
        
        cursor.execute("SELECT username FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, email, created_at) VALUES (?, ?, ?, ?, ?)",
                ('admin', admin_hash, 'Admin', 'admin@phdcci.org', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            logger.info("Created default admin user")
            
        conn.commit()
        logger.info("Database initialized successfully")
            
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
        st.error(f"Database setup error: {e}")
    finally:
        if conn:
            conn.close()

# Helper functions with error handling and validation
def hash_password(password):
    """Create a SHA-256 hash of the password"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    """Simple email validation"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

def register_user(username, password, role, email, full_name="", organization=""):
    """Register a new user with validation"""
    if not username or not password or not role or not email:
        return False, "All required fields must be filled."
        
    if not validate_email(email):
        return False, "Please enter a valid email address."
        
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    
    try:
        conn = get_db_connection()
        if not conn:
            return False, "Database connection error."
            
        cursor = conn.cursor()
        
        # Check if username already exists
        cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return False, "Username already exists."
            
        # Check if email already exists
        cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            return False, "Email already registered."
            
        # Hash the password
        password_hash = hash_password(password)
        
        # Insert new user
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, email, full_name, organization, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (username, password_hash, role, email, full_name, organization, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        logger.info(f"New user registered: {username} as {role}")
        return True, "Registration successful! You can now log in."
        
    except sqlite3.Error as e:
        logger.error(f"Registration error: {e}")
        return False, f"Database error during registration: {e}"
    finally:
        if conn:
            conn.close()

def authenticate_user(username, password):
    """Authenticate user and update last login time"""
    if not username or not password:
        return None, "Username and password required."
        
    try:
        conn = get_db_connection()
        if not conn:
            return None, "Database connection error."
            
        cursor = conn.cursor()
        
        # Hash the provided password
        password_hash = hash_password(password)
        
        # Check credentials
        cursor.execute("SELECT * FROM users WHERE username = ? AND password_hash = ?", 
                      (username, password_hash))
        user = cursor.fetchone()
        
        if user:
            # Update last login timestamp
            cursor.execute("UPDATE users SET last_login = ? WHERE username = ?", 
                          (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username))
            conn.commit()
            logger.info(f"User logged in: {username}")
            return dict(user), "Login successful."
        else:
            logger.warning(f"Failed login attempt for username: {username}")
            return None, "Invalid username or password."
            
    except sqlite3.Error as e:
        logger.error(f"Authentication error: {e}")
        return None, f"Database error during login: {e}"
    finally:
        if conn:
            conn.close()

def post_job(company, title, description, location="", job_type="", duration="", stipend="", requirements="", deadline=""):
    """Post a new job with validation"""
    if not company or not title or not description:
        return False, "Company, title and description are required."
        
    try:
        conn = get_db_connection()
        if not conn:
            return False, "Database connection error."
            
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO job_posts (
                company, title, description, location, job_type, duration, 
                stipend, requirements, deadline, posted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company, title, description, location, job_type, duration, 
            stipend, requirements, deadline, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        
        conn.commit()
        job_id = cursor.lastrowid
        logger.info(f"New job posted: {title} by {company} (ID: {job_id})")
        return True, f"Job posted successfully (ID: {job_id})."
        
    except sqlite3.Error as e:
        logger.error(f"Job posting error: {e}")
        return False, f"Database error posting job: {e}"
    finally:
        if conn:
            conn.close()

def get_jobs(company=None, status="Active"):
    """Get jobs with optional filtering by company or status"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        if company:
            cursor.execute("""
                SELECT * FROM job_posts 
                WHERE company = ? AND (status = ? OR ? = 'All')
                ORDER BY posted_at DESC
            """, (company, status, status))
        else:
            cursor.execute("""
                SELECT * FROM job_posts 
                WHERE status = ? OR ? = 'All'
                ORDER BY posted_at DESC
            """, (status, status))
            
        jobs = [dict(row) for row in cursor.fetchall()]
        return jobs
        
    except sqlite3.Error as e:
        logger.error(f"Error fetching jobs: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_job_by_id(job_id):
    """Get job details by ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_posts WHERE id = ?", (job_id,))
        job = cursor.fetchone()
        
        if job:
            return dict(job)
        return None
        
    except sqlite3.Error as e:
        logger.error(f"Error fetching job {job_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def apply_to_job(student, job_id, resume_path="", cover_letter="", skills=""):
    """Apply to a job with validation"""
    if not student or not job_id:
        return False, "Student and job ID are required."
        
    try:
        conn = get_db_connection()
        if not conn:
            return False, "Database connection error."
            
        cursor = conn.cursor()
        
        # Check if student has already applied to this job
        cursor.execute("SELECT id FROM applications WHERE student = ? AND job_id = ?", 
                      (student, job_id))
        if cursor.fetchone():
            return False, "You have already applied for this job."
            
        # Check if job exists and is active
        cursor.execute("SELECT id, status FROM job_posts WHERE id = ?", (job_id,))
        job = cursor.fetchone()
        if not job:
            return False, "Job not found."
        if job['status'] != 'Active':
            return False, "This job is no longer accepting applications."
            
        # Apply for the job
        cursor.execute("""
            INSERT INTO applications (
                student, job_id, resume_path, cover_letter, skills, applied_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            student, job_id, resume_path, cover_letter, skills,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        
        conn.commit()
        app_id = cursor.lastrowid
        logger.info(f"New application: Student {student} applied to job {job_id} (App ID: {app_id})")
        return True, "Application submitted successfully!"
        
    except sqlite3.Error as e:
        logger.error(f"Error applying to job: {e}")
        return False, f"Database error applying to job: {e}"
    finally:
        if conn:
            conn.close()

def get_student_applications(student):
    """Get all applications for a student with job details"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.*, j.title, j.company
            FROM applications a
            JOIN job_posts j ON a.job_id = j.id
            WHERE a.student = ?
            ORDER BY a.applied_at DESC
        """, (student,))
        
        applications = [dict(row) for row in cursor.fetchall()]
        return applications
        
    except sqlite3.Error as e:
        logger.error(f"Error fetching student applications: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_applications_for_company(company):
    """Get all applications for jobs posted by a company"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.*, j.title, j.company, u.full_name, u.email
            FROM applications a
            JOIN job_posts j ON a.job_id = j.id
            JOIN users u ON a.student = u.username
            WHERE j.company = ?
            ORDER BY a.applied_at DESC
        """, (company,))
        
        applications = [dict(row) for row in cursor.fetchall()]
        return applications
        
    except sqlite3.Error as e:
        logger.error(f"Error fetching company applications: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_all_applications():
    """Get all applications with details (admin only)"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.*, j.title, j.company, u.full_name, u.email
            FROM applications a
            JOIN job_posts j ON a.job_id = j.id
            JOIN users u ON a.student = u.username
            ORDER BY a.applied_at DESC
        """)
        
        applications = [dict(row) for row in cursor.fetchall()]
        return applications
        
    except sqlite3.Error as e:
        logger.error(f"Error fetching all applications: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_application_status(app_id, status, feedback="", reviewed_by=""):
    """Update application status with feedback"""
    try:
        conn = get_db_connection()
        if not conn:
            return False, "Database connection error."
            
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE applications 
            SET status = ?, feedback = ?, reviewed_at = ?, reviewed_by = ?
            WHERE id = ?
        """, (
            status, feedback, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            reviewed_by, app_id
        ))
        
        if cursor.rowcount == 0:
            return False, "Application not found."
            
        conn.commit()
        logger.info(f"Application {app_id} status updated to {status} by {reviewed_by}")
        return True, f"Application status updated to {status}."
        
    except sqlite3.Error as e:
        logger.error(f"Error updating application status: {e}")
        return False, f"Database error updating application: {e}"
    finally:
        if conn:
            conn.close()

def update_job_status(job_id, status):
    """Update job status (active/inactive)"""
    try:
        conn = get_db_connection()
        if not conn:
            return False, "Database connection error."
            
        cursor = conn.cursor()
        
        cursor.execute("UPDATE job_posts SET status = ? WHERE id = ?", (status, job_id))
        
        if cursor.rowcount == 0:
            return False, "Job not found."
            
        conn.commit()
        logger.info(f"Job {job_id} status updated to {status}")
        return True, f"Job status updated to {status}."
        
    except sqlite3.Error as e:
        logger.error(f"Error updating job status: {e}")
        return False, f"Database error updating job: {e}"
    finally:
        if conn:
            conn.close()

def export_to_excel(content_type="applications"):
    """Export data to Excel file"""
    try:
        conn = get_db_connection()
        if not conn:
            return None, "Database connection error."
            
        if content_type == "applications":
            query = '''
            SELECT 
                a.id as application_id, 
                a.student, 
                u.email as student_email,
                u.full_name as student_name,
                a.job_id, 
                j.title as job_title, 
                j.company, 
                a.status, 
                a.applied_at,
                a.reviewed_at,
                a.reviewed_by,
                a.feedback
            FROM applications a
            JOIN job_posts j ON a.job_id = j.id
            JOIN users u ON a.student = u.username
            ORDER BY a.applied_at DESC
            '''
            file_name = f"phdcci_applications_{datetime.now().strftime('%Y%m%d')}.xlsx"
            
        elif content_type == "jobs":
            query = '''
            SELECT 
                id as job_id,
                company,
                title,
                location,
                job_type,
                duration,
                stipend,
                deadline,
                status,
                posted_at
            FROM job_posts
            ORDER BY posted_at DESC
            '''
            file_name = f"phdcci_jobs_{datetime.now().strftime('%Y%m%d')}.xlsx"
            
        elif content_type == "users":
            query = '''
            SELECT 
                username,
                email,
                full_name,
                role,
                organization,
                created_at,
                last_login
            FROM users
            ORDER BY created_at DESC
            '''
            file_name = f"phdcci_users_{datetime.now().strftime('%Y%m%d')}.xlsx"
        else:
            return None, "Invalid export type."
            
        # Get the data
        df = pd.read_sql_query(query, conn)
        
        # Export to Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name=content_type.capitalize())
            
            # Auto-adjust columns' width
            worksheet = writer.sheets[content_type.capitalize()]
            for i, col in enumerate(df.columns):
                # Find the maximum length in the column
                max_len = max(
                    df[col].astype(str).map(len).max(),  # Length of largest item
                    len(str(col))  # Length of column name
                ) + 2  # Add a little extra space
                
                worksheet.set_column(i, i, max_len)  # Set column width
                
        output.seek(0)
        
        # Generate download link
        b64 = base64.b64encode(output.read()).decode()
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{file_name}">Download Excel File</a>'
        
        return href, "Export successful!"
        
    except Exception as e:
        logger.error(f"Error exporting to Excel: {e}")
        return None, f"Error exporting data: {e}"
    finally:
        if conn:
            conn.close()

# UI Components
def navigation_bar():
    """Create navigation menu based on user role"""
    if "user" in st.session_state:
        user = st.session_state.user
        role = user["role"]
        
        with st.sidebar:
            st.subheader(f"Welcome, {user['username']}")
            st.caption(f"Role: {role}")
            
            if role == "Student":
                st.sidebar.page_link("Browse Internships", "Browse Jobs", use_container_width=True)
                st.sidebar.page_link("My Applications", "My Applications", use_container_width=True)
                st.sidebar.page_link("Profile", "My Profile", use_container_width=True)
                
            elif role == "Company":
                st.sidebar.page_link("Post New Job", "Post New Job", use_container_width=True)
                st.sidebar.page_link("Manage Jobs", "Manage Jobs", use_container_width=True)
                st.sidebar.page_link("Review Applications", "Review Applications", use_container_width=True)
                st.sidebar.page_link("Profile", "Company Profile", use_container_width=True)
                
            elif role == "Admin":
                st.sidebar.page_link("Dashboard", "Admin Dashboard", use_container_width=True)
                st.sidebar.page_link("Manage Users", "Manage Users", use_container_width=True)
                st.sidebar.page_link("Manage Jobs", "Manage Jobs", use_container_width=True)
                st.sidebar.page_link("Manage Applications", "Review Applications", use_container_width=True)
                st.sidebar.page_link("Export Data", "Export Data", use_container_width=True)
                
            if st.sidebar.button("Logout", use_container_width=True):
                # Clear session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

def display_job_card(job, display_actions=True, user_role=None):
    """Display a job posting with consistent styling"""
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(job["title"])
            st.caption(f"Posted by: {job['company']} • {job['posted_at']}")
            
            if job.get("location"):
                st.caption(f"📍 {job['location']}")
                
            if job.get("job_type") and job.get("duration"):
                st.caption(f"🕒 {job['job_type']} • {job['duration']}")
                
            if job.get("stipend"):
                st.caption(f"💰 Stipend: {job['stipend']}")
                
        with col2:
            st.caption(f"Status: {job['status']}")
            if job.get("deadline"):
                st.caption(f"Deadline: {job['deadline']}")
        
        with st.expander("View Details"):
            st.write(job["description"])
            
            if job.get("requirements"):
                st.subheader("Requirements")
                st.write(job["requirements"])
        
        if display_actions and user_role:
            if user_role == "Student" and job["status"] == "Active":
                if st.button(f"Apply", key=f"apply_{job['id']}", use_container_width=True):
                    st.session_state.selected_job_id = job["id"]
                    st.session_state.page = "apply_job"
                    st.rerun()
                    
            elif user_role == "Company" or user_role == "Admin":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"Edit", key=f"edit_{job['id']}", use_container_width=True):
                        st.session_state.selected_job_id = job["id"]
                        st.session_state.page = "edit_job"
                        st.rerun()
                with col2:
                    if job["status"] == "Active":
                        if st.button(f"Deactivate", key=f"deactivate_{job['id']}", use_container_width=True):
                            success, msg = update_job_status(job["id"], "Inactive")
                            if success:
                                st.success(msg)
                            else:
                                st.error(msg)
                            st.rerun()
                    else:
                        if st.button(f"Activate", key=f"activate_{job['id']}", use_container_width=True):
                            success, msg = update_job_status(job["id"], "Active")
                            if success:
                                st.success(msg)
                            else:
                                st.error(msg)
                            st.rerun()

def display_application_card(app, user_role):
    """Display an application with appropriate actions"""
    job = get_job_by_id(app["job_id"])
    if not job:
        return
        
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if user_role == "Student":
                st.subheader(job["title"])
                st.caption(f"Company: {job['company']}")
            else:  # Company or Admin
                st.subheader(f"Application #{app['id']}")
                if "full_name" in app and app["full_name"]:
                    st.caption(f"Student: {app['full_name']} ({app['student']})")
                else:
                    st.caption(f"Student: {app['student']}")
                    
                if "email" in app:
                    st.caption(f"Email: {app['email']}")
                    
                st.caption(f"Applied for: {job['title']}")
        
        with col2:
            st.caption(f"Status: {app['status']}")
            st.caption(f"Applied on: {app['applied_at']}")
            
            if app["reviewed_at"]:
                st.caption(f"Reviewed on: {app['reviewed_at']}")
        
        with st.expander("Application Details"):
            if app.get("skills"):
                st.subheader("Skills")
                st.write(app["skills"])
                
            if app.get("cover_letter"):
                st.subheader("Cover Letter")
                st.write(app["cover_letter"])
                
            if app.get("feedback"):
                st.subheader("Feedback")
                st.write(app["feedback"])
        
        # Application actions for company/admin
        if user_role in ["Company", "Admin"] and app["status"] == "Pending":
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Approve", key=f"approve_{app['id']}", use_container_width=True):
                    st.session_state.selected_app_id = app["id"]
                    st.session_state.action_type = "approve"
                    st.session_state.page = "review_application"
                    st.rerun()
            with col2:
                if st.button("Reject", key=f"reject_{app['id']}", use_container_width=True):
                    st.session_state.selected_app_id = app["id"]
                    st.session_state.action_type = "reject"
                    st.session_state.page = "review_application"
                    st.rerun()

# Page routes
def login_page():
    """Login page with role selection"""
    st.subheader("Login")
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login", use_container_width=True):
            if username and password:
                user, msg = authenticate_user(username, password)
                if user:
                    st.session_state.user = user
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.error("Please enter both username and password")
    
    with col2:
        if st.button("Register Instead", use_container_width=True):
            st.session_state.page = "register"
            st.rerun()

def register_page():
    """User registration page"""
    st.subheader("Create New Account")
    
    with st.form("registration_form"):
        username = st.text_input("Username (Required)")
        email = st.text_input("Email (Required)")
        password = st.text_input("Password (Required)", type="password", help="Minimum 8 characters")
        confirm_password = st.text_input("Confirm Password", type="password")
        role = st.selectbox("Register as", ["Student", "Company"])
        
        if role == "Student":
            full_name = st.text_input("Full Name")
        else:  # Company
            full_name = ""
            organization = st.text_input("Company Name")
        
        submitted = st.form_submit_button("Register")
        
        if submitted:
            if not username or not password or not email:
                st.error("Username, password and email are required.")
            elif password != confirm_password:
                st.error("Passwords do not match.")
            elif len(password) < 8:
                st.error("Password must be at least 8 characters long.")
            else:
                if role == "Company":
                    success, msg = register_user(username, password, role, email, "", organization)
                else:
                    success, msg = register_user(username, password, role, email, full_name)
                    
                if success:
                    st.success(msg)
                    st.info("You can now login with your credentials.")
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.error(msg)
    
    if st.button("Go back to Login"):
        st.session_state.page = "login"
        st.rerun()

def student_browse_jobs_page():
    """Student job browsing page"""
    st.title("Available Internships & Jobs")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        search_query = st.text_input("Search by title or company")
    with col2:
        job_type_filter = st.selectbox("Job Type", ["All", "Internship", "Full-time", "Part-time"])
    
    # Get jobs
    jobs = get_jobs()
    
    # Apply filters
    if search_query:
        search_query = search_query.lower()
        jobs = [job for job in jobs if 
                search_query in job["title"].lower() or 
                search_query in job["company"].lower() or
                (job.get("description") and search_query in job["description"].lower())]
    
    if job_type_filter != "All":
        jobs = [job for job in jobs if job.get("job_type") == job_type_filter]
    
    # Display jobs
    if not jobs:
        st.info("No jobs match your criteria.")
    else:
        st.write(f"Found {len(jobs)} matching opportunities")
        for job in jobs:
            display_job_card(job, True, "Student")

def student_applications_page():
    """Student's applications page"""
    st.title("My Applications")
    
    applications = get_student_applications(st.session_state.user["username"])
    
    if not applications:
        st.info("You haven't applied to any jobs yet.")
    else:
        st.write(f"You have {len(applications)} applications")
        for app in applications:
            display_application_card(app, "Student")

def student_apply_job_page():
    """Student job application page"""
    job_id = st.session_state.get("selected_job_id")
    if not job_id:
        st.error("No job selected")
        st.session_state.page = "browse_jobs"
        st.rerun()
        
    job = get_job_by_id(job_id)
    if not job:
        st.error("Job not found")
        st.session_state.page = "browse_jobs"
        st.rerun()
        
    st.title(f"Apply for: {job['title']}")
    st.caption(f"Company: {job['company']}")
    
    with st.form("application_form"):
        skills = st.text_area("Relevant Skills", 
                            help="List your skills relevant to this position")
        cover_letter = st.text_area("Cover Letter", 
                                  help="Why are you interested in this position?")
        # Resume upload functionality would be added here
        
        submitted = st.form_submit_button("Submit Application")
        
        if submitted:
            success, msg = apply_to_job(
                st.session_state.user["username"], 
                job_id,
                "",  # resume_path (would be implemented with file uploader)
                cover_letter,
                skills
            )
            
            if success:
                st.success(msg)
                st.info("You can track your application status in 'My Applications'")
                st.session_state.page = "student_applications"
                st.rerun()
            else:
                st.error(msg)
    
    if st.button("Back to Jobs"):
        st.session_state.page = "browse_jobs"
        st.rerun()

def company_post_job_page():
    """Company job posting page"""
    st.title("Post New Internship/Job")
    
    with st.form("job_posting_form"):
        title = st.text_input("Job Title (Required)")
        job_type = st.selectbox("Job Type", ["Internship", "Full-time", "Part-time", "Contract"])
        
        col1, col2 = st.columns(2)
        with col1:
            location = st.text_input("Location")
        with col2:
            duration = st.text_input("Duration (e.g., 3 months, 1 year)")
            
        stipend = st.text_input("Stipend/Salary")
        deadline = st.date_input("Application Deadline")
        
        description = st.text_area("Job Description (Required)", 
                                help="Provide detailed information about the role")
        requirements = st.text_area("Requirements", 
                                  help="Education, skills, experience required")
        
        submitted = st.form_submit_button("Post Job")
        
        if submitted:
            if not title or not description:
                st.error("Title and description are required fields.")
            else:
                success, msg = post_job(
                    st.session_state.user["username"],  # company name = username
                    title,
                    description,
                    location,
                    job_type,
                    duration,
                    stipend,
                    requirements,
                    deadline.strftime("%Y-%m-%d") if deadline else ""
                )
                
                if success:
                    st.success(msg)
                    st.session_state.page = "manage_jobs"
                    st.rerun()
                else:
                    st.error(msg)

def company_manage_jobs_page():
    """Company job management page"""
    st.title("Manage Your Job Postings")
    
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Status", ["Active", "Inactive", "All"])
    with col2:
        if st.button("Post New Job", use_container_width=True):
            st.session_state.page = "post_job"
            st.rerun()
    
    # Get company's jobs
    jobs = get_jobs(company=st.session_state.user["username"], status=status_filter)
    
    if not jobs:
        st.info(f"No {status_filter.lower()} job postings found.")
    else:
        st.write(f"Found {len(jobs)} job postings")
        for job in jobs:
            display_job_card(job, True, "Company")

def company_applications_page():
    """Company application review page"""
    st.title("Review Applications")
    
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Status", ["Pending", "Approved", "Rejected", "All"])
    
    # Get applications for company's jobs
    applications = get_applications_for_company(st.session_state.user["username"])
    
    # Apply filter
    if status_filter != "All":
        applications = [app for app in applications if app["status"] == status_filter]
    
    if not applications:
        st.info(f"No {status_filter.lower()} applications found.")
    else:
        st.write(f"Found {len(applications)} applications")
        for app in applications:
            display_application_card(app, "Company")

def review_application_page():
    """Detailed application review page"""
    app_id = st.session_state.get("selected_app_id")
    action = st.session_state.get("action_type", "review")
    
    if not app_id:
        st.error("No application selected")
        if st.session_state.user["role"] == "Company":
            st.session_state.page = "company_applications"
        else:
            st.session_state.page = "admin_applications"
        st.rerun()
    
    # Get application details (would need to implement this function)
    # For now, we'll use a placeholder
    applications = get_all_applications()
    app = next((a for a in applications if a["id"] == app_id), None)
    
    if not app:
        st.error("Application not found")
        if st.session_state.user["role"] == "Company":
            st.session_state.page = "company_applications"
        else:
            st.session_state.page = "admin_applications"
        st.rerun()
    
    st.title(f"Review Application #{app_id}")
    
    # Show application details
    job = get_job_by_id(app["job_id"])
    if job:
        st.subheader(f"Job: {job['title']}")
        st.caption(f"Company: {job['company']}")
    
    st.subheader("Applicant Information")
    st.write(f"Student: {app['student']}")
    if "email" in app:
        st.write(f"Email: {app['email']}")
    if "full_name" in app:
        st.write(f"Name: {app['full_name']}")
    
    st.write(f"Applied on: {app['applied_at']}")
    
    if app.get("skills"):
        st.subheader("Skills")
        st.write(app["skills"])
        
    if app.get("cover_letter"):
        st.subheader("Cover Letter")
        st.write(app["cover_letter"])
    
    with st.form("review_form"):
        if action == "approve":
            new_status = "Approved"
            st.success("You are approving this application")
        elif action == "reject":
            new_status = "Rejected"
            st.error("You are rejecting this application")
        else:
            new_status = st.selectbox("Update Status", ["Pending", "Approved", "Rejected"])
        
        feedback = st.text_area("Feedback to Student", 
                              help="Provide feedback that will be visible to the student")
        
        submitted = st.form_submit_button(f"Confirm {new_status}")
        
        if submitted:
            success, msg = update_application_status(
                app_id, 
                new_status, 
                feedback, 
                st.session_state.user["username"]
            )
            
            if success:
                st.success(msg)
                if st.session_state.user["role"] == "Company":
                    st.session_state.page = "company_applications"
                else:
                    st.session_state.page = "admin_applications"
                st.rerun()
            else:
                st.error(msg)
    
    if st.button("Back"):
        if st.session_state.user["role"] == "Company":
            st.session_state.page = "company_applications"
        else:
            st.session_state.page = "admin_applications"
        st.rerun()

def admin_dashboard_page():
    """Admin dashboard with overview statistics"""
    st.title("Admin Dashboard")
    
    # Get statistics
    try:
        conn = get_db_connection()
        if not conn:
            st.error("Database connection error")
            return
            
        cursor = conn.cursor()
        
        # Count users by role
        cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
        user_stats = cursor.fetchall()
        
        # Count jobs by status
        cursor.execute("SELECT status, COUNT(*) FROM job_posts GROUP BY status")
        job_stats = cursor.fetchall()
        
        # Count applications by status
        cursor.execute("SELECT status, COUNT(*) FROM applications GROUP BY status")
        app_stats = cursor.fetchall()
        
        # Recent activity
        cursor.execute("""
            SELECT 'New User' as type, username as subject, created_at as date
            FROM users
            UNION ALL
            SELECT 'New Job' as type, title as subject, posted_at as date
            FROM job_posts
            UNION ALL
            SELECT 'Application' as type, id as subject, applied_at as date
            FROM applications
            ORDER BY date DESC
            LIMIT 10
        """)
        recent_activity = cursor.fetchall()
        
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        return
    finally:
        if conn:
            conn.close()
    
    # Display statistics in cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.container(border=True, height=150)
        st.subheader("Users")
        total_users = sum(count for _, count in user_stats)
        st.metric("Total Users", total_users)
        for role, count in user_stats:
            st.caption(f"{role}s: {count}")
    
    with col2:
        st.container(border=True, height=150)
        st.subheader("Jobs")
        total_jobs = sum(count for _, count in job_stats)
        st.metric("Total Jobs", total_jobs)
        for status, count in job_stats:
            st.caption(f"{status}: {count}")
    
    with col3:
        st.container(border=True, height=150)
        st.subheader("Applications")
        total_apps = sum(count for _, count in app_stats)
        st.metric("Total Applications", total_apps)
        for status, count in app_stats:
            st.caption(f"{status}: {count}")
    
    # Recent activity
    st.subheader("Recent Activity")
    for activity in recent_activity:
        activity_type, subject, date = activity
        st.write(f"[{date}] {activity_type}: {subject}")

def admin_manage_users_page():
    """Admin user management page"""
    st.title("Manage Users")
    
    col1, col2 = st.columns(2)
    with col1:
        role_filter = st.selectbox("Filter by Role", ["All", "Student", "Company", "Admin"])
    
    try:
        conn = get_db_connection()
        if not conn:
            st.error("Database connection error")
            return
            
        cursor = conn.cursor()
        
        if role_filter == "All":
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        else:
            cursor.execute("SELECT * FROM users WHERE role = ? ORDER BY created_at DESC", (role_filter,))
            
        users = [dict(row) for row in cursor.fetchall()]
        
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        return
    finally:
        if conn:
            conn.close()
    
    if not users:
        st.info(f"No {role_filter.lower()} users found.")
    else:
        st.write(f"Found {len(users)} users")
        for user in users:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(user["username"])
                    st.caption(f"Role: {user['role']}")
                    if user.get("email"):
                        st.caption(f"Email: {user['email']}")
                    if user.get("full_name"):
                        st.caption(f"Name: {user['full_name']}")
                    if user.get("organization"):
                        st.caption(f"Organization: {user['organization']}")
                with col2:
                    st.caption(f"Created: {user['created_at']}")
                    if user.get("last_login"):
                        st.caption(f"Last login: {user['last_login']}")

def admin_manage_applications_page():
    """Admin application management page"""
    st.title("Manage All Applications")
    
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Status", ["All", "Pending", "Approved", "Rejected"])
    
    applications = get_all_applications()
    
    if status_filter != "All":
        applications = [app for app in applications if app["status"] == status_filter]
    
    if not applications:
        st.info(f"No {status_filter.lower()} applications found.")
    else:
        st.write(f"Found {len(applications)} applications")
        for app in applications:
            display_application_card(app, "Admin")

def admin_export_data_page():
    """Admin data export page"""
    st.title("Export Data")
    
    export_type = st.selectbox("Select data to export", 
                             ["Applications", "Jobs", "Users"])
    
    if st.button("Generate Excel Export"):
        with st.spinner("Generating export..."):
            href, msg = export_to_excel(export_type.lower())
            
            if href:
                st.success(msg)
                st.markdown(href, unsafe_allow_html=True)
            else:
                st.error(msg)

# Main application
def main():
    """Main application entry point"""
    # Initialize database on startup
    init_db()
    
    # Set page config
    st.set_page_config(
        page_title="PHDCCI Internship & Placement Portal",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Add custom CSS
    st.markdown("""
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Application header
    col1, col2 = st.columns([1, 3])
    with col1:
        st.image("https://via.placeholder.com/150x80?text=PHDCCI", width=150)
    with col2:
        st.title("🎓 Internship & Placement Portal")
        st.caption("Connect students with opportunities")
    
    # Display navigation if user is logged in
    if "user" in st.session_state:
        navigation_bar()
    
    # Set default page if not set
    if "page" not in st.session_state:
        if "user" in st.session_state:
            # Default pages based on role
            role = st.session_state.user["role"]
            if role == "Student":
                st.session_state.page = "browse_jobs"
            elif role == "Company":
                st.session_state.page = "manage_jobs"
            elif role == "Admin":
                st.session_state.page = "admin_dashboard"
        else:
            st.session_state.page = "login"
    
    # Render appropriate page based on state
    current_page = st.session_state.page
    
    # Guest pages
    if current_page == "login":
        login_page()
    elif current_page == "register":
        register_page()
    
    # Student pages
    elif current_page == "browse_jobs":
        student_browse_jobs_page()
    elif current_page == "student_applications":
        student_applications_page()
    elif current_page == "apply_job":
        student_apply_job_page()
    
    # Company pages
    elif current_page == "post_job":
        company_post_job_page()
    elif current_page == "manage_jobs":
        company_manage_jobs_page()
    elif current_page == "company_applications":
        company_applications_page()
    
    # Admin pages
    elif current_page == "admin_dashboard":
        admin_dashboard_page()
    elif current_page == "admin_users":
        admin_manage_users_page()
    elif current_page == "admin_applications":
        admin_manage_applications_page()
    elif current_page == "admin_export":
        admin_export_data_page()
    
    # Shared pages
    elif current_page == "review_application":
        review_application_page()
    
    # Handle unknown page
    else:
        st.error(f"Unknown page: {current_page}")
        st.session_state.page = "login"
        st.rerun()

if __name__ == "__main__":
    main()
