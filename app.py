import streamlit as st
import pymysql
from pymysql.cursors import DictCursor
import json
import os
import re
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from dotenv import load_dotenv
from collections import Counter
import io

# Load environment variables
load_dotenv()

# MySQL setup
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'your_password'),
    'database': os.getenv('DB_NAME', 'online_learning_platform')
}

def get_db_connection():
    try:
        return pymysql.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            cursorclass=DictCursor
        )
    except pymysql.Error as e:
        st.error("Unable to connect to the database. Please try again later.")
        return None

def validate_email(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search("[a-z]", password):
        return False, "Password needs a lowercase letter"
    if not re.search("[A-Z]", password):
        return False, "Password needs an uppercase letter"
    if not re.search("[0-9]", password):
        return False, "Password needs a digit"
    return True, ""

def create_user(name, email, password, role):
    if not name.strip():
        return False, "Name cannot be empty"
    if not validate_email(email):
        return False, "Invalid email format"
    if role not in ['student', 'teacher']:
        return False, "Invalid role"
    valid_pass, msg = validate_password(password)
    if not valid_pass:
        return False, msg

    hashed_password = generate_password_hash(password)
    conn = get_db_connection()
    if not conn:
        return False, "Database connection error"

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return False, "Email already exists"
        
        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)", 
            (name, email, hashed_password, role)
        )
        user_id = cursor.lastrowid
        conn.commit()
        
        if role == "student":
            cursor.execute(
                "INSERT INTO students (user_id, performance, engagement, challenges, support_needs, level, learning_style) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user_id, '{}', '{}', '[]', '[]', 'Not Assessed', '')
            )
        conn.commit()
        return True, "Registration successful! 🎉"
    except pymysql.Error as err:
        print(f"Error: {err}")
        return False, "Registration failed"
    finally:
        cursor.close()
        conn.close()

def authenticate_user(email, password):
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user and check_password_hash(user['password'], password):
            return user
        return None
    finally:
        cursor.close()
        conn.close()

def get_student_profile(email):
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT s.id, s.user_id, s.performance, s.engagement, s.challenges, 
                   s.support_needs, s.level, s.learning_style, s.personalized_insights, 
                   s.quiz_completed, u.name, u.email,
                   (SELECT COUNT(*) FROM student_activities WHERE student_id = s.user_id AND activity_type = 'video') as videos_watched,
                   (SELECT COUNT(*) FROM student_activities WHERE student_id = s.user_id AND activity_type = 'quiz') as quizzes_completed,
                   (SELECT COUNT(*) FROM student_activities WHERE student_id = s.user_id AND activity_type = 'discussion') as discussion_posts,
                   (SELECT COUNT(*) FROM student_activities WHERE student_id = s.user_id AND activity_type = 'assignment') as assignments_submitted,
                   (SELECT COUNT(DISTINCT DATE(activity_date)) FROM student_activities WHERE student_id = s.user_id AND MONTH(activity_date) = MONTH(CURRENT_DATE())) as login_days
            FROM students s
            JOIN users u ON s.user_id = u.id
            WHERE u.email = %s
        """, (email,))
        return cursor.fetchone()
    except pymysql.Error as err:
        print(f"Database error: {err}")
        st.error(f"Database error: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def record_student_activity(student_id, activity_type, duration_minutes=0):
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO student_activities 
            (student_id, activity_type, activity_date, duration_minutes)
            VALUES (%s, %s, NOW(), %s)
        """, (student_id, activity_type, duration_minutes))
        conn.commit()
        return True
    except pymysql.Error as err:
        print(f"Error recording activity: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

def update_student_performance(student_id, performance_data):
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE students 
            SET performance = %s
            WHERE user_id = %s
        """, (json.dumps(performance_data), student_id))
        conn.commit()
        return True
    except pymysql.Error as err:
        print(f"Error updating performance: {err}")
        return False
    finally:
        cursor.close()
        conn.close()



def update_student_level(student_id, level):
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE students SET level = %s WHERE id = %s",
            (level, student_id)
        )
        conn.commit()
        return True
    except pymysql.Error as err:
        print(f"Error: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

def update_student_learning_style(student_id, learning_style):
    conn = get_db_connection()
    if not conn:
        st.error("Database connection failed. Please try again later.")
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE students SET learning_style = %s WHERE user_id = %s",
            (learning_style, student_id)
        )
        if cursor.rowcount == 0:
            st.warning(f"No student found with user_id {student_id}. Learning style not updated.")
            return False
        conn.commit()
        return True
    except pymysql.Error as err:
        st.error(f"Database error while updating learning style: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_teacher_courses(teacher_id, conn=None):
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM courses WHERE teacher_id = %s", (teacher_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        if close_conn:
            conn.close()

def get_available_courses():
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.*, u.name as teacher_name 
            FROM courses c
            JOIN users u ON c.teacher_id = u.id
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def upload_course(title, description, teacher_id, files):
    if not title.strip() or not description.strip():
        return False, "Title and description cannot be empty"
    allowed_extensions = ['pdf', 'docx', 'mp4']
    max_size = 10 * 1024 * 1024  # 10MB
    conn = get_db_connection()
    if not conn:
        return False, "Database connection error"
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO courses (title, description, teacher_id) VALUES (%s, %s, %s)", 
            (title, description, teacher_id)
        )
        conn.commit()
        course_id = cursor.lastrowid
        
        os.makedirs('./Uploads', exist_ok=True)
        for file in files:
            ext = file.name.split('.')[-1].lower()
            if ext not in allowed_extensions:
                return False, "Invalid file type"
            if file.size > max_size:
                return False, "File too large"
            file_path = f"./Uploads/{file.name}"
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            cursor.execute(
                "INSERT INTO course_files (course_id, file_path) VALUES (%s, %s)", 
                (course_id, file_path)
            )
        conn.commit()
        return True, "Course uploaded successfully! 📚"
    except pymysql.Error as err:
        print(f"Error: {err}")
        return False, "Failed to upload course"
    finally:
        cursor.close()
        conn.close()

def update_course(course_id, teacher_id, title, description, new_files):
    if not title.strip() or not description.strip():
        return False, "Title and description cannot be empty"
    allowed_extensions = ['pdf', 'docx', 'mp4']
    max_size = 10 * 1024 * 1024  # 10MB
    conn = get_db_connection()
    if not conn:
        return False, "Database connection error"
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM courses WHERE id = %s AND teacher_id = %s", (course_id, teacher_id))
        if not cursor.fetchone():
            return False, "Course not found or unauthorized"
        cursor.execute(
            "UPDATE courses SET title = %s, description = %s WHERE id = %s",
            (title, description, course_id)
        )
        if new_files:
            os.makedirs('./Uploads', exist_ok=True)
            for file in new_files:
                ext = file.name.split('.')[-1].lower()
                if ext not in allowed_extensions:
                    return False, "Invalid file type"
                if file.size > max_size:
                    return False, "File too large"
                file_path = f"./Uploads/{file.name}"
                with open(file_path, "wb") as f:
                    f.write(file.getbuffer())
                cursor.execute(
                    "INSERT INTO course_files (course_id, file_path) VALUES (%s, %s)",
                    (course_id, file_path)
                )
        conn.commit()
        return True, "Course updated successfully! 📚"
    except pymysql.Error as err:
        print(f"Error: {err}")
        return False, "Failed to update course"
    finally:
        cursor.close()
        conn.close()

def delete_course(course_id, teacher_id):
    conn = get_db_connection()
    if not conn:
        return False, "Database connection error"
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM courses WHERE id = %s AND teacher_id = %s", (course_id, teacher_id))
        if not cursor.fetchone():
            return False, "Course not found or unauthorized"
        cursor.execute("SELECT file_path FROM course_files WHERE course_id = %s", (course_id,))
        files = cursor.fetchall()
        cursor.execute("DELETE FROM courses WHERE id = %s", (course_id,))
        conn.commit()
        for file in files:
            try:
                os.remove(file['file_path'])
            except FileNotFoundError:
                print(f"File {file['file_path']} not found")
        return True, "Course deleted successfully! 🗑️"
    except pymysql.Error as err:
        print(f"Error: {err}")
        return False, "Failed to delete course"
    finally:
        cursor.close()
        conn.close()

def check_first_enrollment(student_id):
    """Check if this is the student's first-ever course enrollment"""
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) as count FROM enrollments WHERE student_id = %s",
            (student_id,)
        )
        result = cursor.fetchone()
        return result['count'] == 0
    finally:
        cursor.close()
        conn.close()

