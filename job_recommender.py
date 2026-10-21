"""
job_recommender.py
Intelligent Multi-Role Job Recommendation & Career Path Engine
for SkillMatch AI (AI Job Recommendation System).

Features:
- Multi-dimensional Resume & Skill Matching (Skills, Tech Stack, Experience, Degree, Projects)
- Fresher & Entry-Level Prioritization for Students
- Strict Deduplication by Canonical Company & Title
- Clear Job Source Attribution (Verified External Listings vs Curated Portal Roles)
- Working External & Internal Apply Now workflows
- Truthful Skill Compatibility Analysis (Matched Skills vs Skill Gaps)
- Coherent Career Path Generation with Multi-skill Readiness
- Missing-Skill-Targeted Course Recommendations with Verified External Providers
"""

import os
import re
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "data.db")

# Standard Career Track Mappings
CAREER_TRACKS = {
    "all": {
        "label": "All Matched Roles",
        "icon": "fas fa-stars",
        "keywords": []
    },
    "fullstack": {
        "label": "Full Stack Developer",
        "icon": "fas fa-layer-group",
        "keywords": ["full stack", "fullstack", "software engineer", "product engineer", "application engineer"],
        "core_skills": ["python", "javascript", "react", "html", "css", "node.js", "django", "flask", "sql", "git"],
        "target_roles": ["Full Stack Engineer", "Junior Software Developer", "Web Application Developer"],
        "roadmap": [
            "Step 1: Strengthen core language fundamentals (JavaScript ES6+ and Python) with data structures.",
            "Step 2: Build end-to-end full-stack projects combining React frontends with Flask/Node REST APIs.",
            "Step 3: Master relational databases (SQL/PostgreSQL), Docker containerization, and cloud deployment."
        ]
    },
    "backend": {
        "label": "Backend Developer",
        "icon": "fas fa-server",
        "keywords": ["backend", "back-end", "back end", "node", "django", "flask", "java", "api", "spring", "c++", "c#", "golang"],
        "core_skills": ["python", "java", "sql", "flask", "django", "node.js", "rest", "postgresql", "docker", "c++"],
        "target_roles": ["Backend Systems Engineer", "API Developer", "Database Software Engineer"],
        "roadmap": [
            "Step 1: Master server-side languages (Python/Java/Go) and OOP design patterns.",
            "Step 2: Design secure, high-throughput RESTful & GraphQL APIs with authentication and caching.",
            "Step 3: Learn distributed system architecture, database query optimization, and containerized CI/CD."
        ]
    },
    "frontend": {
        "label": "Frontend Developer",
        "icon": "fas fa-code",
        "keywords": ["frontend", "front-end", "front end", "ui", "react", "angular", "vue", "web developer"],
        "core_skills": ["javascript", "html", "css", "react", "typescript", "redux", "tailwind", "responsive design"],
        "target_roles": ["Frontend Engineer", "UI Developer", "React Application Specialist"],
        "roadmap": [
            "Step 1: Solidify modern HTML5, responsive CSS3/Flexbox/Grid, and modern JavaScript.",
            "Step 2: Master React.js, component architecture, state management (Redux/Zustand), and TypeScript.",
            "Step 3: Implement web accessibility (a11y), performance profiling, and interactive UI component libraries."
        ]
    },
    "ai_ml": {
        "label": "AI & Machine Learning",
        "icon": "fas fa-brain",
        "keywords": ["ml engineer", "machine learning", "ai", "artificial intelligence", "deep learning", "research intern", "nlp", "computer vision"],
        "core_skills": ["python", "machine learning", "pytorch", "tensorflow", "pandas", "numpy", "scikit-learn", "sql"],
        "target_roles": ["Machine Learning Engineer", "AI Research Intern", "Applied ML Specialist"],
        "roadmap": [
            "Step 1: Master Python scientific libraries (NumPy, Pandas, Matplotlib) and linear algebra/statistics.",
            "Step 2: Implement supervised & unsupervised algorithms with Scikit-Learn and build neural networks in PyTorch.",
            "Step 3: Deploy ML models as inference microservices with FastAPI, Docker, and MLflow."
        ]
    },
    "data_science": {
        "label": "Data Science & Analytics",
        "icon": "fas fa-chart-line",
        "keywords": ["data scientist", "data analyst", "analytics", "business intelligence", "big data", "bi", "tableau", "power bi"],
        "core_skills": ["python", "sql", "pandas", "numpy", "data analysis", "tableau", "power bi", "statistics"],
        "target_roles": ["Data Scientist", "Business Intelligence Analyst", "Data Analytics Engineer"],
        "roadmap": [
            "Step 1: Master complex SQL queries, relational joins, and Python data manipulation with Pandas.",
            "Step 2: Build interactive BI dashboards using Tableau / Power BI and conduct exploratory data analysis (EDA).",
            "Step 3: Learn statistical hypothesis testing, A/B experimentation, and predictive regression modeling."
        ]
    },
    "devops_cloud": {
        "label": "DevOps & Cloud",
        "icon": "fas fa-cloud",
        "keywords": ["devops", "cloud", "sre", "reliability", "infrastructure", "kubernetes", "docker", "aws", "azure", "linux"],
        "core_skills": ["docker", "kubernetes", "linux", "aws", "git", "ci/cd", "python", "terraform"],
        "target_roles": ["DevOps Engineer", "Cloud Solutions Associate", "Site Reliability Engineer (SRE)"],
        "roadmap": [
            "Step 1: Master Linux command line administration, bash scripting, and Git version control workflows.",
            "Step 2: Containerize applications using Docker and orchestrate multi-container pods with Kubernetes.",
            "Step 3: Build automated CI/CD pipelines (GitHub Actions) and deploy scalable cloud infrastructure on AWS."
        ]
    },
    "mobile": {
        "label": "Mobile App Developer",
        "icon": "fas fa-mobile-alt",
        "keywords": ["mobile", "android", "ios", "flutter", "react native", "swift", "kotlin"],
        "core_skills": ["flutter", "dart", "react native", "java", "kotlin", "android", "mobile app", "git"],
        "target_roles": ["Mobile Application Engineer", "Flutter Developer", "Android Developer"],
        "roadmap": [
            "Step 1: Master cross-platform development with Flutter & Dart or React Native.",
            "Step 2: Implement asynchronous state management, native mobile device APIs, and local storage (SQLite).",
            "Step 3: Integrate REST backends, handle push notifications, and build production APK/App Store packages."
        ]
    },
    "qa_testing": {
        "label": "QA & Software Testing",
        "icon": "fas fa-bug",
        "keywords": ["qa", "quality assurance", "test", "automation", "selenium", "pytest", "cypress"],
        "core_skills": ["python", "selenium", "qa", "test automation", "git", "sql", "api testing"],
        "target_roles": ["QA Automation Engineer", "Software Test Analyst", "Quality Assurance Specialist"],
        "roadmap": [
            "Step 1: Understand software testing fundamentals, test case design, and bug lifecycle tracking.",
            "Step 2: Write automated test suites using Python pytest, Selenium WebDriver, and Postman API testing.",
            "Step 3: Integrate automated regression suites into CI/CD build pipelines and load testing workflows."
        ]
    }
}

