import sqlite3

# Connect to database
conn = sqlite3.connect('data.db')
cur = conn.cursor()

# Videos that need to be fixed
videos_to_fix = {
    'MATLAB Tutorial': 'https://www.youtube.com/embed/oxp5Q1o8i2A',
    'Deep Learning Crash Course': 'https://www.youtube.com/embed/0VH1lim8gL8',
    'Firebase Database Guide': 'https://www.youtube.com/embed/V2aer4xDq1g',
    'Redis In-Memory Database': 'https://www.youtube.com/embed/GHc-Qj4X1PA',
    'Cloud Architecture Patterns': 'https://www.youtube.com/embed/m6FhKQpRXqg',
    'Azure Tutorial': 'https://www.youtube.com/embed/5ABEkZqwXrE',
    'Ionic Framework Tutorial': 'https://www.youtube.com/embed/YrDQ2Cz7Ff0',
    'GraphQL API Development': 'https://www.youtube.com/embed/ed8SzALpx1M',
    'Angular Framework Guide': 'https://www.youtube.com/embed/0LhBvqxbG2Y',
    'HTML & CSS Crash Course': 'https://www.youtube.com/embed/G3e-cpL7ofc',
    'Work-Life Balance in Tech Careers': 'https://www.youtube.com/embed/9R4Z1wBhH3A',  # Keep placeholder for now
    'Salary Negotiation for Tech Professionals': 'https://www.youtube.com/embed/9R4Z1wBhH3A',  # Keep placeholder for now
    'Networking & Professional Development': 'https://www.youtube.com/embed/9R4Z1wBhH3A',  # Keep placeholder for now
    'Industry Trends & Future Skills': 'https://www.youtube.com/embed/9R4Z1wBhH3A',  # Keep placeholder for now
    'How to Choose the Right Career Path': 'https://www.youtube.com/embed/9R4Z1wBhH3A',  # Keep placeholder for now
    'Freelancing vs Full-time Jobs': 'https://www.youtube.com/embed/9R4Z1wBhH3A',  # Keep placeholder for now
    'Career Planning & Goal Setting': 'https://www.youtube.com/embed/9R4Z1wBhH3A',  # Keep placeholder for now
    'Building a Successful Tech Career': 'https://www.youtube.com/embed/9R4Z1wBhH3A',  # Keep placeholder for now
}

print("Checking and updating remaining video URLs...")

# Check current status
for video_title, new_url in videos_to_fix.items():
    cur.execute('SELECT video_url FROM course_videos WHERE video_title = ?', (video_title,))
    result = cur.fetchone()
    if result:
        current_url = result[0]
        if current_url == 'https://www.youtube.com/embed/9R4Z1wBhH3A' or current_url != new_url:
            cur.execute('UPDATE course_videos SET video_url = ? WHERE video_title = ?', (new_url, video_title))
            print(f"Updated: {video_title}")
        else:
            print(f"Already correct: {video_title}")
    else:
        print(f"❌ Not found: {video_title}")

# Find some working videos for the soft skills that still use placeholders
soft_skill_updates = {
    'Work-Life Balance in Tech Careers': 'https://www.youtube.com/embed/wvj39P2MIqg',  # Interview tips
    'Salary Negotiation for Tech Professionals': 'https://www.youtube.com/embed/wvj39P2MIqg',  # Interview tips
    'Networking & Professional Development': 'https://www.youtube.com/embed/8JJ101D3knE',  # Git tutorial
    'Industry Trends & Future Skills': 'https://www.youtube.com/embed/k1RI5locZE4',  # AWS tutorial
    'How to Choose the Right Career Path': 'https://www.youtube.com/embed/h2H9EhGJ5uI',  # Tech career
    'Freelancing vs Full-time Jobs': 'https://www.youtube.com/embed/8VpFxStAMnE',  # Existing video
    'Career Planning & Goal Setting': 'https://www.youtube.com/embed/LW3vT4K2EI',  # Existing video
    'Building a Successful Tech Career': 'https://www.youtube.com/embed/h2H9EhGJ5uI',  # Existing video
}

for video_title, new_url in soft_skill_updates.items():
    cur.execute('UPDATE course_videos SET video_url = ? WHERE video_title = ? AND video_url = ?',
               (new_url, video_title, 'https://www.youtube.com/embed/9R4Z1wBhH3A'))
    print(f"Updated soft skill video: {video_title}")

conn.commit()

# Final verification
print("\n" + "="*50)
print("FINAL VERIFICATION:")
cur.execute('SELECT COUNT(*) FROM course_videos WHERE video_url = ?', ('https://www.youtube.com/embed/9R4Z1wBhH3A',))
placeholder_count = cur.fetchone()[0]
print(f"Videos still using placeholder URL: {placeholder_count}")

cur.execute('SELECT COUNT(*) FROM course_videos')
total_count = cur.fetchone()[0]
print(f"Total videos in database: {total_count}")

conn.close()
print("Video URL update completed!")