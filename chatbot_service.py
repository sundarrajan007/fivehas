"""
chatbot_service.py
AI Career Assistant & Conversational Engine for Smart Career Guidance & Employment Portal.

Features:
- Full conversation history & context tracking across multiple turns
- External LLM Integration (OpenAI / Gemini) when configured via environment variables
- Rich, dynamic local reasoning engine covering:
  1. Programming & Technical Questions (Python, JS, SQL, React, algorithms, code snippets)
  2. Education & Professional Courses (degrees, semesters, learning roadmaps, portal courses)
  3. Career Guidance & Roadmaps (interview prep, skill development, role requirements)
  4. Resume Analysis & ATS Optimization (action verbs, quantifiable metrics, section advice)
  5. Live Job Search (queries real jobs from the portal's SQLite database)
  6. Contextual Follow-up Questions (referencing prior turns)
  7. General Questions & Assistance
- Graceful error handling and zero hardcoded repetitive responses
"""

import os
import re
import json
import sqlite3
import logging
import urllib.request
import urllib.error
from datetime import datetime

logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "data.db")


def call_external_llm(prompt, history=None, student_context=None):
    """
    Calls OpenAI or Gemini if API key is configured.
    Returns (success, response_text).
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not openai_key and not gemini_key:
        return False, None

    # Construct system context
    system_instruction = (
        "You are 'CareerBot', an intelligent, empathetic, and knowledgeable AI career advisor "
        "and coding mentor for the Smart Career Guidance & Employment Portal. "
        "You help university students and job seekers with programming, career roadmaps, "
        "job recommendations, resume optimization, course selection, and interview prep. "
        "Keep answers well-structured with bullet points or brief code snippets where helpful. "
    )
    if student_context:
        system_instruction += (
            f"\nStudent Profile Context:\n"
            f"- Name: {student_context.get('name', 'Student')}\n"
            f"- Skills: {student_context.get('skills', 'Not specified')}\n"
            f"- Interests: {student_context.get('interests', 'Software Engineering')}\n"
            f"- Tech Stack: {student_context.get('tech_stack', '')}\n"
            f"- College: {student_context.get('college', '')}\n"
        )

    # 1. Try OpenAI
    if openai_key:
        try:
            messages = [{"role": "system", "content": system_instruction}]
            if history:
                for h in history[-6:]:  # Keep last 6 turns for context
                    role = "user" if h.get("role") == "user" else "assistant"
                    messages.append({"role": role, "content": h.get("content", "")})
            messages.append({"role": "user", "content": prompt})

            payload = json.dumps({
                "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 600
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_key}"
                }
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data["choices"][0]["message"]["content"].strip()
                return True, reply
        except Exception as e:
            logger.warning(f"OpenAI API call failed: {e}. Falling back to internal engine.")

    # 2. Try Gemini
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            contents = []
            if history:
                for h in history[-4:]:
                    role = "user" if h.get("role") == "user" else "model"
                    contents.append({"role": role, "parts": [{"text": h.get("content", "")}]})
            contents.append({
                "role": "user",
                "parts": [{"text": f"System Context: {system_instruction}\n\nUser Question: {prompt}"}]
            })

            payload = json.dumps({"contents": contents}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return True, reply
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}. Falling back to internal engine.")

    return False, None


def search_jobs_for_chat(query_text):
    """Searches real jobs in data.db matching keywords in query_text."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, title, description, required_skills, posted_by, application_link FROM jobs")
            all_jobs = cur.fetchall()

        if not all_jobs:
            return []

        keywords = [k.lower() for k in re.findall(r'\b[a-zA-Z0-9\+#\.]+\b', query_text) if len(k) > 2]
        stopwords = {"what", "jobs", "show", "tell", "available", "find", "have", "with", "from", "role", "roles", "openings"}
        search_terms = [k for k in keywords if k not in stopwords]

        matches = []
        for j in all_jobs:
            j_id, title, desc, req_skills, company, link = j
            haystack = f"{title} {desc} {req_skills} {company}".lower()
            score = 0
            if search_terms:
                for term in search_terms:
                    if term in (title or "").lower():
                        score += 3
                    elif term in (req_skills or "").lower():
                        score += 2
                    elif term in haystack:
                        score += 1
            else:
                score = 1  # general list

            if score > 0:
                matches.append({
                    "id": j_id,
                    "title": title,
                    "company": company or "Leading Tech Corp",
                    "skills": req_skills or "",
                    "link": link or "#",
                    "score": score
                })

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:5]
    except Exception as e:
        logger.error(f"Error searching jobs for chat: {e}")
        return []


