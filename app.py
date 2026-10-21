import os
import sqlite3
import logging
import io
import secrets
import string
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.utils import secure_filename
import joblib
from sklearn.metrics.pairwise import cosine_similarity
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask_mail import Mail, Message
from dotenv import load_dotenv
from resume_parser import parse_resume
from resume_analyzer import analyze_resume_content
from resume_generator import generate_improved_resume_pdf
from chatbot_service import process_chat_message
from job_recommender import get_recommended_jobs_for_student, CAREER_TRACKS

# Load environment variables
load_dotenv()

# --- Logging Configuration ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(APP_DIR, "data.db")
MODEL_PATH = os.path.join(APP_DIR, "models", "job_recommendation_type_knn.pkl")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "kkit_secret_key_123")

# Email Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'your_email@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'your_app_password')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@careerguidance.com')

mail = Mail(app)

# --- Load Model ---
model = None
vectorizer = None
try:
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        logger.info("AI Model loaded successfully")
        try:
            vectorizer = model.named_steps.get("tfidf", None)
        except:
            vectorizer = None
    else:
        logger.error(f"Model file not found at {MODEL_PATH}")
except Exception as e:
    logger.error(f"Error loading model: {e}")

# --- DB Initialization ---
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Users Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'student',
                created_at TEXT,
                first_login_alert_shown BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Student Profile Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                full_name TEXT,
                register_number TEXT,
                college_name TEXT,
                batch_year TEXT,
                current_semester TEXT,
                skills TEXT,
                skill_ratings TEXT,
                experience TEXT,
                interests TEXT,
                tech_stack TEXT,
                location TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Jobs Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                required_skills TEXT,
                posted_by TEXT,
                application_link TEXT,
                created_at TEXT
            )
        """)

        # Job Recommendations Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                match_score REAL,
                match_reason TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)

        # Courses Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                category TEXT,
                added_by TEXT,
                created_at TEXT
            )
        """)

        # Course Videos Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS course_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER,
                video_title TEXT,
                video_url TEXT,
                category TEXT,
                FOREIGN KEY (course_id) REFERENCES courses(id)
            )
        """)

        # Job Trends Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_role TEXT,
                industry TEXT,
                trending_skills TEXT,
                year TEXT,
                added_by TEXT,
                created_at TEXT
            )
        """)

        # Password Reset Tokens Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Resume Analysis & Recommendations Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS resume_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT,
                overall_score INTEGER,
                grammar_score INTEGER,
                skills_score INTEGER,
                formatting_score INTEGER,
                ats_score INTEGER,
                completeness_score INTEGER,
                analysis_json TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Job Applications Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                student_name TEXT,
                email TEXT,
                phone TEXT,
                resume_filename TEXT,
                cover_note TEXT,
                status TEXT DEFAULT 'Applied',
                applied_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (job_id) REFERENCES jobs(id),
                UNIQUE(user_id, job_id)
            )
        """)

        # Auto-seed jobs from jobs.csv if table is empty
        cur.execute("SELECT count(*) FROM jobs")
        if cur.fetchone()[0] == 0:
            jobs_csv_path = os.path.join(APP_DIR, "jobs.csv")
            if os.path.exists(jobs_csv_path):
                import csv
                with open(jobs_csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        title = row.get('title')
                        company = row.get('company')
                        desc = row.get('description')
                        reqs = row.get('requirements', '').replace(';', ', ')
                        posted = row.get('posted_at', datetime.now().strftime("%Y-%m-%d"))
                        cur.execute("""
                            INSERT INTO jobs (title, description, required_skills, posted_by, created_at) 
                            VALUES (?, ?, ?, ?, ?)
                        """, (title, desc, reqs, company, posted))
                logger.info("Auto-seeded jobs from jobs.csv")

        conn.commit()
        conn.close()
        logger.info("Database checked/initialized")
    except Exception as e:
        logger.error(f"DB Init Error: {e}")

init_db()

# --- DB Helpers ---
def db_fetchall(query, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return cur.fetchall()
    except Exception as e:
        logger.error(f"DB Fetch Error: {e} | Query: {query}")
        return []

def db_execute(query, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        logger.error(f"DB Execute Error: {e} | Query: {query}")
        raise e

# --- ML Logic ---
def build_student_text(profile_row):
    # (id, user_id, name, reg, coll, batch, sem, skills, ratings, exp, ints, stack, loc, date)
    if not profile_row: return ""
    parts = [str(profile_row[7]), str(profile_row[8]), str(profile_row[10]), str(profile_row[11]), str(profile_row[9])]
    return " ".join([p for p in parts if p and p != 'None'])

def job_text(job_row):
    # (id, title, desc, skills, posted, link, date)
    if not job_row: return ""
    parts = [str(job_row[1]), str(job_row[2]), str(job_row[3])]
    return " ".join([p for p in parts if p and p != 'None'])

def recommend_jobs_logic(profile_row, all_jobs, top_k=10):
    profile_text = build_student_text(profile_row)
    recs = []
    predicted_label = None

    if model:
        try:
            predicted_label = str(model.predict([profile_text])[0]).strip().lower()
        except:
            pass

    tfidf_profile, tfidf_jobs = None, None
    if vectorizer and all_jobs:
        try:
            texts = [profile_text] + [job_text(j) for j in all_jobs]
            tfidf = vectorizer.transform(texts)
            tfidf_profile = tfidf[0:1]
            tfidf_jobs = tfidf[1:]
        except:
            pass

    for idx, job in enumerate(all_jobs):
        jtxt = job_text(job)
        eligible, reason, score = False, "", 0.0
        job_title = (job[1] or "").lower()

        if predicted_label and (predicted_label in job_title or job_title in predicted_label):
            eligible, reason, score = True, f"AI Match: {predicted_label}", 1.0

        if not eligible and tfidf_profile is not None and tfidf_jobs is not None:
            sim = float(cosine_similarity(tfidf_profile, tfidf_jobs[idx:idx+1])[0][0])
            if sim >= 0.2:
                eligible, reason, score = True, f"Similarity: {sim:.2f}", sim

        if eligible:
            recs.append({"job_id": job[0], "score": round(score, 3), "reason": reason})

    return predicted_label, sorted(recs, key=lambda x: x["score"], reverse=True)[:top_k]

# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    logger.error(f"404 Error: {request.url} not found")
    return "Page Not Found (404). Please check the URL.", 404

# --- Routes ---
@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/test")
def test():
    return "Flask server is active!"

@app.route("/")
def index():
    # Always show home page as the landing page, regardless of login status
    # This prevents issues in multi-user environments where sessions persist
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if role == "admin":
            if username == "admin" and password == "admin1234":
                session["username"] = "admin"
                session["role"] = "admin"
                session["user_id"] = -1 # Admin has id -1
                return redirect(url_for("admin"))
            flash("Invalid Admin Credentials", "danger")
            return redirect(url_for("login"))

        user = db_fetchall("SELECT * FROM users WHERE username=? AND role='student'", (username,))
        if user and user[0][3] == password:
            session["user_id"] = user[0][0]
            session["username"] = user[0][1]
            session["role"] = "student"

            # Check if this is first login (no profile and alert not shown yet)
            profile = db_fetchall("SELECT id FROM student_profile WHERE user_id=?", (user[0][0],))
            if not profile and not user[0][6]:  # user[0][6] is first_login_alert_shown
                session["show_first_login_alert"] = True
                # Mark that alert will be shown
                db_execute("UPDATE users SET first_login_alert_shown=TRUE WHERE id=?", (user[0][0],))
            else:
                session["show_first_login_alert"] = False

            return redirect(url_for("dashboard"))
        
        flash("Invalid Username or Password", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not (username and email and password and confirm_password):
            flash("Please fill all fields", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters long", "danger")
            return redirect(url_for("register"))

        try:
            # Insert user and get the user ID
            user_id = db_execute("INSERT INTO users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
                               (username, email, password, datetime.now().strftime("%Y-%m-%d %H:%M")))

            flash("Account created successfully! Please login with your credentials.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            logger.error(f"Registration error for user {username}: {e}")
            flash("Username or Email already exists", "danger")
    return render_template("register.html")

@app.route("/forgot_password")
def forgot_password():
    # Generate demo reset token (no login required)
    token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    expires_at = datetime.now() + timedelta(hours=1)  # Token expires in 1 hour

    # Save token to database (use a placeholder user_id for demo)
    # In production, this would be associated with a real user
    demo_user_id = 1  # Placeholder - in real app this would be the actual user
    db_execute("INSERT INTO password_reset_tokens (user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
               (demo_user_id, token, expires_at.strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M")))

    # Redirect directly to reset password page
    return redirect(url_for('reset_password', token=token))

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    # Check if token is valid and not expired
    token_data = db_fetchall("""
        SELECT prt.*, u.email FROM password_reset_tokens prt
        JOIN users u ON prt.user_id = u.id
        WHERE prt.token=? AND prt.used=FALSE AND prt.expires_at > ?
    """, (token, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    if not token_data:
        flash("Invalid or expired reset link. Please request a new password reset.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not password or not confirm_password:
            flash("Please fill all fields", "danger")
            return redirect(url_for("reset_password", token=token))

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("reset_password", token=token))

        if len(password) < 6:
            flash("Password must be at least 6 characters long", "danger")
            return redirect(url_for("reset_password", token=token))

        # Update password
        db_execute("UPDATE users SET password=? WHERE id=?", (password, token_data[0][1]))

        # Mark token as used
        db_execute("UPDATE password_reset_tokens SET used=TRUE WHERE id=?", (token_data[0][0],))

        flash("Password updated successfully! Please login with your new password.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)

# OAuth features have been completely disabled

def send_password_reset_email(target_email, reset_url):
    """Send password reset email to the specified email address
    Returns:
    - True: Email sent successfully
    - False: Email sending failed
    - "demo": Demo mode (link shown but not emailed)
    """
    try:
        # Check if email configuration is properly set
        mail_server = os.getenv('MAIL_SERVER')
        mail_username = os.getenv('MAIL_USERNAME')
        mail_password = os.getenv('MAIL_PASSWORD')

        # For demo purposes, if using demo credentials, return special status
        if mail_username == 'demo@example.com' or mail_password == 'demo_password_123':
            logger.info(f"Demo mode: Password reset link for {target_email}: {reset_url}")
            print(f"\n=== DEMO MODE PASSWORD RESET ===")
            print(f"Email would be sent to: {target_email}")
            print(f"Reset Link: {reset_url}")
            print("Copy this link to test password reset functionality")
            print("=" * 50)
            return "demo"

        # Check if using Gmail - Gmail requires App Passwords for SMTP
        if '@gmail.com' in mail_username:
            logger.warning(f"Gmail detected - Gmail requires App Password for SMTP authentication")
            print(f"\n=== GMAIL REQUIRES APP PASSWORD ===")
            print(f"You are using Gmail ({mail_username}) but Gmail requires an App Password for SMTP.")
            print(f"Regular Gmail passwords don't work for email sending from apps.")
            print(f"Get an App Password from: https://myaccount.google.com/apppasswords")
            print(f"Then update your .env file with the 16-character App Password.")
            print("=" * 50)
            # Return special status for Gmail config issue
            return "gmail_error"

        if not all([mail_server, mail_username, mail_password]):
            logger.error("Email configuration incomplete - missing MAIL_SERVER, MAIL_USERNAME, or MAIL_PASSWORD")
            return False

        if mail_username in ['your_email@gmail.com', ''] or mail_password in ['your_gmail_app_password', '']:
            logger.error("Email configuration using placeholder values")
            return False

        subject = "Password Reset - Smart Career Guidance & Employment Portal"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #2563eb, #3b82f6); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="margin: 0; font-size: 24px;">Password Reset Request</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">Smart Career Guidance & Employment Portal</p>
            </div>

            <div style="background: white; border: 1px solid #e5e7eb; border-radius: 0 0 10px 10px; padding: 30px;">
                <p style="font-size: 16px; line-height: 1.6; color: #374151; margin-bottom: 20px;">
                    We received a request to reset your password. Click the button below to create a new password:
                </p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" style="background: linear-gradient(135deg, #2563eb, #3b82f6); color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3);">
                        Reset Password
                    </a>
                </div>

                <p style="font-size: 14px; color: #6b7280; line-height: 1.5; margin-top: 20px;">
                    This link will expire in 1 hour for security reasons. If you didn't request this password reset, please ignore this email.
                </p>

                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

                <p style="font-size: 12px; color: #9ca3af; text-align: center;">
                    If the button doesn't work, copy and paste this link into your browser:<br>
                    <span style="word-break: break-all; color: #2563eb;">{reset_url}</span>
                </p>
            </div>

            <div style="text-align: center; margin-top: 20px; padding: 20px; background: #f9fafb; border-radius: 8px;">
                <p style="font-size: 14px; color: #6b7280; margin: 0;">
                    Need help? Contact our support team at <a href="mailto:support@careerguidance.com" style="color: #2563eb;">support@careerguidance.com</a>
                </p>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        Password Reset Request - Smart Career Guidance & Employment Portal

        We received a request to reset your password. Click the link below to create a new password:

        {reset_url}

        This link will expire in 1 hour for security reasons. If you didn't request this password reset, please ignore this email.

        Need help? Contact our support team at support@careerguidance.com
        """

        msg = Message(subject, recipients=[target_email])
        msg.html = html_body
        msg.body = text_body

        logger.info(f"Attempting to send password reset email to {target_email}")
        mail.send(msg)
        logger.info(f"Password reset email sent successfully to {target_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send password reset email to {target_email}: {str(e)}")
        logger.error(f"Mail config - Server: {os.getenv('MAIL_SERVER')}, Port: {os.getenv('MAIL_PORT')}, Username: {os.getenv('MAIL_USERNAME')}")
        return False


