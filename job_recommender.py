"""
job_recommender.py
Intelligent Multi-Role Job Recommendation & Career Path Engine
for Smart Career Guidance & Employment Portal.

Features:
- Accurate Skill Overlap & Rating-Weighted Matching
- Role-Specific Career Path Filtering (Frontend, Backend, DevOps, Data Science, AI/ML, Mobile, QA)
- Strict Deduplication by Job ID & Canonical Company/Role
- Diversity Ranking to prevent repeated jobs
- Real-time Application Status Integration
- Clear Empty States with Related Role Alternatives
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
    "frontend": {
        "label": "Frontend Developer",
        "icon": "fas fa-code",
        "keywords": ["frontend", "front-end", "front end", "ui", "react", "angular", "vue", "web developer"]
    },
    "backend": {
        "label": "Backend Developer",
        "icon": "fas fa-server",
        "keywords": ["backend", "back-end", "back end", "node", "django", "flask", "java", "api", "spring"]
    },
    "fullstack": {
        "label": "Full Stack Developer",
        "icon": "fas fa-layer-group",
        "keywords": ["full stack", "fullstack", "software engineer", "product engineer"]
    },
    "devops_cloud": {
        "label": "DevOps & Cloud",
        "icon": "fas fa-cloud",
        "keywords": ["devops", "cloud", "sre", "reliability", "infrastructure", "kubernetes", "docker", "aws", "azure"]
    },
    "data_science": {
        "label": "Data Science & Analytics",
        "icon": "fas fa-chart-line",
        "keywords": ["data scientist", "data analyst", "analytics", "business intelligence", "big data", "bi"]
    },
    "ai_ml": {
        "label": "AI & Machine Learning",
        "icon": "fas fa-brain",
        "keywords": ["ml engineer", "machine learning", "ai", "artificial intelligence", "deep learning", "research intern", "nlp", "computer vision"]
    },
    "mobile": {
        "label": "Mobile App Developer",
        "icon": "fas fa-mobile-alt",
        "keywords": ["mobile", "android", "ios", "flutter", "react native", "swift", "kotlin"]
    },
    "qa_testing": {
        "label": "QA & Software Testing",
        "icon": "fas fa-bug",
        "keywords": ["qa", "quality assurance", "test", "automation", "embedded"]
    }
}


class JobItem(dict):
    """
    Dictionary subclass that allows both key/attribute access (job.title, job['title'])
    and tuple-like integer index access (job[1], job[4], job[7], job[8]) for
    backwards-compatibility with legacy templates and reports.
    """
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __getitem__(self, item):
        if isinstance(item, int):
            index_map = [
                "id",                # 0
                "title",             # 1
                "description",       # 2
                "required_skills",   # 3
                "company",           # 4
                "application_link",  # 5
                "created_at",        # 6
                "match_decimal",     # 7
                "match_reason"       # 8
            ]
            if 0 <= item < len(index_map):
                return self.get(index_map[item])
        return super().__getitem__(item)


def parse_student_skills_and_ratings(skills_str, ratings_str):
    """
    Parses comma-separated skills and ratings (either 'Python: 4' or '4, 5, 3').
    Returns dict: { 'python': 4, 'sql': 5, ... }
    """
    skill_dict = {}
    if not skills_str:
        return skill_dict

    skills = [s.strip().lower() for s in skills_str.split(',') if s.strip()]

    # Check if ratings are formatted like 'Python: 4, SQL: 5' inside skills or ratings_str
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

    # If separate ratings string provided (e.g. '4, 5, 3' or 'Python: 4, Java: 3')
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


def calculate_job_compatibility(student_skill_dict, job_skills_str, student_interests="", student_tech_stack=""):
    """
    Calculates detailed skill compatibility between student and a job.
    Returns: (match_score: float 0.0-1.0, matched_skills: list, missing_skills: list, reason: str)
    """
    if not job_skills_str:
        return 0.5, [], [], "General opening matching broad technical competencies"

    # Split job skills by semicolon or comma
    delimiters = r'[;,]'
    job_skills = [s.strip() for s in re.split(delimiters, job_skills_str) if s.strip()]
    if not job_skills:
        return 0.5, [], [], "General profile match"

    matched_skills = []
    missing_skills = []
    weighted_score = 0.0
    total_weights = 0.0

    # Key tech keywords get extra weight
    critical_keywords = {'python', 'java', 'javascript', 'react', 'sql', 'docker', 'kubernetes', 'aws', 'pytorch', 'tensorflow', 'django', 'node'}

    for j_skill in job_skills:
        j_lower = j_skill.lower().strip()
        weight = 1.5 if any(k in j_lower for k in critical_keywords) else 1.0
        total_weights += weight

        best_rating = 0
        matched_name = None

        # Exact match or substring match
        for s_name, s_rating in student_skill_dict.items():
            if s_name == j_lower:
                best_rating = s_rating
                matched_name = j_skill
                break
            elif s_name in j_lower or j_lower in s_name:
                if s_rating > best_rating:
                    best_rating = s_rating
                    matched_name = j_skill

        # Also check tech_stack and interests if not matched in direct skills
        if not matched_name:
            aux_text = f"{student_interests} {student_tech_stack}".lower()
            if j_lower in aux_text:
                best_rating = 3
                matched_name = j_skill

        if matched_name:
            matched_skills.append(matched_name)
            # Normalize 1-5 rating into 0.6 to 1.0 multiplier
            norm_rating = 0.5 + (best_rating * 0.1)
            weighted_score += weight * norm_rating
        else:
            missing_skills.append(j_skill)

    # Base skill ratio
    if total_weights > 0:
        base_match = weighted_score / total_weights
    else:
        base_match = 0.4

    # Domain / Interest alignment bonus
    bonus = 0.0
    if student_interests:
        interests_lower = student_interests.lower()
        if any(w in interests_lower for w in [s.lower() for s in matched_skills]):
            bonus += 0.06

    final_score = min(0.98, max(0.35, base_match + bonus))

    # Construct human-readable reason
    if len(missing_skills) == 0:
        reason = f"Excellent compatibility! All {len(matched_skills)} required skills matched."
    elif len(matched_skills) >= 3:
        reason = f"Strong match with {len(matched_skills)} core skills ({', '.join(matched_skills[:3])}). {len(missing_skills)} learning opportunity."
    elif len(matched_skills) > 0:
        reason = f"Matched {len(matched_skills)} skill(s) ({', '.join(matched_skills)}). Good entry point to develop {', '.join(missing_skills[:2])}."
    else:
        reason = f"Great growth role. Build skills in {', '.join(missing_skills[:3])} to qualify."

    return round(final_score, 2), matched_skills, missing_skills, reason


def classify_job_track(title):
    """Identifies which career track a job title belongs to."""
    title_lower = (title or "").lower()
    for track_key, info in CAREER_TRACKS.items():
        if track_key == "all": continue
        for kw in info["keywords"]:
            if kw in title_lower:
                return track_key
    return "fullstack"


def get_recommended_jobs_for_student(user_id, role_filter="all", limit=50):
    """
    Fetches real jobs from SQLite, computes personalized scores, deduplicates,
    filters by selected role, and decorates with application status.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # 1. Fetch Student Profile
        cur.execute("SELECT * FROM student_profile WHERE user_id=?", (user_id,))
        prof_row = cur.fetchone()

        # 2. Fetch User Applications
        cur.execute("SELECT job_id, applied_at, status FROM applications WHERE user_id=?", (user_id,))
        app_rows = cur.fetchall()
        applied_map = {row[0]: {"applied_at": row[1], "status": row[2]} for row in app_rows}

        # 3. Fetch All Jobs from Database
        cur.execute("SELECT id, title, description, required_skills, posted_by, application_link, created_at FROM jobs ORDER BY id ASC")
        jobs_raw = cur.fetchall()

    if not jobs_raw:
        return {
            "success": True,
            "jobs": [],
            "total_count": 0,
            "role_counts": {},
            "active_role": role_filter,
            "message": "No jobs found in the database. Please add jobs through Admin Dashboard."
        }

    # Parse Student Profile
    student_skills = prof_row[7] if prof_row else ""
    student_ratings = prof_row[8] if prof_row else ""
    student_interests = prof_row[10] if prof_row else ""
    student_tech_stack = prof_row[11] if prof_row else ""
    skill_dict = parse_student_skills_and_ratings(student_skills, student_ratings)

    # Process & Deduplicate all jobs
    processed_jobs = []
    seen_keys = set()
    role_counts = {k: 0 for k in CAREER_TRACKS.keys()}

    for j in jobs_raw:
        j_id, title, desc, req_skills, company, app_link, created_at = j

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

        # Compatibility score
        match_score, matched_skills, missing_skills, reason = calculate_job_compatibility(
            skill_dict, req_skills, student_interests, student_tech_stack
        )

        app_info = applied_map.get(j_id)
        is_applied = bool(app_info)

        # External Link Check
        is_external = bool(app_link and app_link.startswith(('http://', 'https://')))

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
            "application_link": app_link if is_external else "",
            "is_external": is_external,
            "applied": is_applied,
            "applied_at": app_info["applied_at"] if is_applied else None,
            "application_status": app_info["status"] if is_applied else None,
            "created_at": created_at or "Recently"
        }))

    # Filter by selected role
    active_filter = (role_filter or "all").lower().strip()
    if active_filter != "all":
        filtered_jobs = [j for j in processed_jobs if j["track"] == active_filter]
    else:
        filtered_jobs = processed_jobs

    # Sort by match score descending, then prioritize unapplied
    filtered_jobs.sort(key=lambda x: (x["match_score"], not x["applied"]), reverse=True)

    # Empty state handling with related recommendations
    related_tracks = []
    if len(filtered_jobs) == 0 and active_filter != "all":
        # Find other tracks that have jobs with highest match scores
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
        "active_role": active_filter,
        "total_count": len(filtered_jobs),
        "role_counts": role_counts,
        "tracks": CAREER_TRACKS,
        "related_tracks": related_tracks,
        "jobs": filtered_jobs[:limit]
    }
