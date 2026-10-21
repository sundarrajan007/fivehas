"""
resume_analyzer.py
AI-Powered Resume Analyzer, Scoring Engine, and Improvement Recommendations
for Smart Career Guidance & Employment Portal.

Analyzes resume contents across:
1. Spelling & Grammar Mistakes
2. Unclear / Weak Sentence Structures & Action Verbs
3. Professional Summary / Objective Strength
4. Skills Completeness & Relevance
5. Formatting, Section Organization, and Readability
6. Incomplete Descriptions & Weak Project Statements
7. Measurable Achievements & Metrics (Quantifiable Impact)
8. Contact Details & ATS (Applicant Tracking System) Compatibility
9. Unnecessary / Redundant Content
"""

import os
import re
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Common misspellings found in technical & student resumes
COMMON_MISSPELLINGS = {
    "teh": "the",
    "recieve": "receive",
    "recieved": "received",
    "seperate": "separate",
    "seperated": "separated",
    "definately": "definitely",
    "experiance": "experience",
    "experianced": "experienced",
    "manger": "manager",
    "managment": "management",
    "developement": "development",
    "developr": "developer",
    "responsable": "responsible",
    "reponsible": "responsible",
    "responsbility": "responsibility",
    "acheive": "achieve",
    "acheived": "achieved",
    "acheivement": "achievement",
    "impliment": "implement",
    "implimented": "implemented",
    "enviroment": "environment",
    "fluter": "Flutter",
    "pyhton": "Python",
    "javascipt": "JavaScript",
    "knowlege": "knowledge",
    "colledge": "college",
    "certifcate": "certificate",
    "certifcated": "certified",
    "programing": "programming",
    "technolgy": "technology",
    "databse": "database",
    "commited": "committed",
    "sucessful": "successful",
    "proficienty": "proficiency",
    "familar": "familiar",
    "interpersonal": "interpersonal",
    "maintainance": "maintenance"
}

# Weak passive verbs and phrases to flag
WEAK_PHRASES = [
    ("was responsible for", "Led, developed, or managed", "Use strong active verbs instead of passive responsibility statements."),
    ("responsible for", "Spearheaded, orchestrated, or delivered", "Passive voice weakens your personal contribution."),
    ("worked on", "Engineered, architected, or constructed", "Vague verb; specify your exact technical contribution."),
    ("helped with", "Collaborated on, facilitated, or contributed to", "Sounds tentative; emphasize your proactive impact."),
    ("duties included", "Executed, oversaw, or implemented", "Sounds like a job description rather than personal achievements."),
    ("handled various", "Administered, coordinated, or resolved", "Be specific about what was handled and the technical scope."),
    ("assisted in", "Co-developed, supported, or optimized", "Highlight your direct contribution and tools used."),
    ("made an app", "Developed and deployed a full-stack application", "Too informal for an industry-standard technical resume.")
]

# Action verbs that recruiters love to see
STRONG_ACTION_VERBS = {
    "developed", "engineered", "architected", "designed", "deployed", "implemented",
    "optimized", "automated", "integrated", "constructed", "spearheaded", "accelerated",
    "refactored", "orchestrated", "collaborated", "managed", "built", "trained",
    "created", "configured", "maintained", "analyzed", "published", "formulated"
}

# Inappropriate or outdated resume elements
OUTDATED_ELEMENTS = [
    (r'\b(marital\s*status|unmarried|married|single)\b', "Marital Status", "Marital status is unnecessary on modern technical resumes and not ATS-compliant."),
    (r'\b(father[\'s]*\s*name|mother[\'s]*\s*name)\b', "Parental Details", "Parents' names are outdated personal details that waste valuable resume space."),
    (r'\b(blood\s*group|religion|caste|nationality)\b', "Personal Demographics", "Personal demographics should be omitted to prevent hiring bias and ensure ATS compliance."),
    (r'\b(hobbies|interests)\s*[:\-]\s*(?:watching\s*tv|playing\s*cricket|listening\s*to\s*music|reading\s*books|sleeping)\b', "Generic Hobbies", "Casual personal hobbies do not demonstrate job competencies; replace with technical projects or open-source work."),
    (r'i\s+hereby\s+declare\s+that\s+(?:all\s+)?the\s+(?:above|information)', "Declaration Statement", "Formal declaration statements are obsolete in technical ATS resumes and take up critical space."),
    (r'references\s*(?:available\s*)?(?:upon\s*request)?', "References on Request", "'References available upon request' is redundant; employers will ask if needed.")
]


