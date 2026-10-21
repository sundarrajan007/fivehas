"""
resume_parser.py
Robust Resume Parser for Smart Career Guidance & Employment Portal
Extracts text from PDF and DOCX files and performs entity extraction
for Career Profile auto-fill:
- Full Name
- Email & Phone
- Register Number (if present)
- College / University
- Batch Year & Semester
- Location
- Skills, Skill Ratings, Tech Stack, Interests
- Summary, Work Experience, Projects, Certifications
"""

import os
import re
import tempfile
import logging
import io

logger = logging.getLogger(__name__)

# Try importing PDF and DOCX libraries
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import docx2txt
except ImportError:
    docx2txt = None


# Comprehensive Technical & Professional Skills List
COMMON_SKILLS = [
    # Languages
    "Python", "Java", "C++", "C#", "C", "JavaScript", "TypeScript", "PHP", "Ruby",
    "Swift", "Kotlin", "Go", "Rust", "R", "Dart", "Scala", "MATLAB", "Perl",
    # Web & Frontend
    "HTML", "HTML5", "CSS", "CSS3", "React", "React.js", "Angular", "AngularJS",
    "Vue.js", "Next.js", "Bootstrap", "Tailwind CSS", "Tailwind", "jQuery", "Redux",
    "Sass", "Webpack", "Vite", "Responsive Design",
    # Backend & Frameworks
    "Node.js", "Express.js", "Express", "Django", "Flask", "FastAPI", "Spring Boot",
    "Spring", "ASP.NET", ".NET", "Laravel", "Ruby on Rails", "REST API", "RESTful APIs",
    "GraphQL", "Microservices", "Socket.io",
    # Databases
    "SQL", "MySQL", "PostgreSQL", "MongoDB", "SQLite", "Oracle", "Redis",
    "Cassandra", "DynamoDB", "Firebase", "Firestore", "MariaDB",
    # Cloud, DevOps & Tools
    "AWS", "Azure", "GCP", "Google Cloud", "Docker", "Kubernetes", "Git", "GitHub",
    "GitLab", "CI/CD", "Jenkins", "Linux", "Unix", "Nginx", "Apache", "Jira",
    "Postman", "Terraform", "Ansible",
    # AI / ML & Data Science
    "Machine Learning", "Deep Learning", "Artificial Intelligence", "NLP",
    "Computer Vision", "Data Science", "Pandas", "NumPy", "Scikit-Learn", "SciPy",
    "TensorFlow", "Keras", "PyTorch", "OpenCV", "Data Analysis", "Data Visualization",
    "Power BI", "Tableau", "Matplotlib", "Seaborn", "Big Data", "Hadoop", "Spark",
    # Mobile
    "Android", "iOS", "Flutter", "React Native", "Android Studio",
    # Core CS & Methodologies
    "Data Structures", "Algorithms", "Object-Oriented Programming", "OOP",
    "Agile", "Scrum", "SDLC", "System Design", "Operating Systems", "Computer Networks",
    "DBMS", "Cybersecurity", "Network Security", "Cryptography",
    # Soft & Management Skills
    "Problem Solving", "Team Leadership", "Communication", "Critical Thinking",
    "Time Management", "Project Management"
]

# Tech Stack Categorization
TECH_STACK_ITEMS = {
    "React", "Angular", "Vue.js", "Next.js", "Node.js", "Express.js", "Express",
    "Django", "Flask", "FastAPI", "Spring Boot", "Laravel", "ASP.NET",
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "SQLite", "Firebase",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "Flutter", "React Native"
}

