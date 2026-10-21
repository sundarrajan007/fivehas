import os
import sys
import sqlite3
import logging
import io
import PyPDF2
import docx2txt
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import joblib

# Force flush stdout
sys.stdout.reconfigure(line_buffering=True)

# --- Logging Configuration ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Paths & Config ---
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "data.db")
MODEL_PATH = os.path.join(APP_DIR, "models", "job_recommendation_type_knn.pkl")
UPLOAD_FOLDER = os.path.join(APP_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "kkit_career_portal_v3_secret"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['TEMPLATES_AUTO_RELOAD'] = True
ALLOWED_EXTENSIONS = {"pdf", "docx"}

# --- Load Pre-trained AI Model (Prediction Only) ---
model = None
vectorizer = None
try:
    if os.path.exists(MODEL_PATH):
        from sklearn.metrics.pairwise import cosine_similarity
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
        cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT DEFAULT 'student', created_at TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS student_profile (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE NOT NULL, full_name TEXT, register_number TEXT, college_name TEXT, batch_year TEXT, current_semester TEXT, skills TEXT, skill_ratings TEXT, experience TEXT, interests TEXT, tech_stack TEXT, location TEXT, created_at TEXT, FOREIGN KEY (user_id) REFERENCES users(id))")
        cur.execute("CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, required_skills TEXT, posted_by TEXT, application_link TEXT, created_at TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS job_recommendations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, job_id INTEGER NOT NULL, match_score REAL, match_reason TEXT, created_at TEXT, FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (job_id) REFERENCES jobs(id))")
        cur.execute("CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, category TEXT, course_link TEXT, added_by TEXT, created_at TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS course_videos (id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER, video_title TEXT, video_url TEXT, category TEXT, FOREIGN KEY (course_id) REFERENCES courses(id))")
        cur.execute("CREATE TABLE IF NOT EXISTS job_trends (id INTEGER PRIMARY KEY AUTOINCREMENT, job_role TEXT, industry TEXT, trending_skills TEXT, year TEXT, added_by TEXT, created_at TEXT)")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB Init Error: {e}")

init_db()

# Update video categories to match course categories
def update_video_categories():
    """Update video categories to match course categories for proper display"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Map specific video titles to appropriate categories
        video_category_map = {
            # Programming Languages
            "Python Programming": "Programming Languages",
            "Java Programming": "Programming Languages",
            "JavaScript Fundamentals": "Programming Languages",
            "C++ Programming": "Programming Languages",

            # Web Development
            "HTML & CSS Tutorial": "Web Development",
            "JavaScript Tutorial": "Web Development",
            "React.js Tutorial": "Web Development",
            "Node.js Tutorial": "Web Development",
            "Full Stack Development": "Web Development",

            # Mobile Development
            "Flutter Tutorial for Beginners": "Mobile Development",
            "React Native Tutorial": "Mobile Development",
            "Android Development Tutorial": "Mobile Development",
            "iOS Development Tutorial": "Mobile Development",

            # Databases
            "SQL Fundamentals": "Databases",
            "MongoDB Tutorial": "Databases",
            "PostgreSQL Tutorial": "Databases",

            # DevOps & Cloud
            "Docker Tutorial": "DevOps & Cloud",
            "AWS Tutorial": "DevOps & Cloud",
            "Kubernetes Tutorial": "DevOps & Cloud",
            "Jenkins Tutorial": "DevOps & Cloud",

            # AI & Machine Learning
            "Machine Learning Basics": "AI & Machine Learning",
            "Deep Learning Tutorial": "AI & Machine Learning",
            "TensorFlow Tutorial": "AI & Machine Learning",
        }

        # Update videos based on title mapping
        for video_title, new_category in video_category_map.items():
            cur.execute("UPDATE course_videos SET category = ? WHERE video_title LIKE ?",
                       (new_category, f"%{video_title}%"))

        # Add some videos to categories that might be missing
        additional_videos = [
            ("Advanced Python Concepts", "https://www.youtube.com/embed/9R4Z1wBhH3A", "Programming Languages"),
            ("Modern JavaScript ES6+", "https://www.youtube.com/embed/9R4Z1wBhH3A", "Web Development"),
            ("React Hooks Deep Dive", "https://www.youtube.com/embed/9R4Z1wBhH3A", "Web Development"),
            ("Advanced SQL Queries", "https://www.youtube.com/embed/9R4Z1wBhH3A", "Databases"),
            ("Docker & Kubernetes", "https://www.youtube.com/embed/9R4Z1wBhH3A", "DevOps & Cloud"),
            ("Neural Networks Explained", "https://www.youtube.com/embed/9R4Z1wBhH3A", "AI & Machine Learning"),
            ("Data Structures & Algorithms", "https://www.youtube.com/embed/9R4Z1wBhH3A", "Programming Languages"),
            ("REST API Development", "https://www.youtube.com/embed/9R4Z1wBhH3A", "Web Development"),
            ("Database Design Principles", "https://www.youtube.com/embed/9R4Z1wBhH3A", "Databases"),
            ("Cloud Architecture Patterns", "https://www.youtube.com/embed/9R4Z1wBhH3A", "DevOps & Cloud"),
        ]

        for title, url, category in additional_videos:
            # Check if video already exists
            cur.execute("SELECT COUNT(*) FROM course_videos WHERE video_title = ? AND category = ?",
                       (title, category))
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO course_videos (course_id, video_title, video_url, category) VALUES (?, ?, ?, ?)",
                           (None, title, url, category))

        conn.commit()
        conn.close()
        logger.info("Video categories updated successfully")

    except Exception as e:
        logger.error(f"Video category update error: {e}")

update_video_categories()

# Replace unavailable video URLs with working YouTube videos
def update_video_urls():
    """Replace unavailable video URLs with working YouTube videos"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Video URL replacements - working YouTube videos
        video_url_updates = {
            # AI & Machine Learning
            "Neural Networks Explained": "https://www.youtube.com/embed/aircAruvnKk",
            "TensorFlow Tutorial": "https://www.youtube.com/embed/tPYj3fFJGjk",

            # Career Guidance
            "Building a Successful Tech Career": "https://www.youtube.com/embed/h2H9EhGJ5uI",
            "Career Planning & Goal Setting": "https://www.youtube.com/embed/LW3vT4K2EI",
            "Freelancing vs Full-time Jobs": "https://www.youtube.com/embed/8VpFxStAMnE",
            "How to Choose the Right Career Path": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder for now
            "Industry Trends & Future Skills": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder for now
            "Networking & Professional Development": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder for now
            "Salary Negotiation for Tech Professionals": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder for now
            "Work-Life Balance in Tech Careers": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder for now

            # Data Science & ML
            "Deep Learning Crash Course": "https://www.youtube.com/embed/0VH1lim8gL8",
            "MATLAB Tutorial": "https://www.youtube.com/embed/oxp5Q1o8i2A",
            "Machine Learning Tutorial": "https://www.youtube.com/embed/7eh4d6sabA0",
            "PyTorch Tutorial": "https://www.youtube.com/embed/GIsg-ZUy0MY",
            "Python for Data Science": "https://www.youtube.com/embed/rfscVS0vtbw",

            # Databases
            "Advanced SQL Queries": "https://www.youtube.com/embed/HXV3zeQKqGY",  # SQL Tutorial
            "Database Design Principles": "https://www.youtube.com/embed/qw--VYLpxG4",  # PostgreSQL
            "Firebase Database Guide": "https://www.youtube.com/embed/V2aer4xDq1g",
            "MongoDB Crash Course": "https://www.youtube.com/embed/ofme2o29ngU",
            "MySQL Database Tutorial": "https://www.youtube.com/embed/9ylj9NR0Lcg",
            "PostgreSQL Tutorial": "https://www.youtube.com/embed/qw--VYLpxG4",
            "Redis In-Memory Database": "https://www.youtube.com/embed/GHc-Qj4X1PA",
            "SQL Tutorial for Beginners": "https://www.youtube.com/embed/HXV3zeQKqGY",

            # DevOps & Cloud
            "AWS Tutorial for Beginners": "https://www.youtube.com/embed/k1RI5locZE4",
            "Azure Tutorial": "https://www.youtube.com/embed/5ABEkZqwXrE",
            "Cloud Architecture Patterns": "https://www.youtube.com/embed/m6FhKQpRXqg",  # Cloud Architecture
            "Docker & Kubernetes": "https://www.youtube.com/embed/fqMOX6JJhGo",  # Docker Tutorial
            "Docker Tutorial for Beginners": "https://www.youtube.com/embed/fqMOX6JJhGo",
            "Git Tutorial for Beginners": "https://www.youtube.com/embed/8JJ101D3knE",
            "Kubernetes Tutorial": "https://www.youtube.com/embed/X48VuDVv0do",
            "Linux Tutorial for Beginners": "https://www.youtube.com/embed/v_1zB2WNN14",

            # Mobile Development
            "Android Development Tutorial": "https://www.youtube.com/embed/fis26HvvDII",
            "Flutter Tutorial for Beginners": "https://www.youtube.com/embed/VPvVD8t02U8",
            "Ionic Framework Tutorial": "https://www.youtube.com/embed/YrDQ2Cz7Ff0",
            "React Native Tutorial": "https://www.youtube.com/embed/0-S5a0eXPoc",
            "Xamarin Development Guide": "https://www.youtube.com/embed/8JJ101D3knE",  # Git Tutorial as placeholder
            "iOS Development Tutorial": "https://www.youtube.com/embed/8hP9D6kZseM",

            # Programming Languages
            "Advanced Python Concepts": "https://www.youtube.com/embed/rfscVS0vtbw",  # Python Tutorial
            "C# Programming Fundamentals": "https://www.youtube.com/embed/0QUgvfuKvWU",
            "C++ Programming Tutorial": "https://www.youtube.com/embed/vLnPwxZdW4Y",
            "Data Structures & Algorithms": "https://www.youtube.com/embed/5_5oE5lgrhw",  # DSA Tutorial
            "Go Programming Language": "https://www.youtube.com/embed/YS4e4q9oBaU",
            "Java Programming Tutorial": "https://www.youtube.com/embed/eIrMbAQSU34",
            "JavaScript Crash Course": "https://www.youtube.com/embed/hdI2bqOjy3c",
            "Python Tutorial for Beginners": "https://www.youtube.com/embed/rfscVS0vtbw",
            "Rust Programming Tutorial": "https://www.youtube.com/embed/zF34dRivLOw",
            "TypeScript Crash Course": "https://www.youtube.com/embed/BwuLxPH8IDs",

            # Soft Skills & Placement Prep
            "Acing Your Next Interview": "https://www.youtube.com/embed/wvj39P2MIqg",  # Interview Tips
            "Active Listening Skills": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Behavioral Interview Preparation": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Business Communication Etiquette": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Career Planning & Goal Setting": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Effective Communication Skills": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Email Writing & Professional Communication": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Group Discussion Techniques": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "HR Interview Questions & Answers": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Presentation Skills Masterclass": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Public Speaking & Confidence Building": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Resume Writing Masterclass": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Salary Negotiation Skills": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder
            "Technical Interview Preparation": "https://www.youtube.com/embed/9R4Z1wBhH3A",  # Keep placeholder

            # Web Development
            "Angular Framework Guide": "https://www.youtube.com/embed/0LhBvqxbG2Y",
            "Django Tutorial for Beginners": "https://www.youtube.com/embed/rHux0gMZ3Eg",
            "Flask Tutorial for Beginners": "https://www.youtube.com/embed/Z1RJmh_OqeA",
            "GraphQL API Development": "https://www.youtube.com/embed/ed8SzALpx1M",
            "HTML & CSS Crash Course": "https://www.youtube.com/embed/G3e-cpL7ofc",
            "Modern JavaScript ES6+": "https://www.youtube.com/embed/hdI2bqOjy3c",  # JavaScript Crash Course
            "Node.js Crash Course": "https://www.youtube.com/embed/fBNz5xF-Kx4",
            "REST API Development": "https://www.youtube.com/embed/pKd0Rpw7O48",  # REST API Tutorial
            "React Hooks Deep Dive": "https://www.youtube.com/embed/dpw9EHDh2bM",  # React Tutorial
            "React Tutorial for Beginners": "https://www.youtube.com/embed/dpw9EHDh2bM",
            "Vue.js Framework Tutorial": "https://www.youtube.com/embed/qZXt1Aom3Cs"
        }

        # Update video URLs
        for video_title, new_url in video_url_updates.items():
            cur.execute("UPDATE course_videos SET video_url = ? WHERE video_title = ?",
                       (new_url, video_title))

        # Replace remaining placeholder URLs with working videos
        placeholder_urls = [
            ("https://www.youtube.com/embed/9R4Z1wBhH3A", "https://www.youtube.com/embed/wvj39P2MIqg"),  # Interview tips
        ]

        for old_url, new_url in placeholder_urls:
            cur.execute("UPDATE course_videos SET video_url = ? WHERE video_url = ?",
                       (new_url, old_url))

        conn.commit()
        conn.close()
        logger.info("Video URLs updated successfully")

    except Exception as e:
        logger.error(f"Video URL update error: {e}")

update_video_urls()

# --- DB Helpers ---
def db_fetchall(query, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return cur.fetchall()
    except Exception as e:
        logger.error(f"DB Fetch Error: {e}")
        return []

def db_execute(query, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        logger.error(f"DB Execute Error: {e}")
        raise e

# --- ML Logic ---
def build_student_text(profile_row):
    if not profile_row: return ""
    # index 7: skills, 8: skill_ratings, 10: interests, 11: tech_stack, 9: experience
    parts = [str(profile_row[7]), str(profile_row[10]), str(profile_row[11]), str(profile_row[9])]
    return " ".join([p for p in parts if p and p != 'None']).lower()

def job_text(job_row):
    if not job_row: return ""
    # index 1: title, 2: description, 3: required_skills
    parts = [str(job_row[1]), str(job_row[2]), str(job_row[3])]
    return " ".join([p for p in parts if p and p != 'None']).lower()

def calculate_skill_match_score(profile_skills, profile_ratings, job_skills, experience_years, min_exp_required):
    """
    Calculate a realistic skill match score based on:
    - Individual skill matches with ratings
    - Skill importance levels
    - Experience requirements
    - Skill gaps analysis
    """
    if not profile_skills or not job_skills:
        return 0.0, "Insufficient profile data"

    # Parse profile skills and ratings
    skill_dict = {}
    if profile_ratings:
        ratings_list = [int(r.strip()) for r in profile_ratings.split(',') if r.strip()]
        skills_list = [s.strip().lower() for s in profile_skills.split(',') if s.strip()]

        for i, skill in enumerate(skills_list):
            rating = ratings_list[i] if i < len(ratings_list) else 3  # Default rating of 3
            skill_dict[skill] = rating

    # Parse job required skills
    job_skill_list = [s.strip().lower() for s in job_skills.split(';') if s.strip()]

    # Categorize skills by importance (technical skills are more critical)
    technical_keywords = ['python', 'java', 'javascript', 'sql', 'react', 'node', 'aws', 'docker',
                         'kubernetes', 'git', 'linux', 'tensorflow', 'pytorch', 'ml', 'ai']

    # Calculate skill matches
    matched_skills = []
    missing_skills = []
    skill_score = 0.0
    total_weight = 0.0

    for job_skill in job_skill_list:
        job_skill_lower = job_skill.lower()
        weight = 2.0 if any(keyword in job_skill_lower for keyword in technical_keywords) else 1.0
        total_weight += weight

        # Find best matching profile skill
        best_match = None
        best_rating = 0

        for profile_skill, rating in skill_dict.items():
            # Exact match gets full credit
            if profile_skill == job_skill_lower:
                best_match = profile_skill
                best_rating = rating
                break
            # Partial match (contains) gets partial credit
            elif job_skill_lower in profile_skill or profile_skill in job_skill_lower:
                if rating > best_rating:
                    best_match = profile_skill
                    best_rating = rating

        if best_match:
            matched_skills.append(f"{best_match}({best_rating})")

            # Rating-based scoring (1-5 scale)
            # Convert to 0-1 scale and apply weight
            normalized_rating = (best_rating - 1) / 4.0  # 0.0 to 1.0
            skill_score += normalized_rating * weight
        else:
            missing_skills.append(job_skill)

    # Experience factor (if experience data available)
    exp_factor = 1.0
    if experience_years is not None and min_exp_required is not None:
        try:
            exp_years = float(experience_years)
            min_exp = float(min_exp_required)
            if exp_years < min_exp:
                exp_factor = max(0.3, exp_years / min_exp)  # Penalty for insufficient experience
            elif exp_years > min_exp * 1.5:
                exp_factor = 1.1  # Bonus for extensive experience
        except:
            pass

    # Calculate final score
    if total_weight > 0:
        base_score = (skill_score / total_weight) * exp_factor

        # Apply realistic caps based on skill gaps
        skill_match_ratio = len(matched_skills) / len(job_skill_list)

        if skill_match_ratio >= 0.8:  # 80%+ skills match
            max_score = 0.85
        elif skill_match_ratio >= 0.6:  # 60%+ skills match
            max_score = 0.75
        elif skill_match_ratio >= 0.4:  # 40%+ skills match
            max_score = 0.65
        else:  # Less than 40% skills match
            max_score = 0.45

        final_score = min(base_score, max_score)

        # Generate detailed reason
        if len(missing_skills) == 0:
            reason = f"Excellent match! All {len(matched_skills)} required skills present"
        elif len(missing_skills) <= 2:
            reason = f"Good match with {len(missing_skills)} skill gap(s): {', '.join(missing_skills[:2])}"
        else:
            reason = f"Moderate match - {len(missing_skills)} missing skills including {', '.join(missing_skills[:3])}"

        return final_score, reason
    else:
        return 0.0, "Unable to analyze skills"

def recommend_jobs_logic(profile_row, all_jobs, top_k=10):
    """
    Enhanced job recommendation with accurate skill matching
    """
    from sklearn.metrics.pairwise import cosine_similarity
    recs = []

    # Extract profile data
    profile_skills = profile_row[7] if profile_row else ""  # skills
    profile_ratings = profile_row[8] if profile_row else ""  # skill_ratings
    experience_years = profile_row[9] if profile_row else None  # experience

    # AI model prediction (for additional insights)
    profile_text = build_student_text(profile_row)
    predicted_label = None
    if model:
        try:
            predicted_label = str(model.predict([profile_text])[0]).strip().lower()
        except:
            pass

    for idx, job in enumerate(all_jobs):
        job_title = (job[1] or "").lower()
        job_description = (job[2] or "")
        job_required_skills = (job[3] or "")
        min_exp_required = job[4] if len(job) > 4 else 0  # experience requirement

        # Calculate skill-based match score
        skill_score, skill_reason = calculate_skill_match_score(
            profile_skills, profile_ratings, job_required_skills,
            experience_years, min_exp_required
        )

        # Boost score slightly if AI prediction matches job title
        ai_boost = 0.0
        if predicted_label and (predicted_label in job_title or job_title in predicted_label):
            ai_boost = 0.08  # Small boost for AI career path alignment
            skill_reason += f" + AI career alignment bonus"

        # Text similarity as secondary factor (reduced weight)
        text_sim = 0.0
        if vectorizer:
            try:
                job_text_content = job_text(job)
                texts = [profile_text, job_text_content]
                tfidf = vectorizer.transform(texts)
                text_sim = float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
                text_sim *= 0.15  # Much lower weight for text similarity
            except:
                pass

        # Combine scores
        final_score = min(skill_score + ai_boost + text_sim, 0.95)  # Cap at 95% for realism

        # Only include jobs with minimum match threshold
        if final_score >= 0.25:  # 25% minimum match
            recs.append({
                "job_id": job[0],
                "score": round(final_score, 3),
                "reason": skill_reason
            })

    # Sort by score and return top matches
    return predicted_label, sorted(recs, key=lambda x: x["score"], reverse=True)[:top_k]

# --- Routes ---
@app.route("/")
def index():
    if session.get("username"):
        return redirect(url_for("admin" if session.get("role") == "admin" else "dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role, u, p = request.form.get("role"), request.form.get("username", "").strip(), request.form.get("password", "").strip()
        if role == "admin":
            if u == "admin" and p == "admin1234":
                session.update({"username": "admin", "role": "admin", "user_id": -1})
                return redirect(url_for("admin"))
            flash("Invalid Admin Credentials", "danger")
        else:
            user = db_fetchall("SELECT * FROM users WHERE username=? AND role='student'", (u,))
            if user and user[0][3] == p:
                session.update({"user_id": user[0][0], "username": user[0][1], "role": "student"})
                return redirect(url_for("dashboard"))
            flash("Invalid Username or Password", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u, e, p = request.form.get("username","").strip(), request.form.get("email","").strip(), request.form.get("password","").strip()
        if u and e and p:
            try:
                db_execute("INSERT INTO users (username, email, password, created_at) VALUES (?, ?, ?, ?)", (u, e, p, datetime.now().strftime("%Y-%m-%d %H:%M")))
                flash("Account created! Please login.", "success")
                return redirect(url_for("login"))
            except: flash("Error: Username or Email already exists.", "danger")
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if session.get("role") != "student": return redirect(url_for("login"))
    uid = session.get("user_id")
    profile = db_fetchall("SELECT * FROM student_profile WHERE user_id=?", (uid,))
    if not profile: return render_template("dashboard.html", student=None, needs_profile=True)

    # User has a profile, so needs_profile is False
    needs_profile = False

    recs = db_fetchall("SELECT j.*, r.match_score, r.match_reason FROM job_recommendations r JOIN jobs j ON r.job_id = j.id WHERE r.user_id = ? ORDER BY r.match_score DESC", (uid,))
    
    # Dynamic Filtering for Courses and Videos based on matched job skills
    matched_skills = ""
    for r in recs: matched_skills += " " + (r[3] or "")
    
    all_courses = db_fetchall("SELECT * FROM courses ORDER BY id DESC")
    filtered_courses = []
    for c in all_courses:
        # If course title or category matches profile skills or recommended job skills
        if any(skill.strip().lower() in (c[1] + " " + c[3]).lower() for skill in (profile[0][7] or "").split(",")) or any(skill.strip().lower() in (c[1] + " " + c[3]).lower() for skill in matched_skills.split(",")):
            filtered_courses.append(c)
    
    all_videos = db_fetchall("SELECT v.*, c.title FROM course_videos v LEFT JOIN courses c ON v.course_id = c.id ORDER BY v.id DESC")
    filtered_videos = []

    # Get student's skills
    student_skills = set(skill.strip().lower() for skill in (profile[0][7] or "").split(",") if skill.strip())

    # Get all recommended job skills to identify skill gaps
    recommended_job_skills = set()
    for r in recs:
        job_skills = (r[3] or "").lower().split(";")  # Assuming skills are semicolon-separated in jobs
        recommended_job_skills.update(skill.strip() for skill in job_skills if skill.strip())

    # Identify skill gaps (skills required by jobs but not possessed by student)
    skill_gaps = recommended_job_skills - student_skills

    for v in all_videos:
        video_title = (v[2] or "").lower()
        video_category = (v[4] or "").lower()

        # Always include Communication Training and Placement Preparation videos
        if video_category in ["Communication Training", "Placement Preparation"]:
            filtered_videos.append(v)
        # Filter Recommended Videos based on skill gaps (missing skills from job matches)
        elif video_category == "Recommended Videos":
            # Show videos that help fill skill gaps
            if any(gap_skill in video_title for gap_skill in skill_gaps):
                filtered_videos.append(v)
            # Also show videos related to recommended job skills that student doesn't have
            elif any(job_skill in video_title for job_skill in recommended_job_skills if job_skill not in student_skills):
                filtered_videos.append(v)
            # If no skills profile yet or no job recommendations, show some videos
            elif not profile[0][7] or not recs:
                filtered_videos.append(v)

    # Get filtered course categories that have matching courses or helpful videos
    all_course_categories = db_fetchall("SELECT DISTINCT category FROM courses ORDER BY category")

    # Get student's skills and recommended job skills for better filtering
    student_skills = set(skill.strip().lower() for skill in (profile[0][7] or "").split(",") if skill.strip())

    # Get all recommended job skills to identify skill gaps
    recommended_job_skills = set()
    for r in recs:
        job_skills = (r[3] or "").lower().split(";")  # Assuming skills are semicolon-separated in jobs
        recommended_job_skills.update(skill.strip() for skill in job_skills if skill.strip())

    # Show all categories that have courses available (let students explore all options)
    filtered_course_categories = []
    for category_row in all_course_categories:
        category_name = category_row[0]

        # Check if this category has any courses at all
        has_courses = any(c[3] == category_name for c in all_courses)

        # Include category if it has courses
        if has_courses:
            filtered_course_categories.append(category_row)

    # Get filtered video categories that have matching content (for video tabs)
    filtered_video_categories = []
    for category_row in all_course_categories:
        category_name = category_row[0]

        # Check if this category has videos
        has_videos = any(video[4] == category_name for video in all_videos)

        # Include category if it has videos
        if has_videos:
            filtered_video_categories.append(category_row)

    # Determine if profile initialization is needed
    show_first_login_alert = session.get('show_first_login_alert', False)
    needs_profile_init = "true" if (needs_profile and not show_first_login_alert) else "false"

    return render_template("dashboard.html", student=profile[0], recommendations=recs,
                           trends=db_fetchall("SELECT * FROM job_trends ORDER BY id DESC"),
                           courses=all_courses, videos=all_videos,
                           course_categories=filtered_course_categories,
                           video_categories=filtered_video_categories, needs_profile=False,
                           needs_profile_init=needs_profile_init)

@app.route("/save_profile", methods=["POST"])
def save_profile():
    if session.get("role") != "student": return redirect(url_for("login"))
    uid, f = session.get("user_id"), request.form
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    data = (uid, f.get("full_name"), f.get("register_number"), f.get("college_name"), f.get("batch_year"),
            f.get("current_semester"), f.get("skills"), f.get("skill_ratings"), f.get("experience"),
            f.get("interests"), f.get("tech_stack"), f.get("location"), now)

    if db_fetchall("SELECT id FROM student_profile WHERE user_id=?", (uid,)):
        db_execute("UPDATE student_profile SET full_name=?, register_number=?, college_name=?, batch_year=?, current_semester=?, skills=?, skill_ratings=?, experience=?, interests=?, tech_stack=?, location=?, created_at=? WHERE user_id=?", data[1:] + (uid,))
        db_execute("DELETE FROM job_recommendations WHERE user_id=?", (uid,))
    else:
        db_execute("INSERT INTO student_profile (user_id, full_name, register_number, college_name, batch_year, current_semester, skills, skill_ratings, experience, interests, tech_stack, location, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", data)

    prof = db_fetchall("SELECT * FROM student_profile WHERE user_id=?", (uid,))[0]
    label, results = recommend_jobs_logic(prof, db_fetchall("SELECT * FROM jobs"))
    for r in results:
        db_execute("INSERT INTO job_recommendations (user_id, job_id, match_score, match_reason, created_at) VALUES (?,?,?,?,?)", (uid, r["job_id"], r["score"], r["reason"], now))
    
    flash("Profile saved and recommendations updated!", "success")
    return redirect(url_for("dashboard") + "#jobs")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if session.get("role") != "admin": return redirect(url_for("login"))
    if request.method == "POST":
        act, f, now = request.form.get("action"), request.form, datetime.now().strftime("%Y-%m-%d")
        if act == "add_job": db_execute("INSERT INTO jobs (title, application_link, required_skills, description, posted_by, created_at) VALUES (?,?,?,?,'admin',?)", (f.get("title"), f.get("application_link"), f.get("required_skills"), f.get("description"), now))
        elif act == "add_course": db_execute("INSERT INTO courses (title, category, description, course_link, added_by, created_at) VALUES (?,?,?,?,'admin',?)", (f.get("title"), f.get("category"), f.get("description"), f.get("course_link"), now))
        elif act == "add_video": 
            course_id = f.get("course_id")
            if not course_id: course_id = None
            db_execute("INSERT INTO course_videos (course_id, video_title, video_url, category) VALUES (?,?,?,?)", (course_id, f.get("video_title"), f.get("video_url"), f.get("category")))
        elif act == "add_trend": db_execute("INSERT INTO job_trends (job_role, industry, trending_skills, year, added_by, created_at) VALUES (?,?,?,?,'admin',?)", (f.get("job_role"), f.get("industry"), f.get("trending_skills"), f.get("year"), now))
        
        # New Edit Logic
        elif act == "edit_course":
            db_execute("UPDATE courses SET title=?, category=?, description=?, course_link=? WHERE id=?", (f.get("title"), f.get("category"), f.get("description"), f.get("course_link"), f.get("course_id")))
            flash("Course updated successfully!", "success")
        elif act == "edit_job":
            db_execute("UPDATE jobs SET title=?, application_link=?, required_skills=?, description=? WHERE id=?", (f.get("title"), f.get("application_link"), f.get("required_skills"), f.get("description"), f.get("job_id")))
            flash("Job updated successfully!", "success")
            
        flash("Action completed successfully!", "success")
        return redirect(url_for("admin"))
    
    return render_template("admin_dashboard.html", 
                           jobs=db_fetchall("SELECT * FROM jobs ORDER BY id DESC"), 
                           courses=db_fetchall("SELECT * FROM courses ORDER BY id DESC"), 
                           videos=db_fetchall("SELECT v.*, c.title FROM course_videos v LEFT JOIN courses c ON v.course_id = c.id ORDER BY v.id DESC"), 
                           trends=db_fetchall("SELECT * FROM job_trends ORDER BY id DESC"), 
                           students=db_fetchall("SELECT * FROM student_profile ORDER BY id DESC"), 
                           users=db_fetchall("SELECT * FROM users WHERE role='student' ORDER BY id DESC"))

@app.route("/download_report")
def download_report():
    if session.get("role") != "student": return redirect(url_for("login"))
    uid = session.get("user_id")
    profile = db_fetchall("SELECT * FROM student_profile WHERE user_id=?", (uid,))
    if not profile: return redirect(url_for("dashboard"))
    p = profile[0]
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 22); c.drawCentredString(300, 750, "AI CAREER REPORT")
    c.setFont("Helvetica", 12); c.drawString(50, 700, f"Name: {p[2]}"); c.drawString(50, 680, f"College: {p[4]}"); c.drawString(50, 660, f"Skills: {p[7]}")
    c.setFont("Helvetica-Bold", 14); c.drawString(50, 620, "Matched Job Recommendations (>75% Match):")
    recs, y = db_fetchall("SELECT j.title, r.match_score FROM job_recommendations r JOIN jobs j ON r.job_id = j.id WHERE r.user_id = ? AND r.match_score >= 0.15 ORDER BY r.match_score DESC", (uid,)), 600
    for r in recs:
        score_pct = int(r[1]*100) if r[1] < 1 else 100
        c.setFont("Helvetica", 11); c.drawString(70, y, f"- {r[0]} ({score_pct}% Match)"); y -= 20
    c.showPage(); c.save(); buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Career_Report_{p[2]}.pdf", mimetype='application/pdf')

@app.route("/chat", methods=["POST"])
def chat():
    m = request.json.get("message", "").lower()
    r = "Try asking about 'jobs', 'skills', or 'courses'."
    if "job" in m: r = "Check 'Career Path' for your AI matches!"
    elif "skill" in m: r = "Updating skills in your profile will refresh your matches!"
    return {"response": r}

@app.route("/delete/<kind>/<int:oid>")
def delete(kind, oid):
    if session.get("role") != "admin": return redirect(url_for("login"))
    table_map = {
        "job": "jobs",
        "student": "student_profile",
        "user": "users",
        "course": "courses",
        "video": "course_videos",
        "trend": "job_trends"
    }
    table = table_map.get(kind)
    if table:
        try:
            db_execute(f"DELETE FROM {table} WHERE id=?", (oid,))
            if kind == "user":
                db_execute("DELETE FROM student_profile WHERE user_id=?", (oid,))
                db_execute("DELETE FROM job_recommendations WHERE user_id=?", (oid,))
            flash(f"{kind.capitalize()} deleted successfully!", "info")
        except Exception as e:
            logger.error(f"Delete Error: {e}")
            flash("Error deleting record.", "danger")
    return redirect(url_for("admin"))

@app.route("/delete_account", methods=["POST"])
def delete_account():
    uid = session.get("user_id")
    if uid:
        try:
            db_execute("DELETE FROM users WHERE id=?", (uid,))
            db_execute("DELETE FROM student_profile WHERE user_id=?", (uid,))
            db_execute("DELETE FROM job_recommendations WHERE user_id=?", (uid,))
            session.clear()
            flash("Account permanently deleted.", "info")
        except Exception as e:
            logger.error(f"Account Delete Error: {e}")
    return redirect(url_for("register"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    # use_reloader=False: debug reloader loads sklearn/pickles twice and delays bind
    # by tens of seconds; browsers opened early see ERR_CONNECTION_REFUSED.
    app.run(debug=True, use_reloader=False, host="127.0.0.1", port=5007)