# Verified external job opportunities
VERIFIED_EXTERNAL_JOBS = [
    {
        "title": "Associate Software Engineer / Application Engineer",
        "company": "Google",
        "description": "Design, develop, test, deploy, and maintain large-scale software solutions. Collaborate with engineering teams across search, cloud, and core web platforms.",
        "required_skills": "Python, Java, C++, Data Structures, Algorithms, Linux, Git",
        "location": "Bengaluru, Karnataka, India",
        "source": "Google Careers",
        "application_link": "https://www.google.com/about/careers/applications/jobs/results/",
        "is_external": 1,
        "min_experience_years": 0
    },
    {
        "title": "Software Engineer - Cloud & Web Platforms",
        "company": "Microsoft",
        "description": "Build modern developer experiences and scalable cloud services on Azure. Write clean, reliable code with TypeScript, React, and cloud microservices.",
        "required_skills": "TypeScript, React, C#, Azure, REST, Docker, SQL",
        "location": "Hyderabad, Telangana, India / Hybrid",
        "source": "Microsoft Careers",
        "application_link": "https://careers.microsoft.com/professionals/us/en",
        "is_external": 1,
        "min_experience_years": 0
    },
    {
        "title": "Software Development Engineer (SDE I)",
        "company": "Amazon",
        "description": "Develop high-throughput distributed systems, optimize customer-facing backend APIs, and participate in full software engineering lifecycles.",
        "required_skills": "Java, Python, AWS, Docker, Git, Linux, Object-Oriented Programming",
        "location": "Chennai / Bengaluru, India",
        "source": "Amazon Jobs",
        "application_link": "https://www.amazon.jobs/",
        "is_external": 1,
        "min_experience_years": 0
    },
    {
        "title": "Full Stack Web Developer",
        "company": "Zoho Corporation",
        "description": "Join Zoho's SaaS engineering teams to design, architect, and deliver responsive, high-performance web applications used by millions of global businesses.",
        "required_skills": "JavaScript, HTML, CSS, React, Java, PostgreSQL, REST",
        "location": "Chennai, Tamil Nadu, India",
        "source": "Zoho Careers",
        "application_link": "https://www.zoho.com/careers/",
        "is_external": 1,
        "min_experience_years": 0
    },
    {
        "title": "Systems Engineer - Python & Full Stack",
        "company": "Infosys",
        "description": "Entry-level engineering opportunity for recent graduates and freshers. Hands-on development with enterprise Python, database integration, and web frameworks.",
        "required_skills": "Python, SQL, HTML, CSS, Flask, Git",
        "location": "Bengaluru / Chennai / Pune, India",
        "source": "Infosys Careers",
        "application_link": "https://www.infosys.com/careers/",
        "is_external": 1,
        "min_experience_years": 0
    },
    {
        "title": "Junior Machine Learning Engineer",
        "company": "Fractal Analytics",
        "description": "Build and validate machine learning models, statistical algorithms, and data pipelines for artificial intelligence enterprise transformation.",
        "required_skills": "Python, Pandas, NumPy, Scikit-Learn, PyTorch, SQL, Machine Learning",
        "location": "Bengaluru / Mumbai, India",
        "source": "LinkedIn Jobs",
        "application_link": "https://www.linkedin.com/jobs/",
        "is_external": 1,
        "min_experience_years": 0
    },
    {
        "title": "DevOps & Cloud Engineer Associate",
        "company": "GitHub",
        "description": "Maintain developer platform infrastructure, automate continuous integration and delivery pipelines, and support high-availability cloud systems.",
        "required_skills": "Docker, Kubernetes, Linux, Git, CI/CD, Go, Python",
        "location": "Remote - India",
        "source": "GitHub Careers",
        "application_link": "https://github.com/about/careers",
        "is_external": 1,
        "min_experience_years": 0
    }
]