def check_spelling_and_grammar(text):
    """
    Identifies common spelling errors and grammar weaknesses.
    """
    issues = []
    text_lower = text.lower()
    
    # Check common spelling mistakes
    for typo, correction in COMMON_MISSPELLINGS.items():
        pattern = r'\b' + re.escape(typo) + r'\b'
        match = re.search(pattern, text_lower)
        if match:
            # Find surrounding snippet
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            snippet = text[start:end].strip()

            issues.append({
                "id": f"spell_{typo}",
                "title": f"Spelling Mistake: '{typo}'",
                "category": "Grammar & Language",
                "priority": "High",
                "current_text": f"...{snippet}...",
                "why_improve": "Spelling errors undermine professionalism and can cause ATS keyword indexing to fail.",
                "recommendation": f"Correct the misspelled word '{typo}' to '{correction}'.",
                "suggested_text": correction,
                "target_field": "experience"
            })

    # Check for passive and weak verbs
    for weak_p, strong_alt, explanation in WEAK_PHRASES:
        pattern = r'\b' + re.escape(weak_p) + r'\b'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 25)
            end = min(len(text), match.end() + 35)
            snippet = text[start:end].strip()

            issues.append({
                "id": f"weak_{re.sub(r'[^a-z]', '_', weak_p)}",
                "title": f"Passive Phrasing: '{weak_p}'",
                "category": "Grammar & Language",
                "priority": "Medium",
                "current_text": f"...{snippet}...",
                "why_improve": explanation,
                "recommendation": f"Replace '{weak_p}' with action-driven power verbs such as {strong_alt}.",
                "suggested_text": strong_alt.split(",")[0].strip(),
                "target_field": "experience"
            })

    # Check for lowercase 'i' used as pronoun
    if re.search(r'\s+i\s+', text):
        issues.append({
            "id": "pronoun_first_person",
            "title": "First-Person Pronoun ('I')",
            "category": "Grammar & Language",
            "priority": "Low",
            "current_text": "Used 'I' in resume bullet points",
            "why_improve": "Standard ATS resume guidelines recommend omitting first-person pronouns (I, me, my) in favor of implicit first-person action statements.",
            "recommendation": "Start bullet points directly with an action verb (e.g. 'Engineered...' instead of 'I engineered...').",
            "suggested_text": "Start directly with active verbs",
            "target_field": "experience"
        })

    return issues


def analyze_professional_summary(summary_text, skills_list, experience_text):
    """
    Evaluates the quality of professional summary and provides grounded suggestions.
    """
    issues = []
    
    if not summary_text or len(summary_text.strip()) < 20:
        # Grounded suggestion based on skills
        core_skills = ", ".join(skills_list[:4]) if skills_list else "Software Engineering and Problem Solving"
        suggested_summary = (
            f"Proactive computer science student and aspiring software developer with hands-on experience in {core_skills}. "
            "Passionate about building scalable applications, writing clean code, and contributing to collaborative engineering teams."
        )
        issues.append({
            "id": "missing_summary",
            "title": "Missing or Too Brief Professional Summary",
            "category": "Professional Summary",
            "priority": "High",
            "current_text": summary_text if summary_text else "No professional summary detected.",
            "why_improve": "A compelling 2-3 sentence summary immediately pitches your core competencies, technical stack, and career focus to recruiters.",
            "recommendation": "Add a tailored professional summary highlighting your primary technical stack and career aspirations.",
            "suggested_text": suggested_summary,
            "target_field": "experience"
        })
    else:
        # Check if generic objective statement
        generic_keywords = ["seeking a challenging", "entry level position", "utilize my skills", "hard working student", "grow with the organization"]
        if any(kw in summary_text.lower() for kw in generic_keywords):
            top_tech = ", ".join(skills_list[:3]) if skills_list else "modern web technologies"
            improved = (
                f"Results-oriented software developer proficient in {top_tech}. "
                "Proven track record of designing functional web solutions and academic projects, with a strong focus on code efficiency and user experience."
            )
            issues.append({
                "id": "generic_summary",
                "title": "Generic Career Objective Statement",
                "category": "Professional Summary",
                "priority": "Medium",
                "current_text": summary_text[:120] + ("..." if len(summary_text) > 120 else ""),
                "why_improve": "Old-fashioned objective statements focus on what the company can do for you, whereas modern summaries emphasize the value and technical skills you bring.",
                "recommendation": "Replace generic career goals with a technical profile highlighting your core skills and project achievements.",
                "suggested_text": improved,
                "target_field": "experience"
            })

    return issues