# Domain / Interest Mapping based on detected skills
DOMAIN_MAPPINGS = [
    {
        "domain": "Artificial Intelligence & Machine Learning",
        "keywords": ["machine learning", "deep learning", "nlp", "tensorflow", "pytorch", "keras", "scikit-learn", "computer vision", "artificial intelligence", "data science"]
    },
    {
        "domain": "Full Stack Web Development",
        "keywords": ["react", "node.js", "express", "django", "flask", "angular", "vue.js", "html", "css", "javascript", "full stack", "frontend", "backend"]
    },
    {
        "domain": "Data Science & Analytics",
        "keywords": ["pandas", "numpy", "power bi", "tableau", "data analysis", "data visualization", "sql", "r", "statistics", "big data", "hadoop", "spark"]
    },
    {
        "domain": "Cloud & DevOps",
        "keywords": ["aws", "azure", "gcp", "docker", "kubernetes", "ci/cd", "jenkins", "terraform", "cloud", "linux", "devops"]
    },
    {
        "domain": "Mobile Application Development",
        "keywords": ["flutter", "react native", "android", "ios", "swift", "kotlin", "mobile app"]
    },
    {
        "domain": "Cybersecurity & Networking",
        "keywords": ["cybersecurity", "network security", "cryptography", "ethical hacking", "penetration testing", "infosec"]
    },
    {
        "domain": "Database Administration & Engineering",
        "keywords": ["postgresql", "mysql", "mongodb", "oracle", "dbms", "redis", "database design"]
    },
    {
        "domain": "Software Engineering & Systems",
        "keywords": ["c++", "java", "c#", "object-oriented programming", "data structures", "algorithms", "system design"]
    }
]

# Popular Indian & Global Locations for Quick Matching
KNOWN_LOCATIONS = [
    "Chennai", "Coimbatore", "Bengaluru", "Bangalore", "Hyderabad", "Mumbai",
    "Pune", "Delhi", "New Delhi", "Noida", "Gurugram", "Gurgaon", "Kolkata",
    "Kochi", "Cochin", "Trivandrum", "Thiruvananthapuram", "Madurai", "Salem",
    "Trichy", "Tiruchirappalli", "Erode", "Vellore", "Tirunelveli", "Mysore",
    "Mangalore", "Visakhapatnam", "Vijayawada", "Ahmedabad", "Chandigarh",
    "Jaipur", "Lucknow", "Bhubaneswar", "Indore", "Tamil Nadu", "Karnataka",
    "Kerala", "Andhra Pradesh", "Telangana", "Maharashtra"
]


def extract_text_from_pdf(file_input):
    """
    Extracts text from a PDF file stream or file path using PyPDF2.
    """
    if not PyPDF2:
        raise RuntimeError("PyPDF2 is not installed or available.")
    
    text = ""
    try:
        if isinstance(file_input, (str, bytes, bytearray)):
            if isinstance(file_input, str) and os.path.isfile(file_input):
                reader = PyPDF2.PdfReader(file_input)
            else:
                reader = PyPDF2.PdfReader(io.BytesIO(file_input))
        else:
            # File-like object / SpooledTemporaryFile / BytesIO
            file_input.seek(0)
            reader = PyPDF2.PdfReader(file_input)

        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        logger.error(f"Error reading PDF: {e}")
        raise ValueError(f"Failed to read PDF resume: {str(e)}")

    return text.strip()


def extract_text_from_docx(file_input):
    """
    Extracts text from a DOCX file stream or file path using docx2txt.
    """
    if not docx2txt:
        raise RuntimeError("docx2txt is not installed or available.")

    temp_path = None
    try:
        if isinstance(file_input, str) and os.path.isfile(file_input):
            text = docx2txt.process(file_input)
        else:
            # Write stream to temporary file for docx2txt
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
                temp_path = temp_file.name
                if hasattr(file_input, "seek"):
                    file_input.seek(0)
                    temp_file.write(file_input.read())
                elif isinstance(file_input, (bytes, bytearray)):
                    temp_file.write(file_input)
            
            text = docx2txt.process(temp_path)
    except Exception as e:
        logger.error(f"Error reading DOCX: {e}")
        raise ValueError(f"Failed to read DOCX resume: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    return text.strip() if text else ""


def extract_email(text):
    """Extract email address from text using regex."""
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    matches = re.findall(email_pattern, text)
    if matches:
        # Avoid common false positives or image extensions
        for match in matches:
            clean = match.strip().rstrip('.')
            if not clean.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                return clean
    return ""


def extract_phone(text):
    """Extract phone number using regex."""
    # Match various phone formats (Indian 10-digit, international +91..., etc.)
    phone_patterns = [
        r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}',
        r'\b\d{10}\b',
        r'(?:\+\d{1,3}\s)?(?:\d{2,5}[-\s]?\d{3,5}[-\s]?\d{3,5})'
    ]
    for pattern in phone_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            cleaned = re.sub(r'[^\d+]', '', match)
            if 10 <= len(cleaned.replace('+', '')) <= 13:
                return match.strip()
    return ""