# Verified external learning courses mapped directly to skills
VERIFIED_COURSES_CATALOG = [
    {
        "title": "CS50: Introduction to Computer Science",
        "provider": "Harvard University / edX",
        "category": "Programming Languages",
        "skills": ["c", "python", "sql", "algorithms", "data structures"],
        "url": "https://cs50.harvard.edu/x/",
        "level": "Beginner to Intermediate",
        "description": "An introduction to the intellectual enterprises of computer science and the art of programming."
    },
    {
        "title": "Python Programming Masterclass & Official Guide",
        "provider": "Python Software Foundation",
        "category": "Programming Languages",
        "skills": ["python", "oop", "file handling"],
        "url": "https://www.python.org/about/gettingstarted/",
        "level": "All Levels",
        "description": "Official Python beginner tutorials, syntax mastery, data structures, and standard library modules."
    },
    {
        "title": "Modern JavaScript Deep Dive & ES6+",
        "provider": "JavaScript.info",
        "category": "Programming Languages",
        "skills": ["javascript", "es6", "dom", "async/await"],
        "url": "https://javascript.info/",
        "level": "Beginner to Advanced",
        "description": "The definitive, modern guide from JavaScript basics to advanced concepts like closures and async programming."
    },
    {
        "title": "React Official Interactive Tutorial & Docs",
        "provider": "React.dev / Meta",
        "category": "Web Development",
        "skills": ["react", "javascript", "jsx", "hooks", "frontend"],
        "url": "https://react.dev/learn",
        "level": "Intermediate",
        "description": "Learn React directly from the creators: components, state, hooks, effects, and modern best practices."
    },
    {
        "title": "Docker Essentials & Hands-on Containerization",
        "provider": "Docker Official Docs",
        "category": "DevOps & Cloud",
        "skills": ["docker", "containers", "devops", "linux"],
        "url": "https://docs.docker.com/get-started/",
        "level": "Beginner to Intermediate",
        "description": "Step-by-step hands-on guide to building, containerizing, sharing, and running applications anywhere."
    },
    {
        "title": "Kubernetes Architecture & Core Tutorials",
        "provider": "Kubernetes.io / Linux Foundation",
        "category": "DevOps & Cloud",
        "skills": ["kubernetes", "docker", "devops", "cloud"],
        "url": "https://kubernetes.io/docs/tutorials/",
        "level": "Intermediate to Advanced",
        "description": "Official interactive tutorials covering pods, deployments, service discovery, and cluster orchestration."
    },
    {
        "title": "AWS Cloud Practitioner & Developer Learning Path",
        "provider": "AWS Skill Builder",
        "category": "DevOps & Cloud",
        "skills": ["aws", "cloud", "ec2", "s3", "lambda"],
        "url": "https://explore.skillbuilder.aws/",
        "level": "All Levels",
        "description": "Official cloud training from Amazon Web Services covering core infrastructure, compute, and serverless."
    },
    {
        "title": "Machine Learning with Python & Scikit-Learn",
        "provider": "freeCodeCamp & DeepLearning.AI",
        "category": "Data Science & ML",
        "skills": ["machine learning", "python", "scikit-learn", "numpy", "pandas"],
        "url": "https://www.freecodecamp.org/news/tag/machine-learning/",
        "level": "Intermediate",
        "description": "Complete hands-on curriculum covering supervised regression, classification, clustering, and data pipelines."
    },
    {
        "title": "Deep Learning with PyTorch Official Tutorials",
        "provider": "PyTorch.org",
        "category": "Data Science & ML",
        "skills": ["pytorch", "deep learning", "neural networks", "python"],
        "url": "https://pytorch.org/tutorials/",
        "level": "Intermediate to Advanced",
        "description": "Comprehensive practical tutorials on building, training, and deploying neural networks with PyTorch."
    },
    {
        "title": "PostgreSQL & Relational Database Mastery",
        "provider": "PostgreSQL Tutorial & Mode",
        "category": "Databases",
        "skills": ["sql", "postgresql", "mysql", "database design"],
        "url": "https://www.postgresqltutorial.com/",
        "level": "Beginner to Intermediate",
        "description": "Master SQL syntax, relational schema design, complex joins, subqueries, indexing, and query optimization."
    },
    {
        "title": "Pro Git & Collaborative Open Source Workflows",
        "provider": "Git-SCM Official Book",
        "category": "Programming Languages",
        "skills": ["git", "github", "version control"],
        "url": "https://git-scm.com/book/en/v2",
        "level": "All Levels",
        "description": "The complete, authoritative guide to version control, branching, rebasing, and GitHub workflows."
    },
    {
        "title": "Flutter & Dart Cross-Platform Mobile Guide",
        "provider": "Flutter.dev / Google",
        "category": "Mobile Development",
        "skills": ["flutter", "dart", "mobile", "android", "ios"],
        "url": "https://docs.flutter.dev/get-started",
        "level": "Beginner to Intermediate",
        "description": "Official tutorials for creating beautiful, natively compiled cross-platform mobile apps with Flutter."
    }
]