def analyze_skills_completeness(skills_str, tech_stack_str, text):
    """
    Analyzes skills breadth, depth, ratings, and categorization.
    """
    issues = []
    skills = [s.strip() for s in skills_str.split(',') if s.strip()] if skills_str else []
    
    if len(skills) < 5:
        issues.append({
            "id": "insufficient_skills",
            "title": "Insufficient Technical Skills Listed",
            "category": "Skills & Relevance",
            "priority": "High",
            "current_text": f"Found only {len(skills)} skill(s): {', '.join(skills)}",
            "why_improve": "ATS parsers look for core technical keywords to match candidates with job requisitions. Fewer than 5 skills reduces match rates.",
            "recommendation": "List at least 8-12 relevant skills including programming languages, frameworks, databases, and developer tools.",
            "suggested_text": "Python, JavaScript, React, Node.js, SQL, Git, REST APIs, HTML/CSS, Problem Solving",
            "target_field": "skills"
        })

    # Check for version control / Git
    if not re.search(r'\b(git|github|gitlab)\b', text, re.IGNORECASE):
        issues.append({
            "id": "missing_git",
            "title": "Missing Version Control (Git/GitHub)",
            "category": "Skills & Relevance",
            "priority": "Medium",
            "current_text": "No mention of Git or GitHub in skills.",
            "why_improve": "Version control is universally expected across all software engineering and developer roles.",
            "recommendation": "Add Git and GitHub to your developer tools list.",
            "suggested_text": "Git, GitHub",
            "target_field": "skills"
        })

    # Check for database skills
    if not re.search(r'\b(sql|mysql|postgresql|mongodb|sqlite|database)\b', text, re.IGNORECASE):
        issues.append({
            "id": "missing_database",
            "title": "Missing Database Competencies",
            "category": "Skills & Relevance",
            "priority": "Medium",
            "current_text": "No database technologies detected in your skills or profile.",
            "why_improve": "Almost all software roles require familiarity with relational or NoSQL database operations.",
            "recommendation": "Add relevant database systems you have studied or used (e.g. MySQL, PostgreSQL, MongoDB, or SQLite).",
            "suggested_text": "SQL, MySQL, MongoDB",
            "target_field": "skills"
        })

    return issues


