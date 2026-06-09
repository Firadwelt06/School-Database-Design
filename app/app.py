import streamlit as st
import mysql.connector
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# database connection function with caching to optimize performance
@st.cache_resource
def init_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"),
        database="school_db",
        auth_plugin="mysql_native_password"
    )
conn = init_connection()

# simple query with panda
def run_query(query):
    return pd.read_sql(query, conn)

st.title("📚 School Database Manager")

# Sidebar for navigation
menu = st.sidebar.selectbox("Menu", ["View Data", "Add Records", "Enrollments & Grades"])

if menu == "View Data":
    st.subheader("View Tables")
    table = st.selectbox("Choose table", ["students", "teachers", "courses", "enrollments"])
    if st.button("Show Data"):
        df = run_query(f"SELECT * FROM {table}")
        st.dataframe(df)

# Add new students and teachers with validation
elif menu == "Add Records":
    st.subheader("Add a New Student")
    with st.form("New Student"):
        fname = st.text_input("First Name")
        lname = st.text_input("Last Name")
        email = st.text_input("Email")
        grade_level = st.number_input("Grade level (9-12)", min_value=9, max_value=12, step=1)
        submitted = st.form_submit_button("Add Student")
        if submitted:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO students (first_name, last_name, email, grade_level) VALUES (%s, %s, %s, %s)",
                            (fname, lname, email, grade_level)
                )
                conn.commit()
                st.success(f"Student {fname} {lname} added!")
            except mysql.connector.Error as err:
                st.error(f"Error: {err}")
            finally:
                cursor.close()
    # Add new teachers
    st.subheader("Add a New Teacher")
    with st.form("New Teacher"):
        fname = st.text_input("First Name")
        lname = st.text_input("Last Name")
        email = st.text_input("Email")
        hire_date = st.date_input("Hire Date")
        submitted = st.form_submit_button("Add Teacher")
        if submitted:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO teachers (first_name, last_name, email, hire_date) VALUES (%s, %s, %s, %s)",
                            (fname, lname, email, hire_date)
                )
                conn.commit()
                st.success(f"Teacher {fname} {lname} added!")
            except mysql.connector.Error as err:
                st.error(f"Error: {err}")
            finally:
                cursor.close()

# Enroll students in courses and assign grades
elif menu == "Enrollments & Grades":
    st.subheader("Enroll a Student in a Course")
    #get students list
    students_df = run_query("SELECT student_id, first_name, last_name FROM students ORDER BY last_name")
    student_options = {f"{row['first_name']} {row['last_name']}": row['student_id'] for _, row in students_df.iterrows()}
    selected_student = st.selectbox("Student", list(student_options.keys()))
    student_id = student_options[selected_student]

    #get courses list    
    courses_df = run_query("SELECT course_id, course_name FROM courses ORDER BY course_name")
    course_options = {row['course_name']: row['course_id'] for _, row in courses_df.iterrows()}
    selected_course = st.selectbox("Select Course", list(course_options.keys()))
    course_id = course_options[selected_course]
    
    if st.button("Enroll"):
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s)",
                (student_id, course_id)
            )
            conn.commit()
            st.success(f"Enrolled {selected_student} in {selected_course}")
        except mysql.connector.Error as err:
            if "Duplicate entry" in str(err):
                st.warning(f"{selected_student} is already enrolled in {selected_course}")
            else:
                st.error(f"Error: {err}")
        finally:
            cursor.close()
    # Assign grades
    st.subheader("Assign/Update Final Grade")

    #get enrollments list
    enrollments_df = run_query("""
        SELECT e.enrollment_id, CONCAT(s.first_name, ' ', s.last_name) AS student_name, c.course_name, e.final_grade
        FROM enrollments e
        JOIN students s ON e.student_id = s.student_id
        JOIN courses c ON e.course_id = c.course_id
        ORDER BY student_name, course_name
    """)

    if enrollments_df.empty:
        st.info("No enrollments found. Please enroll students in courses first.")
    else:
        # let user select an enrollment to update grade
        enrollment_options = {
            f"{row['student_name']} - {row['course_name']} (current grade: {row['final_grade'] or 'None'})": row['enrollment_id']
            for _, row in enrollments_df.iterrows()
        }
        selected_enrollment_label = st.selectbox("Select Enrollment", list(enrollment_options.keys()))
        enrollment_id = enrollment_options[selected_enrollment_label]

        new_grade = st.selectbox("New Grade", ["", "S", "A", "B", "C", "D", "F"], index=0)
        if st.button("Update Grade") and new_grade:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE enrollments SET final_grade = %s WHERE enrollment_id = %s",
                (new_grade , enrollment_id)
                )
            conn.commit()
            st.success(f"Grade updated to {new_grade}")
            cursor.close()
            st.rerun()  # Refresh the app