def enroll_in_course(student_id, student_name, course_id):
    """Enroll a student in a course with proper error handling"""
    conn = get_db_connection()
    if not conn:
        return False, "Database connection error"
    
    cursor = conn.cursor()
    try:
        # Check if this would be the first enrollment
        cursor.execute(
            "SELECT COUNT(*) as count FROM enrollments WHERE student_id = %s",
            (student_id,)
        )
        result = cursor.fetchone()
        is_first_enrollment = result['count'] == 0
        
        # Check if already enrolled in this specific course
        cursor.execute(
            "SELECT id FROM enrollments WHERE student_id = %s AND course_id = %s",
            (student_id, course_id)
        )
        existing = cursor.fetchone()
        
        if existing:
            return False, "You're already enrolled in this course"
        
        # If not enrolled, insert new enrollment
        cursor.execute(
            "INSERT INTO enrollments (student_id, student_name, course_id) VALUES (%s, %s, %s)",
            (student_id, student_name, course_id)
        )
        conn.commit()
        
        if is_first_enrollment:
            return True, "Congratulations on your first course enrollment! 🎉"
        else:
            return True, "Enrolled successfully! 🚀"
            
    except pymysql.Error as err:
        conn.rollback()
        error_code = err.args[0]
        if error_code == 1062:  # MySQL duplicate entry error code
            return False, "You're already enrolled in this course"
        else:
            print(f"Database error: {err}")
            return False, f"An error occurred during enrollment: {err}"
    finally:
        cursor.close()
        conn.close()

def get_student_courses(student_id):
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.*, u.name as teacher_name 
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            JOIN users u ON c.teacher_id = u.id
            WHERE e.student_id = %s
        """, (student_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def import_student_data(student_data, teacher_id):
    conn = get_db_connection()
    if not conn:
        return False, "Database connection error"
    cursor = conn.cursor()
    try:
        student_json = json.load(student_data)
        expected_keys = ["email", "performance", "engagement", "challenges", "support_needs", "personalized_insights", "level", "learning_style"]
        for student in student_json:
            # Validate required fields
            if not all(key in student for key in ["email"]):
                return False, f"Missing required field 'email' for student data"
            if not validate_email(student["email"]):
                return False, f"Invalid email format for {student['email']}"
            
            # Validate performance
            performance = student.get("performance", {})
            if not isinstance(performance, dict):
                return False, f"Invalid performance data for {student['email']}"
            if "overall_score" in performance and not isinstance(performance["overall_score"], (int, float)):
                return False, f"Invalid overall_score for {student['email']}"
            if "progress" in performance and not isinstance(performance["progress"], (int, float)):
                return False, f"Invalid progress for {student['email']}"
            if "skills" in performance and not isinstance(performance["skills"], dict):
                return False, f"Invalid skills data for {student['email']}"
            
            # Validate engagement
            engagement = student.get("engagement", {})
            if not isinstance(engagement, dict):
                return False, f"Invalid engagement data for {student['email']}"
            engagement_fields = ["videos_watched", "quizzes_completed", "discussion_posts", "assignments_submitted", "login_days"]
            for field in engagement_fields:
                if field in engagement and not isinstance(engagement[field], (int, float)):
                    return False, f"Invalid {field} in engagement data for {student['email']}"
            
            # Validate challenges and support_needs
            challenges = student.get("challenges", [])
            if not isinstance(challenges, list):
                return False, f"Invalid challenges data for {student['email']}"
            support_needs = student.get("support_needs", [])
            if not isinstance(support_needs, list):
                return False, f"Invalid support_needs data for {student['email']}"
            
            # Validate level and learning_style
            level = student.get("level", "Not Assessed")
            if not isinstance(level, str):
                return False, f"Invalid level for {student['email']}"
            learning_style = student.get("learning_style", "")
            if not isinstance(learning_style, str):
                return False, f"Invalid learning_style for {student['email']}"
            
            # Check if student is enrolled in teacher's courses
            cursor.execute("""
                SELECT e.student_id
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                JOIN students s ON e.student_id = s.user_id
                JOIN users u ON s.user_id = u.id
                WHERE c.teacher_id = %s AND u.email = %s
            """, (teacher_id, student["email"]))
            if not cursor.fetchone():
                return False, f"Student {student['email']} is not enrolled in your courses"
            
            # Insert or update student data
            cursor.execute("""
                INSERT INTO students (user_id, performance, engagement, challenges, support_needs, personalized_insights, level, learning_style)
                VALUES ((SELECT id FROM users WHERE email = %s), %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                performance=VALUES(performance),
                engagement=VALUES(engagement),
                challenges=VALUES(challenges),
                support_needs=VALUES(support_needs),
                personalized_insights=VALUES(personalized_insights),
                level=VALUES(level),
                learning_style=VALUES(learning_style)
            """, (
                student["email"],
                json.dumps(performance),
                json.dumps(engagement),
                json.dumps(challenges),
                json.dumps(support_needs),
                student.get("personalized_insights", ""),
                level,
                learning_style
            ))
        conn.commit()
        return True, "Student data imported successfully! 📊"
    except json.JSONDecodeError:
        return False, "Invalid JSON format"
    except pymysql.Error as err:
        print(f"Error: {err}")
        return False, f"Database error: {err}"
    finally:
        cursor.close()
        conn.close()

def get_students(teacher_id):
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT DISTINCT s.*, u.name, u.email
            FROM students s
            JOIN users u ON s.user_id = u.id
            JOIN enrollments e ON s.user_id = e.student_id
            JOIN courses c ON e.course_id = c.id
            WHERE c.teacher_id = %s
        """, (teacher_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_student_progress_history(student_id):
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT DATE_FORMAT(activity_date, '%%b') as month, 
                   AVG(CASE 
                       WHEN activity_type = 'quiz' THEN duration_minutes * 2 
                       WHEN activity_type = 'assignment' THEN duration_minutes * 1.5
                       ELSE duration_minutes 
                   END) as score
            FROM student_activities
            WHERE student_id = %s
            GROUP BY DATE_FORMAT(activity_date, '%%b'), MONTH(activity_date)
            ORDER BY MONTH(activity_date)
        """, (student_id,))
        progress_data = cursor.fetchall()
        
        if not progress_data:
            # If no data exists, return empty rather than random data
            return []
            
        return progress_data
    finally:
        cursor.close()
        conn.close()

def get_course_files(course_id, conn=None):
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM course_files WHERE course_id = %s", (course_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        if close_conn:
            conn.close()

def get_student_engagement_metrics(student_id):
    conn = get_db_connection()
    if not conn:
        return {}
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM student_activities WHERE student_id = %s AND activity_type = 'video') as videos_watched,
                (SELECT COUNT(*) FROM student_activities WHERE student_id = %s AND activity_type = 'quiz') as quizzes_completed,
                (SELECT COUNT(*) FROM student_activities WHERE student_id = %s AND activity_type = 'discussion') as discussion_posts,
                (SELECT COUNT(*) FROM student_activities WHERE student_id = %s AND activity_type = 'assignment') as assignments_submitted,
                (SELECT COUNT(DISTINCT DATE(activity_date)) FROM student_activities WHERE student_id = %s AND MONTH(activity_date) = MONTH(CURRENT_DATE())) as login_days
        """, (student_id, student_id, student_id, student_id, student_id))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def get_class_performance_comparison(teacher_id):
    conn = get_db_connection()
    if not conn:
        return [], []
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT u.name, 
                   COALESCE(AVG(qr.score), 0) as avg_score
            FROM students s
            JOIN users u ON s.user_id = u.id
            JOIN enrollments e ON s.user_id = e.student_id
            JOIN courses c ON e.course_id = c.id
            LEFT JOIN quiz_results qr ON s.user_id = qr.student_id
            WHERE c.teacher_id = %s
            GROUP BY u.id, u.name
        """, (teacher_id,))
        results = cursor.fetchall()
        
        names = [row['name'] for row in results]
        scores = [row['avg_score'] for row in results]
        
        return names, scores
    finally:
        cursor.close()
        conn.close()

def get_student_skill_assessment(student_id):
    conn = get_db_connection()
    if not conn:
        return {}, []
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT skill_name, skill_score 
            FROM student_skills
            WHERE student_id = %s
        """, (student_id,))
        skills = {row['skill_name']: row['skill_score'] for row in cursor.fetchall()}
        
        if not skills:
            # Return empty if no skills exist
            return {}, []
            
        return skills, list(skills.keys())
    finally:
        cursor.close()
        conn.close()