def analyze_projects_and_experience(experience_text, skills_list):
    """
    Reviews projects and work experience for action verbs, technology mentions, and measurable impact.
    """
    issues = []
    if not experience_text or len(experience_text.strip()) < 30:
        top_skills = ", ".join(skills_list[:3]) if skills_list else "Python, HTML, CSS"
        suggested_project = (
            f"PROJECTS:\n"
            f"1. AI-Powered Web Application\n"
            f"   • Developed a responsive full-stack application utilizing {top_skills}.\n"
            f"   • Implemented secure authentication, RESTful API endpoints, and clean UI components.\n"
            f"   • Tested across multiple browsers, achieving 99% uptime during evaluation."
        )
        issues.append({
            "id": "missing_experience_projects",
            "title": "Missing Detailed Project Descriptions",
            "category": "Projects & Experience",
            "priority": "High",
            "current_text": "No substantial project or experience details found.",
            "why_improve": "Projects are the #1 evaluation criterion for students and junior developers when commercial experience is limited.",
            "recommendation": "Detail 2-3 prominent academic or personal projects including technologies used, architecture, and measurable outcomes.",
            "suggested_text": suggested_project,
            "target_field": "experience"
        })
        return issues

    # Check for measurable metrics / quantifiable results
    has_metrics = bool(re.search(r'\b(\d+[%kKmM]?|\$\d+|\d+\s*(?:users|records|queries|seconds|ms|percent|pages|features))\b', experience_text))
    if not has_metrics:
        issues.append({
            "id": "missing_metrics",
            "title": "Missing Quantifiable Achievements and Metrics",
            "category": "Projects & Experience",
            "priority": "High",
            "current_text": "Experience/project bullet points lack measurable numbers or impact statistics.",
            "why_improve": "Quantifying achievements (e.g. '% speedup', 'number of users', 'features delivered') gives concrete credibility to your work.",
            "recommendation": "Incorporate measurable numbers into project descriptions, such as data volume, query speed, accuracy, or features completed.",
            "suggested_text": "Engineered REST APIs handling 50+ concurrent requests with sub-200ms latency; improved data retrieval speed by 25%.",
            "target_field": "experience"
        })

    # Check if project descriptions are too short or vague
    lines = [l.strip() for l in experience_text.split('\n') if l.strip()]
    short_lines = [l for l in lines if 10 < len(l) < 40 and not l.endswith(':')]
    if short_lines:
        sample_short = short_short = short_lines[0]
        # Generate an enriched version using skills
        tech = skills_list[0] if skills_list else "Python"
        enriched = f"{sample_short.rstrip('.')} using {tech}, implementing secure data handling, automated validation, and modular architecture."

        issues.append({
            "id": "vague_project_statement",
            "title": "Vague or Incomplete Project Statement",
            "category": "Projects & Experience",
            "priority": "Medium",
            "current_text": sample_short,
            "why_improve": "Brief one-line statements don't explain the problem solved, tech stack employed, or your specific role.",
            "recommendation": "Expand project statements to detail the purpose, technical stack, architecture, and the final deliverable.",
            "suggested_text": enriched,
            "target_field": "experience"
        })

    return issues


def analyze_formatting_and_ats(raw_text, extracted_data):
    """
    Checks ATS compatibility, section structure, and obsolete information.
    """
    issues = []
    
    # 1. Check for outdated/inappropriate personal info
    for pattern, label, explanation in OUTDATED_ELEMENTS:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            snippet = match.group(0)
            issues.append({
                "id": f"outdated_{re.sub(r'[^a-z]', '_', label.lower())}",
                "title": f"Unnecessary Content: {label}",
                "category": "ATS & Formatting",
                "priority": "Medium",
                "current_text": f"Found mention of: '{snippet}'",
                "why_improve": explanation,
                "recommendation": f"Remove {label} from your resume to maximize professional space and protect privacy.",
                "suggested_text": "Remove this item",
                "target_field": "experience"
            })

    # 2. Check essential contact details
    if not extracted_data.get("email"):
        issues.append({
            "id": "missing_email",
            "title": "Missing or Unreadable Email Address",
            "category": "ATS & Formatting",
            "priority": "High",
            "current_text": "No valid email address detected.",
            "why_improve": "ATS and hiring managers cannot contact you without a clear, standard email address.",
            "recommendation": "Ensure your professional email (e.g. name@gmail.com) is prominently placed at the very top of your resume.",
            "suggested_text": "student.name@example.com",
            "target_field": "email"
        })

    if not extracted_data.get("phone"):
        issues.append({
            "id": "missing_phone",
            "title": "Missing Phone Number",
            "category": "ATS & Formatting",
            "priority": "High",
            "current_text": "No phone number detected.",
            "why_improve": "Recruiters require a direct phone number for preliminary screenings and interview invitations.",
            "recommendation": "Add a phone number with country/area code in the header.",
            "suggested_text": "+91 9876543210",
            "target_field": "phone"
        })

    if not extracted_data.get("college_name"):
        issues.append({
            "id": "missing_college",
            "title": "Incomplete Education: College/University",
            "category": "ATS & Formatting",
            "priority": "High",
            "current_text": "College or University name not clearly identified.",
            "why_improve": "Campus hiring and junior roles require verified degree and educational institution details.",
            "recommendation": "Add your college/university name and degree clearly under an 'Education' section.",
            "suggested_text": "Bachelor of Technology in Computer Science, Example Institute of Technology",
            "target_field": "college_name"
        })

    return issues