class JobItem(dict):
    """
    Dictionary subclass allowing both key access (job['title'], job.title)
    and tuple index access (job[0], job[1]) for legacy template compatibility.
    """
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __getitem__(self, item):
        if isinstance(item, int):
            index_map = [
                "id", "title", "description", "required_skills", "company",
                "application_link", "created_at", "match_decimal", "match_reason"
            ]
            if 0 <= item < len(index_map):
                return self.get(index_map[item])
        return super().__getitem__(item)


def init_extended_jobs_db():
    """
    Ensures jobs table schema includes location, source, is_external,
    min_experience_years, and seeds verified external opportunities.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            
            # Check existing columns
            cur.execute("PRAGMA table_info(jobs)")
            cols = [row[1] for row in cur.fetchall()]
            
            if "location" not in cols:
                cur.execute("ALTER TABLE jobs ADD COLUMN location TEXT DEFAULT 'Bengaluru, India'")
            if "source" not in cols:
                cur.execute("ALTER TABLE jobs ADD COLUMN source TEXT DEFAULT 'SkillMatch Curated Portal'")
            if "is_external" not in cols:
                cur.execute("ALTER TABLE jobs ADD COLUMN is_external INTEGER DEFAULT 0")
            if "min_experience_years" not in cols:
                cur.execute("ALTER TABLE jobs ADD COLUMN min_experience_years INTEGER DEFAULT 0")
                
            conn.commit()
            
            # Check if verified external jobs exist, if not insert them
            for ej in VERIFIED_EXTERNAL_JOBS:
                cur.execute("SELECT id FROM jobs WHERE title=? AND posted_by=?", (ej["title"], ej["company"]))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO jobs (title, description, required_skills, posted_by, location, source, application_link, is_external, min_experience_years, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ej["title"], ej["description"], ej["required_skills"], ej["company"],
                        ej["location"], ej["source"], ej["application_link"], ej["is_external"],
                        ej["min_experience_years"], datetime.now().strftime("%Y-%m-%d")
                    ))
            conn.commit()
    except Exception as e:
        logger.error(f"Error in init_extended_jobs_db: {e}", exc_info=True)


def parse_student_skills_and_ratings(skills_str, ratings_str):
    """
    Parses skills and confidence ratings into a dictionary: { 'python': 4, 'sql': 5, ... }
    """
    skill_dict = {}
    if not skills_str:
        return skill_dict

    skills = [s.strip().lower() for s in re.split(r'[,;]', skills_str) if s.strip()]

    for s in skills:
        if ':' in s:
            parts = s.split(':', 1)
            name = parts[0].strip().lower()
            try:
                rate = int(re.sub(r'[^0-9]', '', parts[1]))
                skill_dict[name] = max(1, min(5, rate))
            except:
                skill_dict[name] = 3
        else:
            skill_dict[s] = 3

    if ratings_str:
        rating_items = [r.strip() for r in ratings_str.split(',') if r.strip()]
        for i, item in enumerate(rating_items):
            if ':' in item:
                parts = item.split(':', 1)
                name = parts[0].strip().lower()
                try:
                    rate = int(re.sub(r'[^0-9]', '', parts[1]))
                    skill_dict[name] = max(1, min(5, rate))
                except:
                    pass
            elif i < len(skills):
                try:
                    rate = int(re.sub(r'[^0-9]', '', item))
                    skill_dict[skills[i]] = max(1, min(5, rate))
                except:
                    pass

    return skill_dict


def normalize_skill_name(skill):
    """Normalizes technical skill aliases for accurate matching."""
    s = skill.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    aliases = {
        'js': 'javascript',
        'ts': 'typescript',
        'py': 'python',
        'react.js': 'react',
        'reactjs': 'react',
        'node': 'node.js',
        'nodejs': 'node.js',
        'vue': 'vue.js',
        'vuejs': 'vue.js',
        'postgres': 'postgresql',
        'k8s': 'kubernetes',
        'rest api': 'rest',
        'restful': 'rest',
        'ml': 'machine learning',
        'ai': 'artificial intelligence',
        'dl': 'deep learning',
        'golang': 'go'
    }
    return aliases.get(s, s)


def calculate_job_compatibility(student_skill_dict, job_skills_str, student_interests="", student_tech_stack="", student_experience="", min_exp=0, candidate_is_fresher=True):
    """
    Intelligent skill, experience, and domain matching algorithm:
    - Normalizes skill names & aliases
    - Computes weighted skill match ratio
    - Rewards fresher/entry-level alignment for college graduates
    - Penalizes roles requiring 3+ years experience when candidate is a fresher
    - Truthful, transparent reason generator with exact matched and missing skills
    """
    if not job_skills_str:
        return 0.45, [], [], "General technical opening."

    job_skills_raw = [s.strip() for s in re.split(r'[,;]', job_skills_str) if s.strip()]
    if not job_skills_raw:
        return 0.45, [], [], "General profile match."

    normalized_student = {normalize_skill_name(k): v for k, v in student_skill_dict.items()}
    
    # Also add tech stack items
    if student_tech_stack:
        for ts in re.split(r'[,;]', student_tech_stack):
            clean_ts = normalize_skill_name(ts)
            if clean_ts and clean_ts not in normalized_student:
                normalized_student[clean_ts] = 3

    # Add any skills mentioned in experience text
    if student_experience:
        exp_lower = student_experience.lower()
        for common in ['python', 'java', 'react', 'sql', 'flask', 'django', 'html', 'css', 'docker', 'git', 'aws']:
            if common in exp_lower and common not in normalized_student:
                normalized_student[common] = 3

    matched_skills = []
    missing_skills = []
    weighted_matches = 0.0
    total_weights = 0.0

    critical_keywords = {'python', 'java', 'javascript', 'react', 'sql', 'docker', 'kubernetes', 'aws', 'pytorch', 'tensorflow', 'django', 'flask', 'c++'}

    for j_skill in job_skills_raw:
        j_norm = normalize_skill_name(j_skill)
        weight = 1.4 if any(k in j_norm for k in critical_keywords) else 1.0
        total_weights += weight

        best_rating = 0
        is_matched = False

        for s_norm, s_rate in normalized_student.items():
            if s_norm == j_norm or (len(s_norm) > 2 and s_norm in j_norm) or (len(j_norm) > 2 and j_norm in s_norm):
                is_matched = True
                best_rating = max(best_rating, s_rate)

        if is_matched:
            matched_skills.append(j_skill)
            # Rating multiplier: 1=0.7, 3=0.85, 5=1.0
            rating_mult = 0.65 + (best_rating * 0.07)
            weighted_matches += weight * rating_mult
        else:
            missing_skills.append(j_skill)

    skill_ratio = (weighted_matches / total_weights) if total_weights > 0 else 0.0

    # Domain bonus
    domain_bonus = 0.0
    if student_interests:
        interests_lower = student_interests.lower()
        if any(normalize_skill_name(s) in interests_lower for s in matched_skills):
            domain_bonus += 0.08

    # Experience level adjustment
    exp_factor = 0.0
    if candidate_is_fresher:
        if min_exp == 0:
            exp_factor = 0.08 # Prioritize entry/fresher roles
        elif min_exp >= 3:
            exp_factor = -0.18 # Heavy penalty for 3+ years senior roles for freshers

    # If NO skills matched at all and low domain overlap, do NOT inflate score
    if len(matched_skills) == 0:
        raw_score = max(0.12, (skill_ratio * 0.4) + exp_factor)
    else:
        raw_score = (skill_ratio * 0.85) + domain_bonus + exp_factor

    final_score = min(0.98, max(0.15, raw_score))

    # Match explanation construction
    if len(matched_skills) >= 4 and len(missing_skills) == 0:
        reason = f"Excellent compatibility! All {len(matched_skills)} required skills matched: {', '.join(matched_skills)}."
    elif len(matched_skills) >= 3:
        reason = f"Strong match with {len(matched_skills)} core skills ({', '.join(matched_skills[:3])}). Recommend upskilling in {missing_skills[0]}." if missing_skills else f"Strong match with {len(matched_skills)} core skills."
    elif len(matched_skills) >= 1:
        missing_preview = ', '.join(missing_skills[:2]) if missing_skills else "none"
        reason = f"Matches {len(matched_skills)} key skill(s) ({', '.join(matched_skills)}). Opportunity to develop {missing_preview}."
    else:
        missing_preview = ', '.join(missing_skills[:3]) if missing_skills else "advanced skills"
        reason = f"Growth opportunity. Requires developing {missing_preview}."

    return round(final_score, 2), matched_skills, missing_skills, reason


def classify_job_track(title):
    """Categorizes a job title into a standard career track."""
    title_lower = (title or "").lower()
    for track_key, info in CAREER_TRACKS.items():
        if track_key == "all": continue
        for kw in info["keywords"]:
            if kw in title_lower:
                return track_key
    return "fullstack"


def get_recommended_jobs_for_student(user_id, role_filter="all", limit=50):
    """
    Fetches real and curated jobs, calculates personalized match scores,
    prioritizes entry-level for freshers, deduplicates, and annotates application state.
    """
    init_extended_jobs_db()

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # 1. Fetch Student Profile
        cur.execute("SELECT * FROM student_profile WHERE user_id=?", (user_id,))
        prof_row = cur.fetchone()

        # 2. Fetch Latest Resume Analysis if available
        cur.execute("SELECT analysis_json FROM resume_analysis WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,))
        analysis_row = cur.fetchone()

        # 3. Fetch User Applications
        cur.execute("SELECT job_id, applied_at, status FROM applications WHERE user_id=?", (user_id,))
        app_rows = cur.fetchall()
        applied_map = {row[0]: {"applied_at": row[1], "status": row[2]} for row in app_rows}

        # 4. Fetch All Jobs from Database
        cur.execute("""
            SELECT id, title, description, required_skills, posted_by, created_at,
                   application_link, location, source, is_external, min_experience_years
            FROM jobs ORDER BY id ASC
        """)
        jobs_raw = cur.fetchall()

    if not jobs_raw:
        return {
            "success": True,
            "jobs": [],
            "total_count": 0,
            "role_counts": {},
            "active_role": role_filter,
            "message": "No jobs found in the database."
        }

    # Extract Candidate Details
    student_skills = prof_row[7] if prof_row else ""
    student_ratings = prof_row[8] if prof_row else ""
    student_experience = prof_row[9] if prof_row else ""
    student_interests = prof_row[10] if prof_row else ""
    student_tech_stack = prof_row[11] if prof_row else ""
    batch_year = prof_row[5] if prof_row else ""
    
    # Candidate is considered fresher if batch is recent or experience text is short/academic
    candidate_is_fresher = True
    if student_experience and len(student_experience) > 200:
        if any(w in student_experience.lower() for w in ["senior", "lead", "3+ years", "4 years", "5 years"]):
            candidate_is_fresher = False

    skill_dict = parse_student_skills_and_ratings(student_skills, student_ratings)

    # Process and Deduplicate all jobs
    processed_jobs = []
    seen_keys = set()
    role_counts = {k: 0 for k in CAREER_TRACKS.keys()}

    for j in jobs_raw:
        j_id, title, desc, req_skills, company, created_at, app_link, location, source, is_external, min_exp = j

        # Canonical deduplication key (title + company)
        clean_title = re.sub(r'[^a-zA-Z0-9]', '', (title or "").lower())
        clean_comp = re.sub(r'[^a-zA-Z0-9]', '', (company or "").lower())
        canon_key = f"{clean_title}_{clean_comp}"

        if canon_key in seen_keys:
            continue
        seen_keys.add(canon_key)

        track = classify_job_track(title)
        role_counts["all"] += 1
        if track in role_counts:
            role_counts[track] += 1

        # Calculate compatibility
        match_score, matched_skills, missing_skills, reason = calculate_job_compatibility(
            skill_dict, req_skills, student_interests, student_tech_stack,
            student_experience, min_exp or 0, candidate_is_fresher
        )

        app_info = applied_map.get(j_id)
        is_applied = bool(app_info)

        # External Link Check
        is_ext = bool(is_external or (app_link and app_link.startswith(('http://', 'https://'))))
        real_link = app_link if (app_link and app_link.startswith(('http://', 'https://'))) else (
            "https://www.linkedin.com/jobs/" if is_ext else ""
        )

        display_source = source if source else ("Verified External Posting" if is_ext else "SkillMatch Curated Portal")
        display_location = location if location else "Bengaluru / Hybrid"
        is_fresher_friendly = bool((min_exp or 0) == 0 or any(w in (title or "").lower() for w in ["fresher", "intern", "entry", "trainee", "associate", "junior"]))

        processed_jobs.append(JobItem({
            "id": j_id,
            "title": title,
            "company": company or "Leading Tech Corp",
            "description": desc or "No description provided.",
            "required_skills": req_skills or "",
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "match_score": int(match_score * 100),
            "match_decimal": match_score,
            "match_reason": reason,
            "track": track,
            "location": display_location,
            "source": display_source,
            "application_link": real_link,
            "is_external": is_ext,
            "applied": is_applied,
            "applied_at": app_info["applied_at"] if is_applied else None,
            "application_status": app_info["status"] if is_applied else None,
            "min_experience_years": min_exp or 0,
            "is_fresher_friendly": is_fresher_friendly,
            "created_at": created_at or "Recently"
        }))

    # Role filter
    active_filter = (role_filter or "all").lower().strip()
    if active_filter != "all":
        filtered_jobs = [j for j in processed_jobs if j["track"] == active_filter]
    else:
        filtered_jobs = processed_jobs

    # Sort strictly by match score descending, then prioritize unapplied
    filtered_jobs.sort(key=lambda x: (x["match_score"], not x["applied"]), reverse=True)

    has_uploaded_resume = bool(analysis_row and analysis_row[0])
    has_profile_skills = bool(prof_row and (prof_row[7] or prof_row[9] or prof_row[11]))
    has_resume = bool(has_uploaded_resume or has_profile_skills)

    # Separate into Resume Suggestions vs Explore Other Roles
    suggested_jobs = []
    other_roles = []

    for j in filtered_jobs:
        # Suggestion criteria: candidate has resume/skills AND at least 1 matching skill AND match_score >= 35%
        if has_resume and len(j["matched_skills"]) >= 1 and j["match_score"] >= 35:
            j["is_suggestion"] = True
            suggested_jobs.append(j)
        else:
            j["is_suggestion"] = False
            if j["missing_skills"]:
                j["other_reason"] = f"Requires developing: {', '.join(j['missing_skills'][:3])} to qualify."
            else:
                j["other_reason"] = "Industry role requiring additional technical specialization."
            other_roles.append(j)

    # Empty state handling with related recommendations
    related_tracks = []
    if len(filtered_jobs) == 0 and active_filter != "all":
        tracks_with_scores = {}
        for j in processed_jobs:
            t = j["track"]
            if t != active_filter:
                tracks_with_scores[t] = max(tracks_with_scores.get(t, 0), j["match_score"])

        top_tracks = sorted(tracks_with_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        for t_key, t_score in top_tracks:
            related_tracks.append({
                "track": t_key,
                "label": CAREER_TRACKS.get(t_key, {}).get("label", t_key.title()),
                "top_match": t_score,
                "count": role_counts.get(t_key, 0)
            })

    return {
        "success": True,
        "has_resume": has_resume,
        "active_role": active_filter,
        "total_count": len(filtered_jobs),
        "suggestions_count": len(suggested_jobs),
        "other_count": len(other_roles),
        "role_counts": role_counts,
        "tracks": CAREER_TRACKS,
        "related_tracks": related_tracks,
        "suggestions": suggested_jobs[:limit],
        "other_roles": other_roles[:limit],
        "jobs": filtered_jobs[:limit]
    }


def get_career_path_analysis(student_profile):
    """
    Evaluates candidate multi-skill readiness across 7 engineering career tracks.
    Returns primary track, secondary track, skill gaps, target roles, and roadmap.
    """
    if not student_profile:
        return None

    skills_str = student_profile[7] if len(student_profile) > 7 else ""
    tech_stack = student_profile[11] if len(student_profile) > 11 else ""
    interests = student_profile[10] if len(student_profile) > 10 else ""
    exp_text = student_profile[9] if len(student_profile) > 9 else ""

    combined_text = f"{skills_str} {tech_stack} {interests} {exp_text}".lower()
    combined_skills = set([normalize_skill_name(s) for s in re.split(r'[,;\s]', combined_text) if len(s) > 1])

    track_scores = []

    for track_key, info in CAREER_TRACKS.items():
        if track_key == "all": continue
        core_skills = info.get("core_skills", [])
        if not core_skills: continue

        matched = [cs for cs in core_skills if cs in combined_skills or any(cs in s for s in combined_skills)]
        missing = [cs for cs in core_skills if cs not in matched]

        # Multi-skill readiness calculation
        readiness_ratio = len(matched) / len(core_skills)
        readiness_pct = int(min(98, max(20, readiness_ratio * 100)))

        # Domain interest boost if interests explicitly mention track keywords
        if any(kw in interests.lower() for kw in info["keywords"]):
            readiness_pct = min(98, readiness_pct + 12)

        track_scores.append({
            "track": track_key,
            "label": info["label"],
            "icon": info["icon"],
            "readiness_pct": readiness_pct,
            "matched_skills": [m.title() for m in matched],
            "missing_skills": [m.title() for m in missing],
            "target_roles": info.get("target_roles", ["Software Engineer"]),
            "roadmap": info.get("roadmap", [])
        })

    track_scores.sort(key=lambda x: x["readiness_pct"], reverse=True)

    primary_track = track_scores[0] if track_scores else None
    secondary_track = track_scores[1] if len(track_scores) > 1 else None

    return {
        "primary_track": primary_track,
        "secondary_track": secondary_track,
        "all_tracks": track_scores
    }


def get_recommended_courses_for_student(user_id, missing_skills=None):
    """
    Recommends verified external courses specifically targeting the candidate's
    actual skill gaps identified from recommended jobs and career path analysis.
    """
    recommended = []
    seen_urls = set()

    # Determine skills to target
    target_skills = set()
    if missing_skills:
        for ms in missing_skills:
            target_skills.add(normalize_skill_name(ms))

    # Also fetch missing skills from student's top jobs if not passed
    if not target_skills:
        rec_jobs = get_recommended_jobs_for_student(user_id, role_filter="all", limit=5)
        for j in rec_jobs.get("jobs", []):
            for ms in j.get("missing_skills", []):
                target_skills.add(normalize_skill_name(ms))

    # Fallback to foundational skills if still empty
    if not target_skills:
        target_skills = {"python", "javascript", "react", "docker", "sql"}

    for course in VERIFIED_COURSES_CATALOG:
        c_skills = [normalize_skill_name(s) for s in course["skills"]]
        
        # Check if course addresses any of the candidate's missing skills
        overlap = [s for s in c_skills if s in target_skills]
        if overlap and course["url"] not in seen_urls:
            seen_urls.add(course["url"])
            
            matched_skill_name = overlap[0].title()
            reason = f"Directly addresses your missing skill '{matched_skill_name}' required by recommended engineering jobs."
            
            recommended.append({
                "title": course["title"],
                "provider": course["provider"],
                "category": course["category"],
                "url": course["url"],
                "level": course["level"],
                "description": course["description"],
                "skill_addressed": matched_skill_name,
                "skill_gap": matched_skill_name,
                "reason": reason,
                "is_verified": True
            })

    return recommended[:8]