def extract_name(text):
    """
    Extracts candidate name from the top lines of the resume text.
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return ""

    # Check first 12 lines
    non_name_keywords = {
        "resume", "curriculum", "vitae", "cv", "profile", "contact",
        "email", "phone", "address", "career", "objective", "summary",
        "experience", "education", "skills", "projects", "certifications",
        "github", "linkedin", "http", "https", "www", "page", "developer",
        "engineer", "student", "fresher", "intern"
    }

    # First check if there is an explicit "Name: XYZ"
    for line in lines[:15]:
        m = re.match(r'^(?:full\s*name|name)\s*[:\-]\s*([A-Za-z\s.\'\-]+)$', line, re.IGNORECASE)
        if m:
            name_cand = m.group(1).strip()
            if 2 <= len(name_cand.split()) <= 4:
                return name_cand.title()

    # Otherwise scan the top 8 lines for a clean 2-4 word proper name
    for line in lines[:8]:
        # Strip bullets or leading symbols
        clean_line = re.sub(r'^[•\-\*\d\.\)\s]+', '', line).strip()
        words = clean_line.split()

        # Reject if contains numbers, email symbols, slashes, or links
        if re.search(r'[@\d\\/_\(\)\[\]\{\}<>|~=+*&#^:;,]', clean_line):
            continue

        if 2 <= len(words) <= 4:
            # Check if words are predominantly alphabetic and not common keywords
            is_valid = True
            for w in words:
                w_lower = w.lower()
                if w_lower in non_name_keywords or len(w) < 2:
                    is_valid = False
                    break
            if is_valid and all(w[0].isupper() or len(w) <= 3 for w in words):
                return clean_line.title()

    return ""


def extract_register_number(text):
    """Extract register or roll number if present."""
    patterns = [
        r'(?:register\s*(?:no|number)?|reg\s*(?:no|num|number)?)\s*[:\-]?\s*([A-Za-z0-9]{5,20})\b',
        r'(?:roll\s*(?:no|num|number)?)\s*[:\-]?\s*([A-Za-z0-9]{5,20})\b',
        r'(?:student\s*id|matric\s*(?:no|number)?)\s*[:\-]?\s*([A-Za-z0-9]{5,20})\b'
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def extract_college_name(text):
    """Extract college or university name with strict boundary checks."""
    college_keywords = [
        r'\b([A-Za-z\s.,\'\-&]{2,}(?:College\s+of\s+Engineering|Institute\s+of\s+Technology|Engineering\s+College|University|College|Institute|Academy)\b[A-Za-z\s.,\'\-&]*)',
        r'\b((?:Karpagam|PSG|CIT|Amrita|Anna|SRM|VIT|Sathyabama|Loyola|SSN|Kumaraguru|Bannari\s+Amman|Kongu|Sri\s+Krishna|Government)\s+[A-Za-z\s.,\'\-&]+)'
    ]
    
    # Common non-college words to reject false positives
    disallowed = [
        "objective", "skills", "experience", "declaration", "project",
        "tracker", "performance", "goals", "metrics", "dashboard",
        "developed", "built", "designed", "react", "node", "activity"
    ]
    
    # Check lines near education headings or whole text
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines:
        for p in college_keywords:
            m = re.search(p, line, re.IGNORECASE)
            if m:
                cand = m.group(1).strip().rstrip('.,-')
                cand_lower = cand.lower()
                # Ensure it looks like a reasonable college name length and doesn't contain project/experience words
                if 8 <= len(cand) <= 80 and not any(kw in cand_lower for kw in disallowed):
                    return cand
    return ""


def extract_batch_year(text):
    """Extract graduation or batch year (e.g. 2024, 2025)."""
    # Look for range like 2021-2025 or 2020 - 2024
    range_match = re.search(r'\b(20[12]\d)\s*[-–to\s]+\s*(20[23]\d)\b', text, re.IGNORECASE)
    if range_match:
        return range_match.group(2) # Return completion/batch year

    # Look for explicit Year of Passing / Batch / Graduation
    explicit_match = re.search(r'(?:batch|passed\s*out|graduation|year\s*of\s*passing|yop)\s*[:\-]?\s*(20[123]\d)', text, re.IGNORECASE)
    if explicit_match:
        return explicit_match.group(1)

    # Search for any recent/upcoming year (2020-2028)
    years = re.findall(r'\b(20[23]\d)\b', text)
    if years:
        # Return the most plausible batch year (often the max or latest)
        return max(years)
    return ""


def extract_semester(text, batch_year=""):
    """Extract current semester (1 to 8)."""
    m = re.search(r'(?:current\s*)?sem(?:ester)?\s*[:\-]?\s*([1-8])\b', text, re.IGNORECASE)
    if m:
        return m.group(1)
    
    m2 = re.search(r'\b([1-8])(?:st|nd|rd|th)?\s*sem(?:ester)?\b', text, re.IGNORECASE)
    if m2:
        return m2.group(1)

    roman_map = {"I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7", "VIII": "8"}
    m3 = re.search(r'\b(I|II|III|IV|V|VI|VII|VIII)\s*sem(?:ester)?\b', text, re.IGNORECASE)
    if m3:
        return roman_map.get(m3.group(1).upper(), "")

    return ""


def extract_location(text):
    """Extract location from text."""
    for loc in KNOWN_LOCATIONS:
        pattern = r'\b' + re.escape(loc) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return loc
    return ""


def extract_skills_and_stack(text):
    """
    Extracts skills from text, builds tech stack, skill ratings, and interests.
    """
    text_lower = text.lower()
    matched_skills = []

    # 1. Match from predefined COMMON_SKILLS
    for skill in COMMON_SKILLS:
        # Use word boundaries or specific matching for short terms like C, R, AI
        if skill in ["C", "R"]:
            pattern = r'(?:\b|\s)' + re.escape(skill) + r'(?:[,;\s\n/]|$)'
        elif skill in ["C++", "C#", ".NET"]:
            pattern = re.escape(skill) + r'(?:[,;\s\n/]|$)'
        else:
            pattern = r'\b' + re.escape(skill) + r'\b'

        if re.search(pattern, text, re.IGNORECASE):
            if skill not in matched_skills:
                matched_skills.append(skill)

    # 2. Extract from explicit "Skills" section if present
    skills_section_text = extract_section_content(text, [
        "skills", "technical skills", "core competencies", "skills & tools",
        "key skills", "technologies", "programming languages"
    ])
    if skills_section_text:
        # Split by commas, bullets, pipes, or newlines
        tokens = re.split(r'[,|•\n\r/:]+', skills_section_text)
        for token in tokens:
            cand = token.strip().strip('-*•')
            if cand and 2 <= len(cand) <= 30:
                # If it's a clean candidate not already in list
                if not re.search(r'[@\d]', cand) and cand.lower() not in ["languages", "database", "frameworks", "tools", "web technologies"]:
                    cand_title = cand.title()
                    if cand_title not in matched_skills and cand not in matched_skills:
                        matched_skills.append(cand)

    # Ensure uniqueness while preserving order
    seen = set()
    unique_skills = []
    for s in matched_skills:
        s_lower = s.lower()
        if s_lower not in seen:
            seen.add(s_lower)
            unique_skills.append(s)

    skills_str = ", ".join(unique_skills[:20])

    # Build Skill Ratings (e.g. Python: 4, Java: 3)
    # Give higher ratings (4-5) to top matched skills, minimum 3
    ratings = []
    for idx, s in enumerate(unique_skills[:8]):
        score = 5 if idx < 2 else (4 if idx < 5 else 3)
        ratings.append(f"{s}: {score}")
    skill_ratings_str = ", ".join(ratings)

    # Build Tech Stack from matched tools/frameworks
    tech_stack = [s for s in unique_skills if s in TECH_STACK_ITEMS or any(item.lower() == s.lower() for item in TECH_STACK_ITEMS)]
    tech_stack_str = ", ".join(tech_stack[:10])

    # Infer Interests / Domains
    interests = []
    for domain_info in DOMAIN_MAPPINGS:
        if any(kw in text_lower for kw in domain_info["keywords"]):
            interests.append(domain_info["domain"])
            if len(interests) >= 3:
                break

    if not interests:
        interests = ["Full Stack Web Development", "Software Engineering"]

    interests_str = ", ".join(interests[:3])

    return skills_str, skill_ratings_str, tech_stack_str, interests_str, unique_skills


def extract_section_content(text, section_keywords):
    """
    Extracts text belonging to a specific section header (e.g., 'Projects', 'Experience').
    """
    lines = text.split('\n')
    found_section = False
    section_lines = []

    # Known common headings that signal start of a new section
    all_headings = [
        "education", "academic", "experience", "work experience", "employment",
        "internship", "internships", "projects", "academic projects", "key projects",
        "skills", "technical skills", "certifications", "certificates", "licenses",
        "summary", "professional summary", "career objective", "objective",
        "achievements", "publications", "interests", "hobbies", "declaration"
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        clean_lower = re.sub(r'[^a-zA-Z\s]', '', stripped).strip().lower()

        # Check if line is one of our target headings
        if any(clean_lower == kw or clean_lower.startswith(kw + " ") for kw in section_keywords):
            found_section = True
            continue

        # If we are inside the section and encounter another known heading, section ends
        if found_section:
            if any(clean_lower == h or clean_lower.startswith(h + " ") for h in all_headings if h not in section_keywords):
                break
            section_lines.append(stripped)

    return "\n".join(section_lines).strip()


def extract_sections(text):
    """
    Extracts Summary, Work Experience, Projects, and Certifications,
    and formats them cleanly into the Career Profile experience field.
    """
    summary = extract_section_content(text, [
        "summary", "professional summary", "profile summary", "career objective", "objective", "about me"
    ])
    experience = extract_section_content(text, [
        "experience", "work experience", "employment history", "professional experience", "internships", "internship"
    ])
    projects = extract_section_content(text, [
        "projects", "academic projects", "key projects", "personal projects"
    ])
    certifications = extract_section_content(text, [
        "certifications", "certificates", "licenses", "courses", "achievements"
    ])

    # Format into structured experience text for Career Profile
    exp_parts = []
    if summary:
        exp_parts.append(f"SUMMARY:\n{summary}")
    if experience:
        exp_parts.append(f"WORK EXPERIENCE:\n{experience}")
    if projects:
        exp_parts.append(f"PROJECTS:\n{projects}")
    if certifications:
        exp_parts.append(f"CERTIFICATIONS:\n{certifications}")

    combined_experience = "\n\n".join(exp_parts).strip()
    return summary, experience, projects, certifications, combined_experience


def parse_resume(file_input, filename):
    """
    Main entry point for parsing resume files.
    file_input: file path, file stream, or bytes
    filename: original uploaded filename (used for extension detection)
    Returns: dict with extracted fields ready for Career Profile auto-fill.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ['.pdf', '.docx']:
        raise ValueError(f"Unsupported file format: {ext}. Only PDF and DOCX files are supported.")

    # 1. Extract raw text
    if ext == '.pdf':
        raw_text = extract_text_from_pdf(file_input)
    elif ext == '.docx':
        raw_text = extract_text_from_docx(file_input)
    else:
        raw_text = ""

    if not raw_text or len(raw_text.strip()) < 20:
        raise ValueError("Could not extract readable text from the uploaded resume. Please verify the document is not an image-only scan or corrupted.")

    # 2. Extract fields
    email = extract_email(raw_text)
    phone = extract_phone(raw_text)
    name = extract_name(raw_text)
    reg_no = extract_register_number(raw_text)
    college = extract_college_name(raw_text)
    batch_year = extract_batch_year(raw_text)
    semester = extract_semester(raw_text, batch_year)
    location = extract_location(raw_text)

    skills, skill_ratings, tech_stack, interests, raw_skills_list = extract_skills_and_stack(raw_text)
    summary, work_exp, projects, certs, combined_exp = extract_sections(raw_text)

    # Fallback for experience if no specific section headers matched
    if not combined_exp and len(raw_text.split()) > 30:
        # Take first 400 characters of meaningful content
        lines = [l.strip() for l in raw_text.split('\n') if len(l.strip()) > 30]
        if lines:
            combined_exp = "\n".join(lines[:5])

    return {
        "success": True,
        "full_name": name,
        "email": email,
        "phone": phone,
        "register_number": reg_no,
        "college_name": college,
        "batch_year": batch_year,
        "current_semester": semester,
        "location": location,
        "skills": skills,
        "skill_ratings": skill_ratings,
        "interests": interests,
        "tech_stack": tech_stack,
        "experience": combined_exp,
        "summary": summary,
        "work_experience": work_exp,
        "projects": projects,
        "certifications": certs,
        "skills_count": len(raw_skills_list),
        "raw_text": raw_text
    }