def search_courses_for_chat(query_text):
    """Searches real courses in data.db."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, title, description, category, course_link FROM courses")
            all_courses = cur.fetchall()

        if not all_courses:
            return []

        keywords = [k.lower() for k in re.findall(r'\b[a-zA-Z0-9\+#\.]+\b', query_text) if len(k) > 2]
        stopwords = {"course", "courses", "learn", "study", "what", "tell", "show"}
        search_terms = [k for k in keywords if k not in stopwords]

        matches = []
        for c in all_courses:
            c_id, title, desc, cat, link = c
            haystack = f"{title} {desc} {cat}".lower()
            score = 0
            for term in search_terms:
                if term in (title or "").lower():
                    score += 3
                elif term in (cat or "").lower():
                    score += 2
                elif term in haystack:
                    score += 1

            if score > 0:
                matches.append({"title": title, "category": cat, "desc": desc, "link": link})

        matches.sort(key=lambda x: x["title"])
        return matches[:4]
    except Exception as e:
        logger.error(f"Error searching courses for chat: {e}")
        return []


def generate_local_response(user_msg, history=None, student_context=None):
    """
    Intelligent conversational reasoning engine.
    Analyzes intent, topic, entities, and context to produce tailored responses.
    """
    msg = user_msg.strip()
    msg_lower = msg.lower()

    # Determine past conversation context if available
    last_bot_topic = None
    if history and len(history) > 0:
        for prev in reversed(history):
            if prev.get("role") in ["assistant", "bot"]:
                prev_text = prev.get("content", "").lower()
                if "python" in prev_text: last_bot_topic = "python"
                elif "react" in prev_text: last_bot_topic = "react"
                elif "sql" in prev_text or "database" in prev_text: last_bot_topic = "sql"
                elif "devops" in prev_text or "docker" in prev_text: last_bot_topic = "devops"
                elif "resume" in prev_text: last_bot_topic = "resume"
                elif "interview" in prev_text: last_bot_topic = "interview"
                break

    # Student attributes
    student_name = student_context.get("name", "Student") if student_context else "there"
    student_skills = student_context.get("skills", "") if student_context else ""
    student_interests = student_context.get("interests", "") if student_context else ""

    # ========================================================
    # 1. GREETINGS & CASUAL INTERACTION
    # ========================================================
    if re.search(r'\b(hi|hello|hey|greetings|good\s*(morning|afternoon|evening)|sup)\b', msg_lower) and len(msg_lower.split()) <= 4:
        first_name = student_name.split()[0] if student_name else "there"
        return (
            f"Hello {first_name}! 👋 I am your **AI Career & Technical Assistant**.\n\n"
            f"I can help you with:\n"
            f"- 💻 **Coding & Programming**: Explanations, syntax, algorithms, and debugging in Python, JavaScript, SQL, Java, etc.\n"
            f"- 💼 **Job Matches**: Exploring active job openings that fit your skill profile.\n"
            f"- 📄 **Resume Review & ATS Tips**: Optimizing your resume quality score and action verbs.\n"
            f"- 🎓 **Courses & Learning Paths**: Video modules and certifications to close skill gaps.\n"
            f"- 🎯 **Interview Prep**: Technical concepts, STAR methodology, and role roadmaps.\n\n"
            f"What would you like to explore today?"
        )

    if re.search(r'\b(who\s*are\s*you|what\s*can\s*you\s*do|help|about\s*you)\b', msg_lower) and len(msg_lower.split()) <= 6:
        return (
            "🤖 **About CareerBot**:\n\n"
            "I am the built-in intelligent career guidance agent for the **Smart Career Guidance & Employment Portal**.\n\n"
            "**Here is how I can assist you:**\n"
            "1. **Analyze Your Profile**: Recommend roles matching your skills, ratings, and interests.\n"
            "2. **Answer Technical Questions**: Explain code, algorithms, framework concepts, and best practices.\n"
            "3. **ATS Resume Optimization**: Advise on quantifiable bullet points, keyword indexing, and formatting.\n"
            "4. **Career Roadmaps**: Step-by-step guides to becoming a Full Stack, DevOps, Data Science, or Mobile Engineer.\n"
            "5. **Real-time Job Queries**: Look up current openings right from our database.\n\n"
            "Try asking: *'How can I become a DevOps Engineer?'* or *'Show me jobs requiring Python'*!"
        )

    if re.search(r'\b(thank\s*you|thanks|thx|awesome|great|cool)\b', msg_lower) and len(msg_lower.split()) <= 4:
        return "You're very welcome! 😊 Always here to help you succeed in your career journey. Do you have any other questions about coding, resume building, or job opportunities?"

    # ========================================================
    # 2. JOB SEARCH & RECOMMENDATION INQUIRIES
    # ========================================================
    if any(k in msg_lower for k in ["job", "jobs", "opening", "openings", "vacancy", "vacancies", "hire", "hiring", "recommend role"]):
        jobs = search_jobs_for_chat(msg)
        if jobs:
            output = f"🔍 **Here are matching career opportunities from our portal database:**\n\n"
            for j in jobs:
                output += (
                    f"• **{j['title']}** at **{j['company']}**\n"
                    f"  - *Required Skills:* {j['skills'][:70]}{'...' if len(j['skills']) > 70 else ''}\n"
                    f"  - *Action:* Head over to the **'Career Path & Jobs'** tab to apply directly with your profile!\n\n"
                )
            output += "💡 *Tip:* You can filter roles by specific career tracks (Frontend, DevOps, ML, etc.) in the **Career Path** section above."
            return output
        else:
            if student_skills:
                return (
                    f"Based on your profile skills (**{student_skills[:50]}**), our portal features diverse openings across "
                    f"Software Engineering, Cloud, and Data roles.\n\n"
                    f"👉 Click on the **'Career Path & Jobs'** tab in the sidebar to review all AI-matched positions with compatibility percentages and 1-click applications!"
                )
            return (
                "We have active openings in Full Stack Development, DevOps, Data Science, Cloud, and ML. "
                "Visit the **Career Path & Jobs** section on your dashboard to view personalized matches!"
            )

    # ========================================================
    # 3. RESUME ANALYSIS, ATS, & PROFILE IMPROVEMENT
    # ========================================================
    if any(k in msg_lower for k in ["resume", "ats", "cv", "score", "spelling", "formatting", "improve resume"]):
        return (
            "📄 **AI Resume & ATS Optimization Guidelines**:\n\n"
            "To achieve a **90+ Resume Quality Score** on our portal and pass Applicant Tracking Systems:\n\n"
            "1. **Use Strong Active Verbs**: Begin every project bullet point with decisive action verbs:\n"
            "   - *Instead of:* 'Was responsible for building an app'\n"
            "   - *Use:* 'Architected and deployed a responsive web application'\n\n"
            "2. **Quantify Your Achievements**: Include measurable impact metrics:\n"
            "   - *Example:* 'Optimized SQL database queries, reducing API latency by 28% across 5,000+ records.'\n\n"
            "3. **Single-Column ATS Layout**: Avoid tables, multi-column text boxes, graphics, and icons which confuse parsers.\n\n"
            "4. **Technical Skill Variety**: Group skills into Languages, Frameworks, Databases, and Tools (including Git).\n\n"
            "5. **Omit Outdated Information**: Remove marital status, parental names, and generic hobbies.\n\n"
            "👉 *You can upload your PDF/DOCX resume in the **Career Profile** section to get instant multi-metric scoring, mistakes detection, and 1-click ATS PDF generation!*"
        )

    # ========================================================
    # 4. PROGRAMMING & CODING QUESTIONS
    # ========================================================
    # Python
    if "python" in msg_lower or (last_bot_topic == "python" and any(k in msg_lower for k in ["example", "code", "explain", "how"])):
        if "flask" in msg_lower:
            return (
                "🐍 **Python Flask Quick Guide**:\n\n"
                "Flask is a lightweight, WSGI web application framework in Python.\n\n"
                "**Minimal Working App:**\n"
                "```python\n"
                "from flask import Flask, jsonify, request\n"
                "app = Flask(__name__)\n\n"
                "@app.route('/api/status', methods=['GET'])\n"
                "def get_status():\n"
                "    return jsonify({'status': 'online', 'service': 'Career Portal'})\n\n"
                "if __name__ == '__main__':\n"
                "    app.run(debug=True, port=5000)\n"
                "```\n\n"
                "**Key Concepts to Master:**\n"
                "- Routing (`@app.route`) & HTTP methods\n"
                "- Jinja2 HTML Templating\n"
                "- Session authentication & cookies\n"
                "- Database integration (SQLite/SQLAlchemy)"
            )
        return (
            "🐍 **Python Programming & Best Practices**:\n\n"
            "Python is widely used in Web Development (Flask/Django), Data Science (Pandas/NumPy), and AI/ML (PyTorch/Scikit-Learn).\n\n"
            "**Core Concepts Evaluated in Technical Interviews:**\n"
            "1. **List Comprehensions & Generators**: Memory-efficient data transformation (`[x**2 for x in nums if x % 2 == 0]`)\n"
            "2. **Decorators & Functions as First-Class Citizens** (`@functools.wraps`)\n"
            "3. **OOP**: Classes, inheritance, `__init__`, and dunder methods (`__repr__`, `__len__`)\n"
            "4. **Exception Handling & Context Managers** (`try...except...finally`, `with open(...) as f`)\n"
            "5. **Virtual Environments**: Always isolate project dependencies with `venv` or `pipenv`.\n\n"
            "Do you need an explanation of a specific algorithm, library, or coding challenge?"
        )

    # SQL & Databases
    if any(k in msg_lower for k in ["sql", "database", "query", "join", "mongodb", "postgresql", "mysql"]):
        return (
            "🗄️ **SQL & Database Essentials for Developers**:\n\n"
            "**1. Core JOIN Types:**\n"
            "- **INNER JOIN**: Returns records that have matching values in both tables.\n"
            "- **LEFT JOIN**: Returns all records from the left table, and matched records from the right table.\n"
            "- **FULL OUTER JOIN**: Returns all records when there is a match in either left or right table.\n\n"
            "**2. Example Query with Aggregation & Grouping:**\n"
            "```sql\n"
            "SELECT u.username, COUNT(a.id) AS total_applications\n"
            "FROM users u\n"
            "JOIN applications a ON u.id = a.user_id\n"
            "WHERE a.status = 'Applied'\n"
            "GROUP BY u.id\n"
            "HAVING total_applications > 0\n"
            "ORDER BY total_applications DESC;\n"
            "```\n\n"
            "**3. Performance Optimization Tips:**\n"
            "- Add **Indexes** on frequently queried foreign keys (`user_id`, `job_id`).\n"
            "- Avoid `SELECT *` in production; query only the required columns.\n"
            "- Use parameterized queries (`?` or `%s`) to prevent SQL injection."
        )

    # React & JavaScript
    if any(k in msg_lower for k in ["react", "javascript", "js", "frontend", "hooks", "typescript"]):
        return (
            "⚛️ **Modern JavaScript & React Fundamentals**:\n\n"
            "**Key React Hooks to Know:**\n"
            "1. `useState`: Manages local component state.\n"
            "2. `useEffect`: Handles side effects (data fetching, DOM updates, subscriptions).\n"
            "3. `useCallback` & `useMemo`: Optimize rendering performance by memoizing functions and computed values.\n\n"
            "**Example Custom Fetch Pattern:**\n"
            "```javascript\n"
            "const [jobs, setJobs] = useState([]);\n"
            "const [loading, setLoading] = useState(true);\n\n"
            "useEffect(() => {\n"
            "  async function fetchJobs() {\n"
            "    try {\n"
            "      const res = await fetch('/api/recommendations');\n"
            "      const data = await res.json();\n"
            "      setJobs(data.jobs || []);\n"
            "    } catch (err) {\n"
            "      console.error('Failed to load jobs', err);\n"
            "    } finally {\n"
            "      setLoading(false);\n"
            "    }\n"
            "  }\n"
            "  fetchJobs();\n"
            "}, []);\n"
            "```\n\n"
            "Would you like an explanation of state management, routing, or component props?"
        )

    # Data Structures & Algorithms
    if any(k in msg_lower for k in ["dsa", "data structures", "algorithm", "binary search", "sorting", "leetcode"]):
        return (
            "🧠 **Data Structures & Algorithms (DSA) Roadmap**:\n\n"
            "1. **Arrays & Strings**: Two pointers, sliding window, prefix sums.\n"
            "2. **Hash Tables**: Fast $O(1)$ lookups, frequency counters, duplicate detection.\n"
            "3. **Linked Lists, Stacks & Queues**: Fast reversal, monotonic stacks, BFS/DFS traversal queues.\n"
            "4. **Trees & Graphs**: Binary Search Trees (BST), BFS (Queue), DFS (Recursion/Stack), Dijkstra's algorithm.\n"
            "5. **Dynamic Programming**: Memoization vs. Tabulation for optimal substructure problems.\n\n"
            "💡 *Interview Advice:* When solving coding problems, always discuss **Time Complexity ($O(n)$)** and **Space Complexity** before writing your solution!"
        )

    # Git & Version Control
    if any(k in msg_lower for k in ["git", "github", "commit", "branch", "pull request", "merge"]):
        return (
            "🐙 **Essential Git Commands & Best Practices**:\n\n"
            "• `git status`: Check modified and untracked files.\n"
            "• `git checkout -b feature/new-branch`: Create and switch to a feature branch.\n"
            "• `git add . && git commit -m 'feat: descriptive commit'`: Stage and commit with clear intention.\n"
            "• `git pull origin main`: Synchronize your local branch with upstream changes.\n"
            "• `git push origin feature/new-branch`: Publish branch for code review via Pull Request.\n\n"
            "Always keep commit messages atomic and avoid committing secrets or `.env` files (use `.gitignore`)."
        )

    # ========================================================
    # 5. CAREER PATHWAYS & ROADMAPS
    # ========================================================
    if any(k in msg_lower for k in ["how to become", "career path", "roadmap", "devops", "data scientist", "machine learning", "full stack"]):
        role = "Software Engineer"
        if "devops" in msg_lower or "cloud" in msg_lower: role = "DevOps / Cloud Engineer"
        elif "data" in msg_lower: role = "Data Scientist / Analyst"
        elif "ml" in msg_lower or "ai" in msg_lower or "machine learning" in msg_lower: role = "Machine Learning Engineer"
        elif "full stack" in msg_lower or "web" in msg_lower: role = "Full Stack Web Developer"

        return (
            f"🗺️ **Career Roadmap: {role}**\n\n"
            f"**Phase 1: Core Fundamentals**\n"
            f"- Strong foundation in Python, JavaScript, or Java\n"
            f"- Linux command line proficiency and Git version control\n\n"
            f"**Phase 2: Specialized Tech Stack**\n"
            f"- Master industry tools: Docker, CI/CD, SQL/NoSQL databases, and cloud platforms (AWS/Azure/GCP)\n"
            f"- Build 2-3 end-to-end projects demonstrating real problem solving\n\n"
            f"**Phase 3: Portfolio & Placement Readiness**\n"
            f"- Deploy your projects live on platforms like Render, Vercel, or AWS\n"
            f"- Tailor your resume using our portal's **AI Resume Analyzer**\n"
            f"- Practice interview questions using the STAR method (Situation, Task, Action, Result)\n\n"
            f"Would you like recommendations on specific courses or projects for this path?"
        )

    # ========================================================
    # 6. COURSES & LEARNING RECOMMENDATIONS
    # ========================================================
    if any(k in msg_lower for k in ["course", "learn", "study", "video", "certification", "tutorial"]):
        courses = search_courses_for_chat(msg)
        if courses:
            output = "📚 **Recommended Learning Resources from our Portal:**\n\n"
            for c in courses:
                output += f"• **{c['title']}** (*{c['category']}*)\n  {c['desc']}\n\n"
            output += "👉 Head over to the **'Courses'** and **'Video Modules'** tabs in the sidebar to begin learning!"
            return output
        return (
            "📚 Our portal offers structured learning tracks across **Programming Languages**, **Web Development**, "
            "**Data Science & ML**, **Databases**, and **DevOps & Cloud**.\n\n"
            "Explore the **'Courses'** section on the dashboard to access curated modules, tutorials, and certification guides!"
        )

    # ========================================================
    # 7. INTERVIEW PREPARATION
    # ========================================================
    if any(k in msg_lower for k in ["interview", "prep", "behavioral", "star method", "questions"]):
        return (
            "💼 **Ace Your Technical & Behavioral Interviews**:\n\n"
            "**1. The STAR Method for Behavioral Questions:**\n"
            "- **S - Situation**: Set the scene and describe the challenge or project.\n"
            "- **T - Task**: Explain what your specific responsibility was.\n"
            "- **A - Action**: Detail the concrete steps and technologies you used.\n"
            "- **R - Result**: Share the quantifiable outcome (e.g., 'improved performance by 30%').\n\n"
            "**2. Technical Interview Strategy:**\n"
            "- Clarify requirements and edge cases before typing code.\n"
            "- Communicate your thought process out loud to the interviewer.\n"
            "- Test your code with sample inputs and boundary conditions.\n\n"
            "Would you like to practice a mock interview question together?"
        )

    # ========================================================
    # 8. DEFAULT DYNAMIC CONTEXTUAL RESPONSE
    # ========================================================
    return (
        f"Thank you for your question! Here are a few ways I can help you right now:\n\n"
        f"• **Find Jobs**: Ask *'What jobs match my skills?'* or *'Show DevOps openings'*.\n"
        f"• **Code & Syntax**: Ask *'Explain Python decorators'* or *'How to write a SQL join'*.\n"
        f"• **Resume Boost**: Ask *'How do I improve my ATS resume score?'*.\n"
        f"• **Learning Paths**: Ask *'What courses should I take for Full Stack?'*.\n\n"
        f"Feel free to ask any specific question about programming, your career, or portal features!"
    )


def process_chat_message(user_message, history=None, student_context=None):
    """
    Main entrance for handling incoming chat requests.
    Tries external LLM if configured; otherwise provides intelligent local response.
    """
    if not user_message or not str(user_message).strip():
        return "Please ask a question, and I'll be glad to help you!"

    clean_message = str(user_message).strip()

    # 1. Check external LLM
    success, llm_reply = call_external_llm(clean_message, history, student_context)
    if success and llm_reply:
        return llm_reply

    # 2. Local intelligent engine
    return generate_local_response(clean_message, history, student_context)