def get_student_learning_patterns(student_id):
    conn = get_db_connection()
    if not conn:
        return [], []
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN HOUR(activity_date) BETWEEN 6 AND 8 THEN '6-9 AM'
                    WHEN HOUR(activity_date) BETWEEN 9 AND 11 THEN '9-12 PM'
                    WHEN HOUR(activity_date) BETWEEN 12 AND 14 THEN '12-3 PM'
                    WHEN HOUR(activity_date) BETWEEN 15 AND 17 THEN '3-6 PM'
                    WHEN HOUR(activity_date) BETWEEN 18 AND 20 THEN '6-9 PM'
                    ELSE '9-12 AM'
                END as time_period,
                COUNT(*) as activity_count
            FROM student_activities
            WHERE student_id = %s
            GROUP BY time_period
            ORDER BY FIELD(time_period, '6-9 AM', '9-12 PM', '12-3 PM', '3-6 PM', '6-9 PM', '9-12 AM')
        """, (student_id,))
        results = cursor.fetchall()
        
        time_periods = ['6-9 AM', '9-12 PM', '12-3 PM', '3-6 PM', '6-9 PM', '9-12 AM']
        activities = [0] * len(time_periods)
        
        for row in results:
            if row['time_period'] in time_periods:
                index = time_periods.index(row['time_period'])
                activities[index] = row['activity_count']
                
        return time_periods, activities
    finally:
        cursor.close()
        conn.close()
        
        
def record_student_activity(student_id, activity_type, duration_minutes=0):
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO student_activities 
            (student_id, activity_type, activity_date, duration_minutes)
            VALUES (%s, %s, NOW(), %s)
        """, (student_id, activity_type, duration_minutes))
        conn.commit()
        return True
    except pymysql.Error as err:
        print(f"Error recording activity: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

def update_student_performance(student_id, performance_data):
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE students 
            SET performance = %s
            WHERE user_id = %s
        """, (json.dumps(performance_data), student_id))
        conn.commit()
        return True
    except pymysql.Error as err:
        print(f"Error updating performance: {err}")
        return False
    finally:
        cursor.close()
        conn.close()
        
                

def has_taken_quiz(student_id):
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as count FROM quiz_results WHERE student_id = %s", (student_id,))
        result = cursor.fetchone()
        return result['count'] > 0
    finally:
        cursor.close()
        conn.close()

def generate_quiz():
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM quizzes ORDER BY RAND() LIMIT 6")
        questions = cursor.fetchall()
        return [
            {
                "question": q['question'],
                "options": json.loads(q['options']),
                "correct": q['correct_option'],
                "difficulty": q['difficulty']
            }
            for q in questions
        ]
    finally:
        cursor.close()
        conn.close()

def conduct_quiz(student_id):
    if 'quiz_answers' not in st.session_state:
        st.session_state.quiz_answers = {}
        st.session_state.quiz_completed = False
        st.session_state.quiz_score = 0

    st.subheader("Placement Quiz 📝")
    st.write("Please answer the following questions to assess your level.")

    questions = generate_quiz()
    if not questions:
        st.error("No quiz questions available.")
        return None

    for i, q in enumerate(questions):
        st.markdown(f"**Question {i+1}: {q['question']}**")
        answer = st.radio(
            "Select an answer:",
            options=q['options'],
            key=f"quiz_question_{i}"
        )
        st.session_state.quiz_answers[i] = q['options'].index(answer) if answer in q['options'] else -1

    if st.button("Submit Quiz 🚀"):
        score = 0
        for i, q in enumerate(questions):
            if st.session_state.quiz_answers.get(i, -1) == q['correct']:
                if q['difficulty'] == "Beginner":
                    score += 10
                elif q['difficulty'] == "Intermediate":
                    score += 15
                else:  # Advanced
                    score += 25
        
        st.session_state.quiz_score = score
        st.session_state.quiz_completed = True
        
        level = "Advanced" if score >= 80 else "Intermediate" if score >= 50 else "Beginner"
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO quiz_results (student_id, score, level) VALUES (%s, %s, %s)",
                    (student_id, score, level)
                )
                cursor.execute(
                    "UPDATE students SET level = %s, quiz_completed = TRUE WHERE user_id = %s",
                    (level, student_id)
                )
                conn.commit()
                st.success(f"Quiz completed! Your level: {level} 🎉")
            except pymysql.Error as err:
                print(f"Error: {err}")
                st.error("Failed to save quiz results 😔")
            finally:
                cursor.close()
                conn.close()
        return level
    return None

def conduct_learning_style_quiz(student_id):
    if 'learning_style_answers' not in st.session_state:
        st.session_state.learning_style_answers = {}
        st.session_state.learning_style_completed = False

    st.subheader("Learning Style Assessment 🧠")
    st.write("Answer the following questions to discover your preferred learning style. Select the option that best describes your preference.")

    questions = [
        {
            "question": "When learning something new, I prefer to:",
            "options": [
                "Watch videos or look at diagrams (Visual)",
                "Listen to explanations or discussions (Auditory)",
                "Read texts or take notes (Reading/Writing)",
                "Engage in hands-on activities (Kinesthetic)",
                "Work in a group (Social)",
                "Study alone (Solitary)",
                "Analyze patterns and logic (Analytical)"
            ],
            "styles": ["Visual", "Auditory", "Reading/Writing", "Kinesthetic", "Social", "Solitary", "Analytical"]
        },
        {
            "question": "I understand best when I can:",
            "options": [
                "See charts or visual aids (Visual)",
                "Hear someone explain it (Auditory)",
                "Write summaries or read instructions (Reading/Writing)",
                "Practice or move around (Kinesthetic)",
                "Discuss with others (Social)",
                "Work independently (Solitary)",
                "Break it down logically (Analytical)"
            ],
            "styles": ["Visual", "Auditory", "Reading/Writing", "Kinesthetic", "Social", "Solitary", "Analytical"]
        },
        {
            "question": "I remember information better if I:",
            "options": [
                "Create mental images or sketches (Visual)",
                "Repeat it aloud or hear it (Auditory)",
                "Write it down or read it (Reading/Writing)",
                "Use physical objects or move (Kinesthetic)",
                "Learn with friends or peers (Social)",
                "Study in a quiet space (Solitary)",
                "Connect it to concepts or theories (Analytical)"
            ],
            "styles": ["Visual", "Auditory", "Reading/Writing", "Kinesthetic", "Social", "Solitary", "Analytical"]
        }
    ]

    for i, q in enumerate(questions):
        st.markdown(f"**Question {i+1}: {q['question']}**")
        answer = st.radio(
            "Select an answer:",
            options=q['options'],
            key=f"learning_style_question_{i}"
        )
        if answer:
            selected_style = q['styles'][q['options'].index(answer)]
            st.session_state.learning_style_answers[i] = selected_style

    if st.button("Submit Learning Style Quiz 🚀"):
        if len(st.session_state.learning_style_answers) == len(questions):
            style_counts = Counter(st.session_state.learning_style_answers.values())
            dominant_style = style_counts.most_common(1)[0][0]
            st.session_state.learning_style_completed = True
            
            success = update_student_learning_style(student_id, dominant_style)
            if success:
                st.success(f"Your learning style is: {dominant_style}! 🎉 Recommendations have been added to your dashboard.")
                st.rerun()
            else:
                st.error("Failed to save learning style. Please try again or contact support. 😔")
        else:
            st.warning("Please answer all questions before submitting.")


def student_dashboard():
    student_profile = get_student_profile(st.session_state.user['email'])
    if not student_profile:
        st.warning("Student profile not found. Please contact support. 📞")
        return

    st.markdown("<div class='dashboard'>", unsafe_allow_html=True)
    st.title("Student Dashboard 🎓")
    
    # Profile and Performance Section
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='section-container'>", unsafe_allow_html=True)
        st.subheader("Your Profile 🌟")
    
        learning_style = student_profile['learning_style'] if student_profile['learning_style'] else 'Not Assessed'
        st.markdown(f"""
    <div class="profile-section">
        <div><strong>Name:</strong> {student_profile['name']}</div>
        <div><strong>Email:</strong> {student_profile['email']}</div>
        <div><strong>Level:</strong> {student_profile['level'] or 'Not Assessed'}</div>
        <div><strong>Learning Style:</strong> {learning_style}</div>
    </div>
    """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("<div class='section-container'>", unsafe_allow_html=True)
        st.subheader("Performance Insights 📊")
        
        # Display performance metrics
        performance_str = student_profile.get('performance') or '{}'
        try:
            performance = json.loads(performance_str)
            score = performance.get('overall_score', 0)
            progress = performance.get('progress', 0)
            score_color = '#4CAF50' if score >= 80 else '#FF9800' if score >= 70 else '#F44336'
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Overall Score</div>
                <div class="metric-value" style="color:{score_color}">{score}%</div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width:{score}%"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Course Progress</div>
                <div class="metric-value" style="color:#3b82f6">{progress}%</div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width:{progress}%"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        except json.JSONDecodeError:
            st.warning("Invalid performance data format ⚠️")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Learning Journey Chart
    st.markdown("<div class='section-container chart-container'>", unsafe_allow_html=True)
    st.subheader("Your Learning Journey 📈")
    progress_data = get_student_progress_history(student_profile['id'])
    if progress_data:
        df = pd.DataFrame(progress_data)
        fig = px.line(
            df, x='month', y='score', 
            markers=True, 
            line_shape='spline',
            title='Performance Trend',
            labels={'month': 'Month', 'score': 'Score'},
            color_discrete_sequence=['#3b82f6']
        )
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#1e293b',
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No progress data available yet. Your learning journey will appear here as you engage with courses.")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Personalized Recommendations
    if student_profile['personalized_insights']:
        st.markdown("<div class='section-container insights-container'>", unsafe_allow_html=True)
        st.subheader("Personalized Recommendations 💡")
        st.markdown(student_profile['personalized_insights'], unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Learning Style Recommendations
    if student_profile.get('learning_style', ''):
        st.markdown("<div class='section-container insights-container'>", unsafe_allow_html=True)
        st.subheader("Learning Style Recommendations 🧠")
        recommendations = {
            "Visual": "Use diagrams, charts, and videos to visualize concepts. Try mind maps to organize information.",
            "Auditory": "Listen to podcasts or recorded lectures. Discuss topics aloud or join study groups to reinforce learning.",
            "Reading/Writing": "Take detailed notes and summarize key points. Read textbooks and write practice questions to solidify understanding.",
            "Kinesthetic": "Engage in hands-on activities like experiments or role-playing. Use physical objects to represent ideas.",
            "Social": "Join study groups or discussion forums. Collaborate with peers to share and learn new perspectives.",
            "Solitary": "Study in a quiet, distraction-free environment. Set personal goals and use self-reflection to track progress.",
            "Analytical": "Break down complex problems into smaller parts. Use logical reasoning and connect concepts to deeper theories."
        }
        st.markdown(f"""
        <div>
            <strong>Your Learning Style:</strong> {student_profile['learning_style']}<br>
            <strong>Recommendations:</strong> {recommendations.get(student_profile['learning_style'], 'Complete the learning style quiz to get tailored recommendations.')}
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Areas for Improvement
    challenges_str = student_profile.get('challenges') or '[]'
    try:
        challenges = json.loads(challenges_str)
        if challenges:
            st.markdown("<div class='section-container chart-container'>", unsafe_allow_html=True)
            st.subheader("Areas for Improvement 🔍")
            challenge_data = [{'Challenge': c, 'Priority': i} for i, c in enumerate(challenges, 1)]
            df = pd.DataFrame(challenge_data)
            fig = px.bar(
                df, 
                x='Challenge', 
                y='Priority',
                color='Priority',
                color_continuous_scale=['#3b82f6', '#60a5fa'],
                labels={'Priority': 'Importance'},
                title='Focus Areas'
            )
            fig.update_layout(
                xaxis_title=None,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='#1e293b',
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
    except json.JSONDecodeError:
        st.warning("Invalid challenges data format ⚠️")
    
    # Recommended Support
    support_needs_str = student_profile.get('support_needs') or '[]'
    try:
        support_needs = json.loads(support_needs_str)
        if support_needs:
            st.markdown("<div class='section-container'>", unsafe_allow_html=True)
            st.subheader("Recommended Support 🤝")
            for need in support_needs:
                st.markdown(f"""
                <div class="metric-card" style="text-align:left;">
                    ✓ {need}
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
    except json.JSONDecodeError:
        st.warning("Invalid support needs data format ⚠️")
    
    # Skills Assessment
    st.markdown("<div class='section-container chart-container'>", unsafe_allow_html=True)
    st.subheader("Your Skills Assessment 🌟")
    skills, categories = get_student_skill_assessment(student_profile['id'])
    if skills:
        fig = go.Figure()
        values = list(skills.values())
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            name='Skills',
            line_color='#3b82f6',
            fillcolor='rgba(59, 130, 246, 0.5)',
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )
            ),
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#1e293b',
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Complete some assessments to see your skills radar chart.")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Engagement Metrics
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader("Your Engagement Metrics 📊")
    engagement_data = get_student_engagement_metrics(student_profile['id'])
    if engagement_data:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Videos Watched 🎥</div>
                <div class="metric-value">{engagement_data['videos_watched']}</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Quizzes Completed ✅</div>
                <div class="metric-value">{engagement_data['quizzes_completed']}</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Discussion Posts 💬</div>
                <div class="metric-value">{engagement_data['discussion_posts']}</div>
            </div>
            """, unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Assignments Submitted 📝</div>
                <div class="metric-value">{engagement_data['assignments_submitted']}</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Active Days This Month 📅</div>
                <div class="metric-value">{engagement_data['login_days']}/30</div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width:{(engagement_data['login_days']/30)*100}%"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Your engagement metrics will appear here as you start using the platform.")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Learning Patterns
    st.markdown("<div class='section-container chart-container'>", unsafe_allow_html=True)
    st.subheader("Your Learning Patterns ⏰")
    time_periods, activities = get_student_learning_patterns(student_profile['id'])
    if activities and any(activities):
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=time_periods,
            y=activities,
            marker_color=['#3b82f6' if i < len(activities)/2 else '#60a5fa' for i in range(len(activities))],
            text=activities,
            textposition='auto',
        ))
        fig.update_layout(
            title='Activity by Time of Day',
            xaxis_title='Time Period',
            yaxis_title='Activity Level',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#1e293b',
            height=350,
            bargap=0.2,
            template='plotly_white'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Your learning patterns will appear here as you engage with the platform throughout the day.")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Course Management
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader("Course Management 📚")
    student_options = st.selectbox("Options", ["My Courses", "Available Courses", "Resources"], key="student_course_options")

    if student_options == "My Courses":
        courses = get_student_courses(st.session_state.user['id'])
        if courses:
            for course in courses:
                st.markdown(f"""
                <div class="course-card">
                    <div class="course-title">{course['title']} - {course['teacher_name']}</div>
                    <div class="course-description">{course['description']}</div>
                """, unsafe_allow_html=True)
            
        else:
            st.info("You are not enrolled in any courses yet.")

    elif student_options == "Available Courses":
        # Handle available courses display here
        courses = get_available_courses()  # You'll need to implement this function
        if courses:
            for course in courses:
                st.markdown(f"""
                <div class="course-card">
                    <div class="course-title">{course['title']} - {course['teacher_name']}</div>
                    <div class="course-description">{course['description']}</div>
                """, unsafe_allow_html=True)
                
                with st.form(key=f"enroll_form_{course['id']}"):
                    submitted = st.form_submit_button(
                        label=f"Enroll in {course['title']} 🚀",
                        use_container_width=True,
                        type="primary"
                    )
                    
                    if submitted:
                        success, message = enroll_in_course(
                            st.session_state.user['id'],
                            st.session_state.user['name'],
                            course['id']
                        )
                        if success:
                            st.success(message)
                            if check_first_enrollment(st.session_state.user['id']):
                                st.session_state.quiz_completed = False
                                st.session_state.quiz_answers = {}
                                st.rerun()
                            else:
                                st.rerun()
                        else:
                            st.error(message)

                    st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No courses available at the moment 😔")
        
    elif student_options == "Resources":
        st.markdown("<div class='insights-container'>", unsafe_allow_html=True)
        st.subheader("Learning Resources 📚")
        st.write("The resources page is currently under development. Check back soon for access to study guides, tutorials, and more! 🚧")
        st.markdown("</div>", unsafe_allow_html=True)
        
    st.markdown("</div>", unsafe_allow_html=True)
        


# Custom CSS with Enhanced Light Blue Gradient Palette
custom_css = """
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: #f8fafc; /* Softer off-white background */
    color: #1e293b; /* Dark slate for text */
    line-height: 1.6;
}

/* General container for dashboards */
.dashboard {
    max-width: 1280px;
    margin: 0 auto;
    padding: 24px;
}

/* Section containers */
.section-container {
    background-color: #e0f2fe; /* Softer light blue background */
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.section-container:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
}

/* Metric card styling */
.metric-card {
    background-color: #f1f5f9; /* Very light gray-blue */
    padding: 20px;
    border-radius: 12px;
    text-align: center;
    margin-bottom: 16px;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.06);
    transition: transform 0.2s ease;
}
.metric-card:hover {
    transform: translateY(-2px);
}
.metric-card .metric-label {
    font-size: 0.95em;
    color: #64748b; /* Slate gray for labels */
    margin-bottom: 10px;
    font-weight: 500;
}
.metric-card .metric-value {
    font-size: 1.6em;
    font-weight: 700;
    color: #1e293b; /* Dark slate for values */
}

/* Progress bar */
.progress-bar-container {
    background-color: #bfdbfe; /* Light blue for progress container */
    border-radius: 8px;
    height: 14px;
    margin-top: 12px;
    overflow: hidden;
}
.progress-bar {
    background: linear-gradient(90deg, #3b82f6, #60a5fa); /* Light blue gradient */
    height: 100%;
    border-radius: 8px;
    transition: width 0.6s ease;
}

/* Insights container */
.insights-container {
    background-color: #f1f5f9; /* Very light gray-blue */
    padding: 28px;
    border-radius: 16px;
    margin-bottom: 24px;
    line-height: 1.7;
}

/* Enhanced course card styling */
.course-card {
    background: linear-gradient(135deg, #e0f2fe, #f1f5f9); /* Subtle gradient */
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 24px;
    border-left: 6px solid #3b82f6; /* Stronger blue accent */
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
    transition: all 0.3s ease;
}
.course-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.12);
    background: linear-gradient(135deg, #bfdbfe, #e0f2fe); /* Slightly darker gradient on hover */
}
.course-card .course-title {
    font-size: 1.4em;
    font-weight: 700;
    color: #1e293b; /* Dark slate */
    margin-bottom: 14px;
    letter-spacing: 0.3px;
}
.course-card .course-description {
    font-size: 1.05em;
    color: #475569; /* Darker slate gray for contrast */
    line-height: 1.6;
    margin-bottom: 20px;
}

/* Enroll and action buttons */
.enroll-button, .stButton > button {
    background: linear-gradient(90deg, #3b82f6, #60a5fa); /* Blue gradient */
    color: #ffffff;
    border: none;
    padding: 12px 28px;
    border-radius: 12px;
    font-size: 1.1em;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    width: 100%;
    text-align: center;
}
/* Target specifically the enrollment button by class */
.enroll-button:hover {
    background: linear-gradient(90deg, #2563eb, #3b82f6); /* Darker blue gradient */
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
    transition: all 0.3s ease;
}

.enroll-button:active {
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* Delete button styling (blue-themed instead of red) */
button[style*="background: linear-gradient(90deg, #ef4444, #f87171)"] {
    background: linear-gradient(90deg, #2563eb, #3b82f6) !important; /* Darker blue gradient for delete */
    color: #ffffff !important;
    border: none !important;
    padding: 10px 20px !important;
    border-radius: 8px !important;
    font-size: 1em !important;
    font-weight: 500 !important;
    cursor: pointer !important;
    margin-top: 10px !important;
}
button[style*="background: linear-gradient(90deg, #ef4444, #f87171)"]:hover {
    background: linear-gradient(90deg, #1e40af, #2563eb) !important; /* Even darker blue on hover */
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15) !important;
}
button[style*="background: linear-gradient(90deg, #ef4444, #f87171)"]:active {
    transform: translateY(0) !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
}

/* Download button for course files */
.course-card .download-button {
    background: linear-gradient(90deg, #3b82f6, #60a5fa); /* Light blue gradient */
    color: #ffffff;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 0.95em;
    cursor: pointer;
    transition: all 0.3s ease;
}
.course-card .download-button:hover {
    background: linear-gradient(90deg, #2563eb, #3b82f6); /* Darker blue gradient */
    transform: translateY(-2px);
}

/* Selectbox styling */
.stSelectbox {
    background-color: #f1f5f9; /* Very light gray-blue */
    border-radius: 12px;
    padding: 8px;
}
.stSelectbox > div > select {
    background-color: transparent;
    color: #1e293b; /* Dark slate */
    border: none;
    font-size: 1em;
    padding: 8px;
}

/* Subheader styling */
h2, .stSubheader {
    color: #1e293b; /* Dark slate */
    font-weight: 600;
    font-size: 1.6em;
    margin-bottom: 16px;
    border-bottom: 3px solid #3b82f6; /* Light blue accent */
    padding-bottom: 10px;
}

/* Chart containers */
.chart-container {
    background-color: #e0f2fe; /* Light blue background */
    border: 1px solid #bfdbfe; /* Subtle border */
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 24px;
}

/* Profile section */
.profile-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
    background-color: #f1f5f9; /* Very light gray-blue */
    padding: 24px;
    border-radius: 16px;
    margin-bottom: 24px;
}
.profile-section div {
    font-size: 1.05em;
    color: #1e293b; /* Dark slate */
}
.profile-section div strong {
    color: #3b82f6; /* Light blue for emphasis */
}

/* Login page styles */
.container {
    max-width: 640px;
    margin: 40px auto;
    padding: 32px;
    background-color: #f1f5f9; /* Very light gray-blue */
    border-radius: 16px;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}
.login-title {
    text-align: center;
    color: #1e293b; /* Dark slate */
    font-size: 2.2em;
    margin-bottom: 12px;
    font-weight: 700;
}
.welcome-text {
    text-align: center;
    color: #64748b; /* Slate gray */
    font-size: 1.3em;
    margin-bottom: 24px;
}
.redirect-button {
    background: none;
    border: none;
    color: #3b82f6; /* Light blue */
    cursor: pointer;
    font-size: 1.05em;
    text-decoration: underline;
    padding: 0;
    margin-top: 12px;
    display: block;
    text-align: center;
}
.redirect-button:hover {
    color: #2563eb; /* Darker blue */
}

/* Responsive design */
@media (max-width: 768px) {
    .dashboard {
        padding: 16px;
    }
    .section-container {
        padding: 20px;
    }
    .metric-card {
        padding: 16px;
    }
    .metric-card .metric-value {
        font-size: 1.4em;
    }
    .course-card {
        padding: 20px;
    }
    .enroll-button, .stButton > button {
        padding: 10px 20px;
        font-size: 1em;
    }
    .login-title {
        font-size: 1.8em;
    }
    .welcome-text {
        font-size: 1.1em;
    }
    .container {
        padding: 24px;
        margin: 20px;
    }
}
"""
st.markdown(f"<style>{custom_css}</style>", unsafe_allow_html=True)

# Ensure uploads directory exists
os.makedirs('./Uploads', exist_ok=True)

# Session state management
if 'user' not in st.session_state:
    st.session_state.user = None
    st.session_state.last_activity = datetime.now()
    st.session_state.page = 'login'
    st.session_state.learning_style_answers = {}
    st.session_state.learning_style_completed = False

# Check session timeout
if st.session_state.user and datetime.now() - st.session_state.last_activity > timedelta(minutes=30):
    st.session_state.user = None
    st.session_state.page = 'login'
    st.session_state.learning_style_answers = {}
    st.session_state.learning_style_completed = False
    st.warning("Session timed out. Please login again. ⏳")
    st.rerun()

# Update last activity time
if st.session_state.user:
    st.session_state.last_activity = datetime.now()

# Login and Registration Page
if st.session_state.user is None:
    with st.container():
        st.markdown("""
        <div class="container">
            <div class="login-title">Welcome to our learning platform 🎓</div>
            <p class="welcome-text">Join our vibrant learning community today! 🚀</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.page == 'login':
            st.subheader("Login to Your Account 🔑")
            
            with st.form("login_form", clear_on_submit=True):
                login_email = st.text_input("Email 📧", placeholder="Enter your email", key="login_email")
                login_password = st.text_input("Password 🔒", type="password", placeholder="Enter your password", key="login_password")
                if st.form_submit_button("Login 🚪"):
                    user = authenticate_user(login_email, login_password)
                    if user:
                        st.session_state.user = user
                        st.success("Login successful! Welcome back! 😊")
                        st.rerun()
                    else:
                        st.error("Invalid credentials! Please try again. 😔")
            
            if st.button("Not a member? Register now", key="to_register", type="secondary", use_container_width=True):
                st.session_state.page = 'register'
                st.rerun()
        
        elif st.session_state.page == 'register':
            st.subheader("Create Your Account 📝")
            
            with st.form("register_form", clear_on_submit=True):
                register_name = st.text_input("Full Name 👤", placeholder="Enter your name", key="register_name")
                register_email = st.text_input("Email 📧", placeholder="Enter your email", key="register_email")
                register_password = st.text_input("Password 🔒", type="password", placeholder="Create a password", key="register_password")
                register_role = st.selectbox("Role 🎭", ["student", "teacher"], help="Are you a student or teacher?", key="register_role")
                if st.form_submit_button("Register Now 🚀"):
                    success, message = create_user(
                        register_name, 
                        register_email, 
                        register_password, 
                        register_role
                    )
                    if success:
                        st.success(message)
                        st.session_state.page = 'login'
                        st.rerun()
                    else:
                        st.error(message)
            
            if st.button("Already a member? Login now", key="to_login", type="secondary", use_container_width=True):
                st.session_state.page = 'login'
                st.rerun()
else:
    st.sidebar.title(f"Welcome, {st.session_state.user['name']} 👋")
    if st.sidebar.button("Logout 🚪"):
        st.session_state.user = None
        st.session_state.page = 'login'
        st.session_state.learning_style_answers = {}
        st.session_state.learning_style_completed = False
        st.success("Logged out successfully! See you soon! 👋")
        st.rerun()

    if st.session_state.user['role'] == 'student':
        student_profile = get_student_profile(st.session_state.user['email'])
        if student_profile:
            if not student_profile['quiz_completed']:
                conduct_quiz(st.session_state.user['id'])
            elif not st.session_state.get('learning_style_completed', False) and not student_profile.get('learning_style', ''):
                conduct_learning_style_quiz(st.session_state.user['id'])
            else:
                student_dashboard()
        else:
            st.warning("Student profile not found. Please contact support. 📞")
    
    elif st.session_state.user['role'] == 'teacher':
        st.markdown("<div class='dashboard'>", unsafe_allow_html=True)
        st.title("Teacher Dashboard 👩‍🏫")
        teacher_options = st.selectbox("Options", ["Student Performance Analytics", "Upload Course", "View My Courses"], key="teacher_options")
        
        if teacher_options == "Student Performance Analytics":
            st.markdown("<div class='section-container'>", unsafe_allow_html=True)
            st.subheader("Student Performance Dashboard 📊")
            st.markdown("""
            <div class="insights-container">
                <h3>Class Performance Overview 📈</h3>
                <p>Analyze your students' performance, engagement, and skill development. Use the tools below to import new student data or view detailed analytics.</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Provide a downloadable JSON template
            template_data = [
                {
                    "email": "student@example.com",
                    "performance": {
                        "overall_score": 85.0,
                        "progress": 70.0,
                        "skills": {
                            "Critical Thinking": 80.0,
                            "Problem Solving": 85.0,
                            "Communication": 75.0,
                            "Collaboration": 90.0,
                            "Technical Knowledge": 88.0
                        }
                    },
                    "engagement": {
                        "videos_watched": 20,
                        "quizzes_completed": 10,
                        "discussion_posts": 5,
                        "assignments_submitted": 15,
                        "login_days": 25
                    },
                    "challenges": ["Time management", "Complex problem solving"],
                    "support_needs": ["Additional practice problems", "One-on-one tutoring"],
                    "personalized_insights": "Focus on time management strategies to improve efficiency.",
                    "level": "Intermediate",
                    "learning_style": "Visual"
                }
            ]
            template_json = json.dumps(template_data, indent=2)
            st.download_button(
                label="Download Student Data Template 📥",
                data=template_json,
                file_name="student_data_template.json",
                mime="application/json"
            )
            
            # Student data upload
            st.markdown("<div class='insights-container'>", unsafe_allow_html=True)
            st.subheader("Upload Student Data 📤")
            st.write("""
            Upload a JSON file containing student performance data. The file should follow the provided template format.
            Ensure students are enrolled in your courses and the email addresses match registered users.
            """)
            uploaded_file = st.file_uploader("Choose a JSON file", type=["json"])
            if uploaded_file:
                success, message = import_student_data(uploaded_file, st.session_state.user['id'])
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            st.markdown("</div>", unsafe_allow_html=True)
            
            student_names, student_scores = get_class_performance_comparison(st.session_state.user['id'])
            if student_names and student_scores:
                avg_score = sum(student_scores) / len(student_scores) if student_scores else 0
                st.markdown("<div class='section-container chart-container'>", unsafe_allow_html=True)
                st.subheader("Performance Comparison 📊")
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=student_names,
                    y=student_scores,
                    marker_color=['#3b82f6' if score < avg_score else '#4CAF50' for score in student_scores],
                    text=[f"{score:.1f}%" for score in student_scores],
                    textposition='auto',
                    name='Student Scores'
                ))
                fig.add_trace(go.Scatter(
                    x=student_names,
                    y=[avg_score] * len(student_names),
                    mode='lines',
                    name=f'Class Average: {avg_score:.1f}%',
                    line=dict(color='rgba(0, 0, 0, 0.8)', width=2, dash='dash')
                ))
                fig.update_layout(
                    title='Student Performance Comparison',
                    xaxis_title='Students',
                    yaxis_title='Score (%)',
                    yaxis=dict(range=[0, 100]),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='#1e293b',
                    height=400,
                    legend=dict(
                        yanchor="top",
                        y=0.99,
                        xanchor="right",
                        x=0.99
                    )
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("<div class='section-container chart-container'>", unsafe_allow_html=True)
                st.subheader("Score Distribution 📈")
                fig = px.histogram(
                    x=student_scores,
                    nbins=10,
                    labels={'x': 'Score (%)'},
                    title='Score Distribution',
                    color_discrete_sequence=['#3b82f6']
                )
                fig.add_vline(
                    x=avg_score, 
                    line_dash="dash", 
                    line_color="black",
                    annotation_text=f"Average: {avg_score:.1f}%", 
                    annotation_position="top right"
                )
                fig.update_layout(
                    xaxis_title='Score Range',
                    yaxis_title='Number of Students',
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='#1e293b',
                    height=300
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("<div class='section-container chart-container'>", unsafe_allow_html=True)
                st.subheader("Class Skill Assessment 🌟")
                skills = ['Critical Thinking', 'Problem Solving', 'Communication', 'Collaboration', 'Technical Knowledge']
                skill_avgs = []
                students = get_students(st.session_state.user['id'])
                for skill in skills:
                    skill_scores = []
                    for student in students:
                        skills_dict, _ = get_student_skill_assessment(student['id'])
                        skill_scores.append(skills_dict.get(skill, np.random.uniform(60, 95)))
                    skill_avgs.append(np.mean(skill_scores))
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=skills,
                    y=skill_avgs,
                    marker_color='#3b82f6',
                    text=[f"{val:.1f}%" for val in skill_avgs],
                    textposition='auto',
                ))
                fig.update_layout(
                    title='Class Average by Skill',
                    xaxis_title='Skills',
                    yaxis_title='Average Score (%)',
                    yaxis=dict(range=[0, 100]),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='#1e293b',
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("<div class='section-container'>", unsafe_allow_html=True)
                st.subheader("Student Data 📋")
                student_data = []
                for student in students:
                    try:
                        performance_str = student.get('performance') or '{}'
                        engagement_str = student.get('engagement') or '{}'
                        challenges_str = student.get('challenges') or '[]'
                        support_needs_str = student.get('support_needs') or '[]'
                        if performance_str is None:
                            performance_str = '{}'
                        if engagement_str is None:
                            engagement_str = '{}'
                        if challenges_str is None:
                            challenges_str = '[]'
                        if support_needs_str is None:
                            support_needs_str = '[]'
                        performance = json.loads(performance_str)
                        engagement = json.loads(engagement_str)
                        challenges = json.loads(challenges_str)
                        support_needs = json.loads(support_needs_str)
                        student_dict = {
                            'Name': student['name'],
                            'Email': student['email'],
                            'Level': student['level'],
                            'Learning Style': student['learning_style'] or 'Not Assessed',
                            'Performance': performance.get('overall_score', 'N/A'),
                            'Progress': performance.get('progress', 'N/A'),
                            'Engagement': engagement.get('level', 'N/A'),
                            'Challenges': len(challenges),
                            'Support Needs': len(support_needs)
                        }
                        student_data.append(student_dict)
                    except json.JSONDecodeError:
                        continue
                if student_data:
                    df = pd.DataFrame(student_data)
                    st.dataframe(
                        df.style.background_gradient(
                            subset=['Performance', 'Progress', 'Engagement'],
                            cmap='Blues',
                            axis=None
                        ).format({
                            'Performance': lambda x: f'{x:.1f}%' if isinstance(x, (int, float)) else x,
                            'Progress': lambda x: f'{x:.1f}%' if isinstance(x, (int, float)) else x,
                            'Engagement': lambda x: f'{x:.1f}%' if isinstance(x, (int, float)) else x
                        }),
                        height=400
                    )
                
                st.markdown("<div class='section-container'>", unsafe_allow_html=True)
                st.subheader("Individual Student Analysis 🔍")
                if student_data:
                    selected_student = st.selectbox("Select student to view detailed analysis:", 
                                                options=[s['Name'] for s in student_data], key="select_student")
                    for student in students:
                        if student['name'] == selected_student:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("""
                                <div class="insights-container">
                                    <h4>Profile & Performance 📊</h4>
                                </div>
                                """, unsafe_allow_html=True)
                                st.markdown(f"""
                                <div class="profile-section">
                                    <div><strong>Name:</strong> {student['name']}</div>
                                    <div><strong>Email:</strong> {student['email']}</div>
                                    <div><strong>Level:</strong> {student['level']}</div>
                                    <div><strong>Learning Style:</strong> {student['learning_style'] or 'Not Assessed'}</div>
                                </div>
                                """, unsafe_allow_html=True)
                                try:
                                    performance_str = student.get('performance') or '{}'
                                    if performance_str is None:
                                        performance_str = '{}'
                                    performance = json.loads(performance_str)
                                    score = performance.get('overall_score', 75)
                                    progress = performance.get('progress', 65)
                                    score_color = '#4CAF50' if float(score) >= 80 else '#FF9800' if float(score) >= 70 else '#F44336'
                                    st.markdown(f"""
                                    <div class="metric-card">
                                        <div class="metric-label">Overall Score</div>
                                        <div class="metric-value" style="color:{score_color}">{score}%</div>
                                        <div class="progress-bar-container">
                                            <div class="progress-bar" style="width:{score}%"></div>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    st.markdown(f"""
                                    <div class="metric-card">
                                        <div class="metric-label">Course Progress</div>
                                        <div class="metric-value" style="color:#3b82f6">{progress}%</div>
                                        <div class="progress-bar-container">
                                            <div class="progress-bar" style="width:{progress}%"></div>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                except json.JSONDecodeError:
                                    st.warning("Invalid performance data format ⚠️")
                                st.markdown("<div class='section-container chart-container'>", unsafe_allow_html=True)
                                st.subheader("Performance Trend 📈")
                                progress_data = get_student_progress_history(student['id'])
                                if progress_data:
                                    df = pd.DataFrame(progress_data)
                                    fig = px.line(
                                        df, x='month', y='score', 
                                        markers=True, 
                                        line_shape='spline',
                                        title='Performance Over Time',
                                        labels={'month': 'Month', 'score': 'Score'},
                                        color_discrete_sequence=['#3b82f6']
                                    )
                                    fig.update_layout(
                                        plot_bgcolor='rgba(0,0,0,0)',
                                        paper_bgcolor='rgba(0,0,0,0)',
                                        font_color='#1e293b',
                                        height=300
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                st.markdown("</div>", unsafe_allow_html=True)
                            with col2:
                                st.markdown("""
                                <div class="insights-container">
                                    <h4>Engagement & Skills 📈</h4>
                                </div>
                                """, unsafe_allow_html=True)
                                try:
                                    engagement_metrics = get_student_engagement_metrics(student['id'])
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.markdown(f"""
                                        <div class="metric-card">
                                            <div class="metric-label">Videos Watched 🎥</div>
                                            <div class="metric-value">{engagement_metrics['videos_watched']}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                    with col2:
                                        st.markdown(f"""
                                        <div class="metric-card">
                                            <div class="metric-label">Quizzes Completed ✅</div>
                                            <div class="metric-value">{engagement_metrics['quizzes_completed']}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                    with col3:
                                        st.markdown(f"""
                                        <div class="metric-card">
                                            <div class="metric-label">Discussion Posts 💬</div>
                                            <div class="metric-value">{engagement_metrics['discussion_posts']}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.markdown(f"""
                                        <div class="metric-card">
                                            <div class="metric-label">Assignments Submitted 📝</div>
                                            <div class="metric-value">{engagement_metrics['assignments_submitted']}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                    with col2:
                                        st.markdown(f"""
                                        <div class="metric-card">
                                            <div class="metric-label">Active Days 📅</div>
                                            <div class="metric-value">{engagement_metrics['login_days']}/30</div>
                                            <div class="progress-bar-container">
                                                <div class="progress-bar" style="width:{(engagement_metrics['login_days']/30)*100}%"></div>
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                except json.JSONDecodeError:
                                    st.warning("Invalid engagement data format ⚠️")
                                st.markdown("<div class='section-container chart-container'>", unsafe_allow_html=True)
                                st.subheader("Skills Assessment 🌟")
                                skills, categories = get_student_skill_assessment(student['id'])
                                if skills:
                                    fig = go.Figure()
                                    values = list(skills.values())
                                    fig.add_trace(go.Scatterpolar(
                                        r=values,
                                        theta=categories,
                                        fill='toself',
                                        name='Skills',
                                        line_color='#3b82f6',
                                        fillcolor='rgba(59, 130, 246, 0.5)',
                                    ))
                                    fig.update_layout(
                                        polar=dict(
                                            radialaxis=dict(
                                                visible=True,
                                                range=[0, 100]
                                            )
                                        ),
                                        showlegend=False,
                                        plot_bgcolor='rgba(0,0,0,0)',
                                        paper_bgcolor='rgba(0,0,0,0)',
                                        font_color='#1e293b',
                                        height=300
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                st.markdown("</div>", unsafe_allow_html=True)
                            challenges_str = student.get('challenges') or '[]'
                            support_needs_str = student.get('support_needs') or '[]'
                            if challenges_str is None:
                                challenges_str = '[]'
                            if support_needs_str is None:
                                support_needs_str = '[]'
                            try:
                                challenges = json.loads(challenges_str)
                                support_needs = json.loads(support_needs_str)
                                if challenges:
                                    st.markdown("<div class='section-container chart-container'>", unsafe_allow_html=True)
                                    st.subheader("Areas for Improvement 🔍")
                                    challenge_data = [{'Challenge': c, 'Priority': i} for i, c in enumerate(challenges, 1)]
                                    df = pd.DataFrame(challenge_data)
                                    fig = px.bar(
                                        df, 
                                        x='Challenge', 
                                        y='Priority',
                                        color='Priority',
                                        color_continuous_scale=['#3b82f6', '#60a5fa'],
                                        labels={'Priority': 'Importance'},
                                        title='Focus Areas'
                                    )
                                    fig.update_layout(
                                        xaxis_title=None,
                                        plot_bgcolor='rgba(0,0,0,0)',
                                        paper_bgcolor='rgba(0,0,0,0)',
                                        font_color='#1e293b',
                                        height=300
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                    st.markdown("</div>", unsafe_allow_html=True)
                                if support_needs:
                                    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
                                    st.subheader("Recommended Support 🤝")
                                    for need in support_needs:
                                        st.markdown(f"""
                                        <div class="metric-card" style="text-align:left;">
                                            ✓ {need}
                                        </div>
                                        """, unsafe_allow_html=True)
                                    st.markdown("</div>", unsafe_allow_html=True)
                                if student.get('personalized_insights'):
                                    st.markdown("<div class='section-container insights-container'>", unsafe_allow_html=True)
                                    st.subheader("Personalized Insights 💡")
                                    st.markdown(student['personalized_insights'], unsafe_allow_html=True)
                                    st.markdown("</div>", unsafe_allow_html=True)
                            except json.JSONDecodeError:
                                st.warning("Invalid challenges or support needs data format ⚠️")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("No student data available. Upload student data to view analytics. 😔")
            st.markdown("</div>", unsafe_allow_html=True)
        
        elif teacher_options == "Upload Course":
            st.markdown("<div class='section-container'>", unsafe_allow_html=True)
            st.subheader("Upload New Course 📚")
            with st.form("upload_course_form", clear_on_submit=True):
                course_title = st.text_input("Course Title 📖", placeholder="Enter course title")
                course_description = st.text_area("Course Description 📝", placeholder="Enter course description")
                course_files = st.file_uploader("Upload Course Materials 📂", accept_multiple_files=True, type=['pdf', 'docx', 'mp4'])
                if st.form_submit_button("Upload Course 🚀"):
                    success, message = upload_course(
                        course_title, 
                        course_description, 
                        st.session_state.user['id'], 
                        course_files
                    )
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
            st.markdown("</div>", unsafe_allow_html=True)
        
        elif teacher_options == "View My Courses":
            st.markdown("<div class='section-container'>", unsafe_allow_html=True)
            st.subheader("My Courses 📚")
            courses = get_teacher_courses(st.session_state.user['id'])
            if courses:
                for course in courses:
                    st.markdown(f"""
                    <div class="course-card">
                        <div class="course-title">{course['title']}</div>
                        <div class="course-description">{course['description']}</div>
                    """, unsafe_allow_html=True)
                    files = get_course_files(course['id'])
                    if files:
                        st.write("Course Materials:")
                        for file in files:
                            file_name = file['file_path'].split('/')[-1]
                            st.markdown(f"- {file_name}", unsafe_allow_html=True)
                            try:
                                with open(file['file_path'], 'rb') as f:
                                    st.download_button(
                                        label="Download 📥",
                                        data=f,
                                        file_name=file_name,
                                        key=f"download_teacher_{file['id']}"
                                    )
                            except FileNotFoundError:
                                st.warning(f"File {file_name} not found.")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Edit Course ✏️", key=f"edit_{course['id']}"):
                            st.session_state.edit_course_id = course['id']
                            st.session_state.edit_course_title = course['title']
                            st.session_state.edit_course_description = course['description']
                            st.session_state.page = f"edit_course_{course['id']}"
                            st.rerun()
                    with col2:
                        with st.form(key=f"delete_form_{course['id']}"):
                            st.markdown(
                                f"<button type='submit' style='background: linear-gradient(90deg, #ef4444, #f87171); color: #ffffff; border: none; padding: 10px 20px; border-radius: 8px; font-size: 1em; font-weight: 500; cursor: pointer; display: inline-block; margin-top: 10px;'>Delete Course 🗑️</button>",
                                unsafe_allow_html=True
                            )
                            submitted = st.form_submit_button(label="", use_container_width=True)
                            if submitted:
                                success, message = delete_course(course['id'], st.session_state.user['id'])
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("You haven't uploaded any courses yet 😔")
            st.markdown("</div>", unsafe_allow_html=True)
        
        if st.session_state.get('page', '').startswith("edit_course_"):
            course_id = int(st.session_state.page.split("_")[-1])
            st.markdown("<div class='section-container'>", unsafe_allow_html=True)
            st.subheader(f"Edit Course: {st.session_state.edit_course_title} ✏️")
            with st.form("edit_course_form", clear_on_submit=True):
                course_title = st.text_input("Course Title 📖", value=st.session_state.edit_course_title)
                course_description = st.text_area("Course Description 📝", value=st.session_state.edit_course_description)
                new_files = st.file_uploader("Add New Course Materials 📂", accept_multiple_files=True, type=['pdf', 'docx', 'mp4'])
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Update Course 🚀"):
                        success, message = update_course(
                            course_id,
                            st.session_state.user['id'],
                            course_title,
                            course_description,
                            new_files
                        )
                        if success:
                            st.success(message)
                            st.session_state.page = 'teacher_dashboard'
                            st.session_state.edit_course_id = None
                            st.rerun()
                        else:
                            st.error(message)
                with col2:
                    if st.form_submit_button("Cancel ❌"):
                        st.session_state.page = 'teacher_dashboard'
                        st.session_state.edit_course_id = None
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)