@app.route("/dashboard")
def dashboard():
    if session.get("role") != "student":
        return redirect(url_for("login"))
    
    user_id = session.get("user_id")
    uid = user_id
    profile = db_fetchall("SELECT * FROM student_profile WHERE user_id=?", (user_id,))
    
    # Fetch latest resume analysis if available
    latest_analysis = None
    analysis_row = db_fetchall("SELECT filename, analysis_json, created_at FROM resume_analysis WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,))
    if analysis_row and analysis_row[0][1]:
        try:
            latest_analysis = json.loads(analysis_row[0][1])
            latest_analysis["filename"] = analysis_row[0][0]
            latest_analysis["analyzed_at"] = analysis_row[0][2]
        except Exception as e:
            logger.error(f"Error loading saved resume analysis for user {user_id}: {e}")

    if not profile:
        return render_template("dashboard.html", student=None, needs_profile=True,
                             latest_resume_analysis=latest_analysis,
                             show_first_login_alert=session.get('show_first_login_alert', False))

    # Fetch applied jobs map for student
    applied_jobs_map = {}
    app_rows = db_fetchall("SELECT job_id, applied_at, status FROM applications WHERE user_id=?", (user_id,))
    for a in app_rows:
        applied_jobs_map[a[0]] = {"applied_at": a[1], "status": a[2]}

    # Get enhanced career recommendations & tracks
    rec_data = get_recommended_jobs_for_student(user_id, role_filter="all")
    recs = rec_data.get("jobs", [])
    career_tracks = rec_data.get("tracks", CAREER_TRACKS)
    role_counts = rec_data.get("role_counts", {})

    # Calculate ATS compatibility insights
    profile_completeness = 0
    ats_insights = []

    if profile and profile[0]:
        p = profile[0]
        # Check profile completeness
        fields = [p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11], p[12]]
        filled_fields = sum(1 for f in fields if f and str(f).strip() and str(f) != 'None')
        profile_completeness = int((filled_fields / len(fields)) * 100)

        # Generate insights based on profile
        if p[7] and len(str(p[7]).split(',')) >= 3:  # Skills
            ats_insights.append("✓ Strong skills profile with multiple technologies")
        elif p[7]:
            ats_insights.append("⚠ Add more skills to improve ATS matching")

        if p[11] and len(str(p[11]).split(',')) >= 2:  # Tech stack
            ats_insights.append("✓ Diverse tech stack increases job opportunities")
        elif p[11]:
            ats_insights.append("⚠ Expand your tech stack for better matches")

        if p[9] and len(str(p[9]).split()) >= 10:  # Experience
            ats_insights.append("✓ Detailed experience description helps ATS parsing")
        elif p[9]:
            ats_insights.append("⚠ Add more details to your experience section")

        if recs and len(recs) >= 5:
            ats_insights.append("✓ Multiple job matches found - good profile strength")
        elif recs and len(recs) >= 2:
            ats_insights.append("✓ Some job matches generated")
        elif recs:
            ats_insights.append("⚠ Limited job matches - consider broadening skills")

        # Default insights if profile is incomplete
        if not ats_insights:
            ats_insights = [
                "Complete your profile for better recommendations",
                "Add skills, experience, and tech stack details",
                "Include specific technologies and tools you know"
            ]

    else:
        profile_completeness = 0
        ats_insights = ["Complete your profile to get personalized insights"]

    # Get unique course categories
    all_courses = db_fetchall("SELECT * FROM courses ORDER BY id DESC")
    course_categories = []
    seen_categories = set()
    for course in all_courses:
        category = course[3]  # category is at index 3 (id, title, description, category, added_by, created_at)
        if category and category not in seen_categories:
            seen_categories.add(category)
            course_categories.append((category,))

    return render_template("dashboard.html", student=profile[0], recommendations=recs,
                           career_tracks=career_tracks, role_counts=role_counts,
                           applied_jobs=applied_jobs_map, active_role="all",
                           trends=db_fetchall("SELECT * FROM job_trends ORDER BY id DESC"),
                           courses=all_courses,
                           course_categories=course_categories,
                           videos=db_fetchall("SELECT * FROM course_videos ORDER BY id DESC"),
                           profile_completeness=profile_completeness, ats_insights=ats_insights,
                           latest_resume_analysis=latest_analysis,
                           needs_profile=False, show_first_login_alert=session.get('show_first_login_alert', False))