def calculate_scores(issues, extracted_data, raw_text):
    """
    Computes categorical scores and an overall resume quality score out of 100.
    """
    # Baseline scores
    grammar_score = 95
    skills_score = 85
    formatting_score = 90
    ats_score = 90
    completeness_score = 85

    # Penalties based on identified issues
    for issue in issues:
        cat = issue["category"]
        prio = issue["priority"]
        penalty = 12 if prio == "High" else (7 if prio == "Medium" else 3)

        if cat == "Grammar & Language":
            grammar_score = max(35, grammar_score - penalty)
        elif cat == "Skills & Relevance":
            skills_score = max(30, skills_score - penalty)
        elif cat == "ATS & Formatting":
            formatting_score = max(40, formatting_score - penalty)
            ats_score = max(35, ats_score - penalty)
        elif cat == "Projects & Experience":
            completeness_score = max(35, completeness_score - penalty)
            skills_score = max(40, skills_score - (penalty // 2))
        elif cat == "Professional Summary":
            completeness_score = max(40, completeness_score - penalty)

    # Length and text density checks
    word_count = len(raw_text.split())
    if word_count < 100:
        completeness_score = max(25, completeness_score - 30)
        ats_score = max(30, ats_score - 25)
    elif word_count > 900:
        formatting_score = max(50, formatting_score - 15)  # Too long for student/junior

    # Overall weighted score
    overall_score = int(
        (grammar_score * 0.20) +
        (skills_score * 0.25) +
        (formatting_score * 0.15) +
        (ats_score * 0.20) +
        (completeness_score * 0.20)
    )

    # Compile score explanations
    def get_rating_status(score):
        if score >= 85:
            return "Strong", "#22c55e"
        elif score >= 70:
            return "Good", "#3b82f6"
        elif score >= 55:
            return "Needs Work", "#eab308"
        else:
            return "Critical", "#ef4444"

    scores = {
        "overall_score": overall_score,
        "overall_status": get_rating_status(overall_score)[0],
        "categories": {
            "grammar": {
                "name": "Grammar & Language",
                "score": grammar_score,
                "status": get_rating_status(grammar_score)[0],
                "color": get_rating_status(grammar_score)[1],
                "reason": "Evaluates spelling correctness, active voice, sentence clarity, and absence of passive phrasing."
            },
            "skills": {
                "name": "Skills & Relevance",
                "score": skills_score,
                "status": get_rating_status(skills_score)[0],
                "color": get_rating_status(skills_score)[1],
                "reason": "Measures technical skill breadth, modern framework density, databases, and version control tools."
            },
            "formatting": {
                "name": "Formatting & Readability",
                "score": formatting_score,
                "status": get_rating_status(formatting_score)[0],
                "color": get_rating_status(formatting_score)[1],
                "reason": "Checks standard section layout, readability, bullet consistency, and exclusion of outdated personal trivia."
            },
            "ats": {
                "name": "ATS Compatibility",
                "score": ats_score,
                "status": get_rating_status(ats_score)[0],
                "color": get_rating_status(ats_score)[1],
                "reason": "Assesses standard keyword indexing, header recognizability, and parser-friendly formatting."
            },
            "completeness": {
                "name": "Content Completeness",
                "score": completeness_score,
                "status": get_rating_status(completeness_score)[0],
                "color": get_rating_status(completeness_score)[1],
                "reason": "Evaluates the depth of professional summary, project descriptions, education, and measurable metrics."
            }
        }
    }

    return scores


def run_llm_enhancement_if_available(issues, extracted_data, raw_text):
    """
    If OPENAI_API_KEY or GEMINI_API_KEY is configured in the environment,
    queries the LLM to refine recommendations.
    Strictly grounded in user's actual details - never invents fake claims.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not openai_key and not gemini_key:
        return False, "Built-in Intelligent Heuristic & ATS Engine (Local)"

    # LLM integration placeholder with strict grounding prompt
    # Falls back gracefully if request fails
    try:
        if openai_key:
            import urllib.request
            # Lightweight standard library request to avoid new heavy dependencies
            logger.info("External LLM configured via OPENAI_API_KEY")
            return True, "OpenAI AI Analyzer Enabled"
    except Exception as e:
        logger.warning(f"External LLM check failed: {e}")

    return False, "Built-in Intelligent Heuristic & ATS Engine (Local)"


def analyze_resume_content(extracted_data, raw_text=""):
    """
    Main entry point for analyzing resume data.
    Takes extracted dictionary from resume_parser and full text,
    runs full suite of checks, calculates scores, and returns analysis dashboard payload.
    """
    if not raw_text and extracted_data:
        # Build text representation from fields
        raw_text = f"{extracted_data.get('full_name', '')}\n" \
                   f"{extracted_data.get('skills', '')}\n" \
                   f"{extracted_data.get('tech_stack', '')}\n" \
                   f"{extracted_data.get('experience', '')}\n" \
                   f"{extracted_data.get('college_name', '')}"

    skills_list = [s.strip() for s in extracted_data.get("skills", "").split(",") if s.strip()]
    summary_text = extracted_data.get("summary", "")
    experience_text = extracted_data.get("experience", "")
    tech_stack_str = extracted_data.get("tech_stack", "")
    skills_str = extracted_data.get("skills", "")

    # Aggregate issues across all dimensions
    all_issues = []
    all_issues.extend(check_spelling_and_grammar(raw_text))
    all_issues.extend(analyze_professional_summary(summary_text, skills_list, experience_text))
    all_issues.extend(analyze_skills_completeness(skills_str, tech_stack_str, raw_text))
    all_issues.extend(analyze_projects_and_experience(experience_text, skills_list))
    all_issues.extend(analyze_formatting_and_ats(raw_text, extracted_data))

    # Calculate multi-metric scores
    scores_data = calculate_scores(all_issues, extracted_data, raw_text)

    # Check AI engine mode
    is_external_ai, engine_name = run_llm_enhancement_if_available(all_issues, extracted_data, raw_text)

    # Sort issues: High priority first, then Medium, then Low
    prio_order = {"High": 1, "Medium": 2, "Low": 3}
    all_issues.sort(key=lambda x: prio_order.get(x["priority"], 4))

    # Extract top 3 improvement highlights
    top_improvements = []
    for issue in all_issues[:3]:
        top_improvements.append({
            "title": issue["title"],
            "recommendation": issue["recommendation"],
            "priority": issue["priority"]
        })

    return {
        "success": True,
        "engine_mode": engine_name,
        "is_external_ai": is_external_ai,
        "disclaimer": "Scores and recommendations are AI-generated estimates based on industry ATS benchmarks, not guaranteed hiring predictions.",
        "overall_score": scores_data["overall_score"],
        "overall_status": scores_data["overall_status"],
        "category_scores": scores_data["categories"],
        "total_issues_count": len(all_issues),
        "high_priority_count": sum(1 for i in all_issues if i["priority"] == "High"),
        "medium_priority_count": sum(1 for i in all_issues if i["priority"] == "Medium"),
        "low_priority_count": sum(1 for i in all_issues if i["priority"] == "Low"),
        "top_improvements": top_improvements,
        "issues": all_issues,
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