@app.route("/save_profile", methods=["POST"])
def save_profile():
    if session.get("role") != "student": return redirect(url_for("login"))
    uid = session.get("user_id")
    f = request.form

    # Debug logging
    logger.info(f"Profile update request for user {uid}")
    logger.info(f"Skills: {f.get('skills')}")
    logger.info(f"Skill Ratings: {f.get('skill_ratings')}")
    logger.info(f"Tech Stack: {f.get('tech_stack')}")

    data = (uid, f.get("full_name"), f.get("register_number"), f.get("college_name"), f.get("batch_year"),
            f.get("current_semester"), f.get("skills"), f.get("skill_ratings"), f.get("experience"),
            f.get("interests"), f.get("tech_stack"), f.get("location"), datetime.now().strftime("%Y-%m-%d %H:%M"))

    existing = db_fetchall("SELECT id FROM student_profile WHERE user_id=?", (uid,))
    if existing:
        db_execute("""UPDATE student_profile SET full_name=?, register_number=?, college_name=?, batch_year=?, 
                   current_semester=?, skills=?, skill_ratings=?, experience=?, interests=?, tech_stack=?, 
                   location=?, created_at=? WHERE user_id=?""", data[1:] + (uid,))
        db_execute("DELETE FROM job_recommendations WHERE user_id=?", (uid,))
    else:
        db_execute("""INSERT INTO student_profile (user_id, full_name, register_number, college_name, batch_year, 
                   current_semester, skills, skill_ratings, experience, interests, tech_stack, location, created_at) 
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", data)

    # Trigger Recs
    try:
        rec_data = get_recommended_jobs_for_student(uid, role_filter="all")
        jobs_list = rec_data.get("jobs", [])
        logger.info(f"Generated {len(jobs_list)} recommendations for user {uid}")

        # Delete old recommendations
        db_execute("DELETE FROM job_recommendations WHERE user_id=?", (uid,))

        # Insert new recommendations
        inserted_count = 0
        for r in jobs_list:
            try:
                db_execute("INSERT INTO job_recommendations (user_id, job_id, match_score, match_reason, created_at) VALUES (?,?,?,?,?)",
                           (uid, r["id"], r["match_decimal"], r["match_reason"], datetime.now().strftime("%Y-%m-%d")))
                inserted_count += 1
            except Exception as e:
                logger.error(f"Error inserting recommendation for user {uid}: {e}")

        logger.info(f"Successfully inserted {inserted_count} new recommendations for user {uid}")

    except Exception as e:
        logger.error(f"Error generating recommendations for user {uid}: {e}")
        # Don't fail the profile update if recommendations fail
        flash("Profile updated! (Note: Recommendations may take a moment to update)", "warning")
        return redirect(url_for("dashboard"))

    flash("Profile updated and recommendations refreshed!", "success")
    return redirect(url_for("dashboard"))

@app.route("/upload_resume", methods=["POST"])
@app.route("/parse_resume", methods=["POST"])
def parse_resume_endpoint():
    """
    Secure endpoint to upload and extract career profile information
    from PDF or DOCX resumes, and run immediate AI analysis.
    """
    if session.get("role") != "student":
        return jsonify({"success": False, "error": "Unauthorized. Please log in as a student."}), 401

    if "resume" not in request.files:
        return jsonify({"success": False, "error": "No resume file was uploaded. Please choose a file."}), 400

    file = request.files["resume"]
    if not file or file.filename.strip() == "":
        return jsonify({"success": False, "error": "No file selected. Please select a valid PDF or DOCX file."}), 400

    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({"success": False, "error": "Invalid filename."}), 400

    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".docx"]:
        return jsonify({
            "success": False,
            "error": f"Unsupported file format '{ext}'. Only PDF and DOCX files are supported."
        }), 400

    try:
        file_bytes = file.read()
        max_size = 10 * 1024 * 1024  # 10 MB limit
        if len(file_bytes) > max_size:
            return jsonify({
                "success": False,
                "error": f"File size exceeds the 10MB limit (uploaded: {len(file_bytes)/(1024*1024):.1f}MB). Please upload a smaller file."
            }), 400

        if len(file_bytes) == 0:
            return jsonify({"success": False, "error": "The uploaded file is empty. Please upload a valid resume."}), 400

        # 1. Extract resume fields
        extracted_data = parse_resume(file_bytes, filename)
        uid = session.get("user_id")
        logger.info(f"Resume parsed successfully for user {uid}: {filename}")

        # 2. Run AI resume analysis
        raw_text = extracted_data.get("raw_text", "")
        analysis_result = analyze_resume_content(extracted_data, raw_text)
        analysis_result["filename"] = filename

        # 3. Save analysis to database for this authenticated student
        try:
            db_execute("""
                INSERT INTO resume_analysis (
                    user_id, filename, overall_score, grammar_score, skills_score,
                    formatting_score, ats_score, completeness_score, analysis_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid,
                filename,
                analysis_result["overall_score"],
                analysis_result["category_scores"]["grammar"]["score"],
                analysis_result["category_scores"]["skills"]["score"],
                analysis_result["category_scores"]["formatting"]["score"],
                analysis_result["category_scores"]["ats"]["score"],
                analysis_result["category_scores"]["completeness"]["score"],
                json.dumps(analysis_result),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
        except Exception as dbe:
            logger.error(f"Error persisting resume analysis for user {uid}: {dbe}")

        return jsonify({
            "success": True,
            "message": "Resume uploaded, extracted, and analyzed successfully!",
            "filename": filename,
            "data": extracted_data,
            "analysis": analysis_result
        }), 200

    except ValueError as ve:
        logger.warning(f"Resume parsing warning for {filename}: {ve}")
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error parsing resume {filename}: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Failed to parse the resume file. Please ensure it is a valid, readable PDF or DOCX document."
        }), 500


@app.route("/analyze_resume", methods=["POST"])
def analyze_resume_endpoint():
    """
    Analyzes or re-analyzes current profile content or revised resume fields.
    Computes updated scores, detects remaining issues, and provides fresh recommendations.
    """
    if session.get("role") != "student":
        return jsonify({"success": False, "error": "Unauthorized. Please log in as a student."}), 401

    uid = session.get("user_id")
    payload = request.get_json(silent=True) or request.form.to_dict() or {}

    filename = payload.get("filename") or "Current_Profile_Resume.pdf"
    raw_text = payload.get("raw_text", "")

    try:
        analysis_result = analyze_resume_content(payload, raw_text)
        analysis_result["filename"] = filename

        # Persist updated analysis
        try:
            db_execute("""
                INSERT INTO resume_analysis (
                    user_id, filename, overall_score, grammar_score, skills_score,
                    formatting_score, ats_score, completeness_score, analysis_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid,
                filename,
                analysis_result["overall_score"],
                analysis_result["category_scores"]["grammar"]["score"],
                analysis_result["category_scores"]["skills"]["score"],
                analysis_result["category_scores"]["formatting"]["score"],
                analysis_result["category_scores"]["ats"]["score"],
                analysis_result["category_scores"]["completeness"]["score"],
                json.dumps(analysis_result),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
        except Exception as dbe:
            logger.error(f"Error saving re-analysis for user {uid}: {dbe}")

        return jsonify({
            "success": True,
            "message": "Resume re-analyzed successfully! Updated scores and remaining suggestions are shown below.",
            "analysis": analysis_result
        }), 200

    except Exception as e:
        logger.error(f"Error during re-analysis for user {uid}: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Analysis failed: {str(e)}"}), 500


@app.route("/get_latest_resume_analysis", methods=["GET"])
def get_latest_resume_analysis():
    """
    Returns the latest resume analysis for the logged-in student.
    """
    if session.get("role") != "student":
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    uid = session.get("user_id")
    row = db_fetchall("""
        SELECT filename, analysis_json, created_at 
        FROM resume_analysis 
        WHERE user_id=? 
        ORDER BY id DESC LIMIT 1
    """, (uid,))

    if not row or not row[0][1]:
        return jsonify({"success": False, "message": "No previous analysis found"}), 404

    try:
        analysis = json.loads(row[0][1])
        analysis["filename"] = row[0][0]
        analysis["analyzed_at"] = row[0][2]
        return jsonify({"success": True, "analysis": analysis}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/download_improved_resume", methods=["POST"])
def download_improved_resume():
    """
    Generates and downloads a clean, professional, ATS-friendly PDF resume
    based on the user's reviewed and approved Career Profile details.
    """
    if session.get("role") != "student":
        return redirect(url_for("login"))

    uid = session.get("user_id")
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()

    # If data is empty, fallback to fetching from student_profile in DB
    if not data or not data.get("full_name"):
        prof = db_fetchall("SELECT * FROM student_profile WHERE user_id=?", (uid,))
        if prof:
            p = prof[0]
            data = {
                "full_name": p[2],
                "register_number": p[3],
                "college_name": p[4],
                "batch_year": p[5],
                "current_semester": p[6],
                "skills": p[7],
                "skill_ratings": p[8],
                "experience": p[9],
                "interests": p[10],
                "tech_stack": p[11],
                "location": p[12]
            }

    # Also check user table for email if missing
    if not data.get("email"):
        u = db_fetchall("SELECT email FROM users WHERE id=?", (uid,))
        if u:
            data["email"] = u[0][0]

    try:
        pdf_buffer = generate_improved_resume_pdf(data)
        raw_name = data.get("full_name") or "Student"
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', raw_name)
        download_filename = f"Improved_ATS_Resume_{safe_name}.pdf"

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=download_filename,
            mimetype="application/pdf"
        )
    except Exception as e:
        logger.error(f"Error generating improved resume for user {uid}: {e}", exc_info=True)
        flash("Could not generate improved resume. Please check your profile details and try again.", "danger")
        return redirect(url_for("dashboard"))

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if session.get("role") != "admin": return redirect(url_for("login"))
    if request.method == "POST":
        act = request.form.get("action")
        f = request.form
        if act == "add_job":
            db_execute("INSERT INTO jobs (title, application_link, required_skills, description, posted_by, created_at) VALUES (?,?,?,?,'admin',?)",
                       (f.get("title"), f.get("application_link"), f.get("required_skills"), f.get("description"), datetime.now().strftime("%Y-%m-%d")))
        elif act == "add_course":
            db_execute("INSERT INTO courses (title, category, description, added_by, created_at) VALUES (?,?,?,'admin',?)",
                       (f.get("title"), f.get("category"), f.get("description"), datetime.now().strftime("%Y-%m-%d")))
        elif act == "add_video":
            db_execute("INSERT INTO course_videos (course_id, video_title, video_url, category) VALUES (?,?,?,?)",
                       (f.get("course_id"), f.get("video_title"), f.get("video_url"), f.get("category")))
        elif act == "add_trend":
            db_execute("INSERT INTO job_trends (job_role, industry, trending_skills, year, added_by, created_at) VALUES (?,?,?,?,'admin',?)",
                       (f.get("job_role"), f.get("industry"), f.get("trending_skills"), f.get("year"), datetime.now().strftime("%Y-%m-%d")))
        return redirect(url_for("admin"))

    return render_template("admin_dashboard.html", 
                           jobs=db_fetchall("SELECT * FROM jobs ORDER BY id DESC"),
                           courses=db_fetchall("SELECT * FROM courses ORDER BY id DESC"),
                           videos=db_fetchall("SELECT v.*, c.title FROM course_videos v LEFT JOIN courses c ON v.course_id = c.id ORDER BY v.id DESC"),
                           trends=db_fetchall("SELECT * FROM job_trends ORDER BY id DESC"),
                           students=db_fetchall("SELECT * FROM student_profile ORDER BY id DESC"),
                           users=db_fetchall("SELECT * FROM users WHERE role='student' ORDER BY id DESC"))

@app.route("/delete/<kind>/<int:oid>")
def delete(kind, oid):
    if session.get("role") != "admin": return redirect(url_for("login"))
    tables = {"job":"jobs", "student":"student_profile", "user":"users", "course":"courses", "video":"course_videos", "trend":"job_trends"}
    if kind in tables:
        db_execute(f"DELETE FROM {tables[kind]} WHERE id=?", (oid,))
        if kind == "user": 
            db_execute("DELETE FROM student_profile WHERE user_id=?", (oid,))
            db_execute("DELETE FROM job_recommendations WHERE user_id=?", (oid,))
    return redirect(url_for("admin"))

@app.route("/download_report")
def download_report():
    if session.get("role") != "student": return redirect(url_for("login"))
    uid = session.get("user_id")
    profile = db_fetchall("SELECT * FROM student_profile WHERE user_id=?", (uid,))
    if not profile: return redirect(url_for("dashboard"))
    p = profile[0]

    # Calculate ATS compatibility insights (same logic as dashboard)
    profile_completeness = 0
    ats_insights = []

    if profile and profile[0]:
        p = profile[0]
        # Check profile completeness
        fields = [p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11], p[12]]
        filled_fields = sum(1 for f in fields if f and str(f).strip() and str(f) != 'None')
        profile_completeness = int((filled_fields / len(fields)) * 100)

        # Generate insights based on profile
        if p[7] and len(str(p[7]).split(',')) >= 3:  # Skills
            ats_insights.append("Strong skills profile with multiple technologies")
        elif p[7]:
            ats_insights.append("Add more skills to improve ATS matching")

        if p[11] and len(str(p[11]).split(',')) >= 2:  # Tech stack
            ats_insights.append("Diverse tech stack increases job opportunities")
        elif p[11]:
            ats_insights.append("Expand your tech stack for better matches")

        if p[9] and len(str(p[9]).split()) >= 10:  # Experience
            ats_insights.append("Detailed experience description helps ATS parsing")
        elif p[9]:
            ats_insights.append("Add more details to your experience section")

        recs = db_fetchall("""
            SELECT j.*, r.match_score, r.match_reason FROM job_recommendations r
            JOIN jobs j ON r.job_id = j.id WHERE r.user_id = ? ORDER BY r.match_score DESC
        """, (uid,))

        if recs and len(recs) >= 5:
            ats_insights.append("Multiple job matches found - good profile strength")
        elif recs and len(recs) >= 2:
            ats_insights.append("Some job matches generated")
        elif recs:
            ats_insights.append("Limited job matches - consider broadening skills")

        # Default insights if profile is incomplete
        if not ats_insights:
            ats_insights = [
                "Complete your profile for better recommendations",
                "Add skills, experience, and tech stack details",
                "Include specific technologies and tools you know"
            ]

    else:
        profile_completeness = 0
        ats_insights = ["Complete your profile to get personalized insights"]
        recs = []

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(300, 750, "AI CAREER REPORT")

    # Profile Summary Section
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 700, "PROFILE SUMMARY")
    c.setFont("Helvetica", 12)
    c.drawString(50, 675, f"Name: {p[2] or 'N/A'}")
    c.drawString(50, 655, f"Register Number: {p[3] or 'N/A'}")
    c.drawString(50, 635, f"College: {p[4] or 'N/A'}")
    c.drawString(50, 615, f"Batch Year: {p[5] or 'N/A'}")
    c.drawString(50, 595, f"Current Semester: {p[6] or 'N/A'}")
    c.drawString(50, 575, f"Skills: {p[7] or 'N/A'}")
    c.drawString(50, 555, f"Tech Stack: {p[11] or 'N/A'}")
    c.drawString(50, 535, f"Interests: {p[10] or 'N/A'}")
    c.drawString(50, 515, f"Location: {p[12] or 'N/A'}")

    # ATS Compatibility Insights
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 480, "ATS COMPATIBILITY INSIGHTS")
    c.setFont("Helvetica", 12)
    c.drawString(50, 460, f"Profile Completeness: {profile_completeness}%")
    y_pos = 440
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y_pos, "Optimization Tips:")
    y_pos -= 20
    c.setFont("Helvetica", 10)
    for i, insight in enumerate(ats_insights[:4]):  # Show top 4 insights
        c.drawString(50, y_pos, f"• {insight}")
        y_pos -= 15

    # Skill Analysis
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 400, "SKILL ANALYSIS")
    c.setFont("Helvetica", 12)
    recs = db_fetchall("SELECT j.title, r.match_score FROM job_recommendations r JOIN jobs j ON r.job_id = j.id WHERE r.user_id = ? ORDER BY r.match_score DESC LIMIT 1", (uid,))
    if recs:
        skill_confidence = int(recs[0][1] * 100)
        c.drawString(50, 380, f"Skill Match Confidence: {skill_confidence}%")
        c.drawString(50, 360, "Analysis: Generated by comparing your profile with job descriptions")
    else:
        c.drawString(50, 380, "Skill Match Confidence: 0%")
        c.drawString(50, 360, "Analysis: No job matches found yet")

    # Job Recommendations
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 320, "TOP JOB RECOMMENDATIONS")
    c.setFont("Helvetica", 12)
    recs = db_fetchall("SELECT j.title, r.match_score FROM job_recommendations r JOIN jobs j ON r.job_id = j.id WHERE r.user_id = ? ORDER BY r.match_score DESC LIMIT 5", (uid,))
    y = 295
    if recs:
        for i, r in enumerate(recs, 1):
            c.drawString(50, y, f"{i}. {r[0]}")
            c.drawString(400, y, f"{int(r[1]*100)}% match")
            y -= 20
    else:
        c.drawString(50, y, "No job recommendations available yet.")
        c.drawString(50, y-20, "Complete your profile and skills to get personalized recommendations.")
    # Footer
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, 50, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(50, 35, "KKIT Career Portal - AI-Powered Career Guidance")

    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"AI_Career_Report_{p[2] or 'Student'}.pdf", mimetype='application/pdf')

@app.route("/chat", methods=["POST"])
def chat():
    """
    Intelligent Conversational AI Chatbot Endpoint.
    Integrates external LLM (OpenAI/Gemini) if configured, or uses advanced local
    multi-domain reasoning engine for coding, careers, resume, education, jobs, and follow-ups.
    """
    payload = request.get_json(silent=True, force=True) or request.form.to_dict() or {}
    if not payload and request.data:
        try:
            payload = json.loads(request.data.decode("utf-8"))
        except:
            payload = {}
    user_message = (payload.get("message") or payload.get("prompt") or "").strip()
    history = payload.get("history", [])

    if not user_message:
        return jsonify({"success": False, "response": "Please type a question so I can assist you!"})

    # Gather authenticated student profile context if available
    student_context = {}
    uid = session.get("user_id")
    if uid and session.get("role") == "student":
        prof = db_fetchall("SELECT * FROM student_profile WHERE user_id=?", (uid,))
        if prof:
            p = prof[0]
            student_context = {
                "name": p[2] or "Student",
                "skills": p[7] or "",
                "interests": p[10] or "",
                "tech_stack": p[11] or "",
                "college": p[4] or ""
            }

    try:
        reply_text = process_chat_message(user_message, history=history, student_context=student_context)
        return jsonify({"success": True, "response": reply_text})
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        return jsonify({
            "success": True,
            "response": "I encountered a temporary processing hiccup. Please rephrase or ask another question about careers, coding, courses, or jobs!"
        })


@app.route("/apply_job", methods=["POST"])
def apply_job():
    """
    Internal Job Application Submission Endpoint.
    Submits application directly, validates job ID, prevents duplicate applications,
    attaches candidate resume, and persists application status in SQLite.
    """
    if session.get("role") != "student":
        return jsonify({"success": False, "error": "Please log in as a student to apply for jobs."}), 401

    uid = session.get("user_id")
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    job_id = payload.get("job_id")
    cover_note = (payload.get("cover_note") or "").strip()

    if not job_id:
        return jsonify({"success": False, "error": "Job ID is required."}), 400

    try:
        job_id = int(job_id)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid Job ID format."}), 400

    # Validate that job exists in the database
    job_row = db_fetchall("SELECT id, title, description, required_skills, posted_by, application_link FROM jobs WHERE id=?", (job_id,))
    if not job_row:
        return jsonify({"success": False, "error": f"Job with ID #{job_id} was not found."}), 404

    job = job_row[0]
    job_title = job[1]
    company = job[4] or "Company"

    # Check for duplicate application
    existing_app = db_fetchall("SELECT id, applied_at, status FROM applications WHERE user_id=? AND job_id=?", (uid, job_id))
    if existing_app:
        return jsonify({
            "success": False,
            "already_applied": True,
            "message": f"You have already applied for '{job_title}' at {company} on {existing_app[0][1]}.",
            "applied_at": existing_app[0][1],
            "status": existing_app[0][2]
        }), 200

    # Retrieve student details
    student_prof = db_fetchall("SELECT * FROM student_profile WHERE user_id=?", (uid,))
    user_info = db_fetchall("SELECT username, email FROM users WHERE id=?", (uid,))

    student_name = student_prof[0][2] if student_prof and student_prof[0][2] else (user_info[0][0] if user_info else "Applicant")
    email = user_info[0][1] if user_info else ""
    phone = student_prof[0][12] if student_prof and student_prof[0][12] else ""

    # Check for latest uploaded resume
    latest_res = db_fetchall("SELECT filename FROM resume_analysis WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,))
    resume_fn = latest_res[0][0] if latest_res and latest_res[0][0] else f"{student_name.replace(' ', '_')}_Resume.pdf"

    applied_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        db_execute("""
            INSERT INTO applications (user_id, job_id, student_name, email, phone, resume_filename, cover_note, status, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Applied', ?)
        """, (uid, job_id, student_name, email, phone, resume_fn, cover_note, applied_at))

        logger.info(f"User {uid} ({student_name}) successfully applied for Job #{job_id} ({job_title})")

        return jsonify({
            "success": True,
            "message": f"Application submitted successfully for '{job_title}' at {company}!",
            "job_id": job_id,
            "job_title": job_title,
            "company": company,
            "status": "Applied",
            "applied_at": applied_at
        }), 200

    except Exception as e:
        logger.error(f"Error persisting application for user {uid}, job {job_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Internal database error while submitting your application. Please try again."}), 500


@app.route("/get_career_recommendations", methods=["GET"])
def get_career_recommendations_endpoint():
    """
    API endpoint to fetch personalized, deduplicated job recommendations
    dynamically filtered by career track / role.
    """
    if session.get("role") != "student":
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    uid = session.get("user_id")
    role_filter = request.args.get("role", "all")
    result = get_recommended_jobs_for_student(uid, role_filter=role_filter)
    return jsonify(result)


@app.route("/my_applications", methods=["GET"])
def my_applications():
    """
    API endpoint returning all jobs applied by the current student.
    """
    if session.get("role") != "student":
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    uid = session.get("user_id")
    apps = db_fetchall("""
        SELECT a.id, a.job_id, a.applied_at, a.status, j.title, j.posted_by
        FROM applications a 
        JOIN jobs j ON a.job_id = j.id 
        WHERE a.user_id=? 
        ORDER BY a.id DESC
    """, (uid,))

    results = []
    for a in apps:
        results.append({
            "application_id": a[0],
            "job_id": a[1],
            "applied_at": a[2],
            "status": a[3],
            "job_title": a[4],
            "company": a[5]
        })

    return jsonify({"success": True, "applications": results})

@app.route("/test_email")
def test_email():
    """Test email functionality - accessible during development"""
    if os.getenv('FLASK_ENV') != 'development':
        return "This endpoint is only available in development mode", 403

    test_email_address = "test@example.com"  # Change this to your real email for testing
    test_reset_url = url_for('reset_password', token='test-token-123', _external=True)

    success = send_password_reset_email(test_email_address, test_reset_url)

    if success:
        return f"Test email sent successfully to {test_email_address}! Check your inbox."
    else:
        return "Failed to send test email. Check Flask console for error details."

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/clear-session")
def clear_session():
    """Clear session and redirect to home"""
    session.clear()
    return redirect(url_for("index", home="true"))

@app.route("/debug-session")
def debug_session():
    """Debug route to check session data"""
    if not session.get("username"):
        return "No active session. <a href='/login'>Login</a>"

    session_data = {
        "user_id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role"),
        "all_keys": list(session.keys())
    }
    return f"""
    <h2>Session Debug Info</h2>
    <pre>{session_data}</pre>
    <a href="/dashboard">Go to Dashboard</a> |
    <a href="/clear-session">Clear Session</a> |
    <a href="/logout">Logout</a>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5007))
    debug = os.environ.get("FLASK_ENV", "development").lower() == "development"
    app.run(debug=debug, host='0.0.0.0', port=port)
