import streamlit as st
import mysql.connector
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()



# database connection function with caching to optimize performance
def init_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"),
        database="school_db",
        auth_plugin="mysql_native_password"
    )

def get_conn():
    if 'conn' not in st.session_state or not st.session_state.conn.is_connected():
        st.session_state.conn = init_connection()
    return st.session_state.conn

conn = get_conn()

# Query with panda
def run_query(query):
    return pd.read_sql(query, get_conn())

# Initialize session state for filters
if 'selected_semester_id' not in st.session_state:
    st.session_state.selected_semester_id = None
if 'selected_year_id' not in st.session_state:
    st.session_state.selected_year_id = None
if 'grade_filter' not in st.session_state:
    st.session_state.grade_filter = "All Grades"
if 'grade_update_message' not in st.session_state:
    st.session_state.grade_update_message = None
# Sidebar - Academic Period Selector
st.sidebar.title("📚 School Database")
st.sidebar.subheader("📅 Academic Period")

try:
    # Get available academic years - check if table exists first
    years_check = run_query("SHOW TABLES LIKE 'academic_years'")
    if years_check.empty:
        st.sidebar.error("⚠️ academic_years table not found. Please run database migration.")
        st.session_state.selected_year_id = None
        st.session_state.selected_semester_id = None
    else:
        years_df = run_query("SELECT year_id, year_name, is_current FROM academic_years ORDER BY year_name DESC")
        
        if years_df.empty:
            st.sidebar.warning("No academic years configured. Please add them in MySQL.")
            st.session_state.selected_year_id = None
            st.session_state.selected_semester_id = None
        else:
            # Check if 'is_current' column exists
            if 'is_current' in years_df.columns:
                # Find current year index
                current_mask = years_df['is_current'] == True
                if current_mask.any():
                    default_idx = years_df.index.get_loc(current_mask.idxmax())
                else:
                    default_idx = 0
            else:
                st.sidebar.warning("'is_current' column missing. Using first year as default.")
                default_idx = 0
            
            year_options = {row['year_name']: row['year_id'] for _, row in years_df.iterrows()}
            selected_year_name = st.sidebar.selectbox(
                "Academic Year",
                list(year_options.keys()),
                index=min(default_idx, len(year_options)-1)
            )
            st.session_state.selected_year_id = year_options[selected_year_name]
            
            # Get semesters for selected year
            semesters_df = run_query(f"""
                SELECT semester_id, semester_name, semester_order 
                FROM semesters 
                WHERE year_id = {st.session_state.selected_year_id}
                ORDER BY semester_order
            """)
            
            if semesters_df.empty:
                st.sidebar.warning(f"No semesters found for {selected_year_name}")
                st.session_state.selected_semester_id = None
            else:
                semester_options = {row['semester_name']: row['semester_id'] for _, row in semesters_df.iterrows()}
                default_semester = 'Fall' if 'Fall' in semester_options else list(semester_options.keys())[0]
                selected_semester_name = st.sidebar.selectbox(
                    "Semester",
                    list(semester_options.keys()),
                    index=list(semester_options.keys()).index(default_semester)
                )
                st.session_state.selected_semester_id = semester_options[selected_semester_name]
                
                st.sidebar.success(f"📚 Viewing: {selected_semester_name} {selected_year_name}")
                
except Exception as e:
    st.sidebar.error(f"Error loading academic data: {str(e)}")
    st.session_state.selected_year_id = None
    st.session_state.selected_semester_id = None

# Sidebar - Grade Level Filter
st.sidebar.subheader("🎓 Grade Level Filter")
grade_filter = st.sidebar.selectbox(
    "Show students in:",
    ["All Grades", "Grade 9", "Grade 10", "Grade 11", "Grade 12"],
    key="grade_filter_widget"
)
st.session_state.grade_filter = grade_filter

# Convert to SQL condition
grade_condition = ""
if grade_filter != "All Grades":
    grade_level = int(grade_filter.split()[1])
    grade_condition = f"AND s.grade_level = {grade_level}"

# Navigation menu
menu = st.sidebar.selectbox("Navigation", [
    "Dashboard",
    "Student Summary", 
    "Course Summary", 
    "Enrollments & Grades", 
    "Add Records", 
    "View Data"
])

if menu == "View Data":
    st.subheader("View Tables")
    table = st.selectbox("Choose table", ["students", "teachers", "courses", "enrollments"])
    if st.button("Show Data"):
        if table == "enrollments":
            semester_filter_clause = ""
            if st.session_state.selected_semester_id:
                semester_filter_clause = f"AND e.semester_id = {st.session_state.selected_semester_id}"
            # Custom query with names instead of IDs for better readability
            df = run_query(f"""
                SELECT e.enrollment_id, 
                       CONCAT(s.first_name, ' ', COALESCE(s.middle_name, ''), ' ', s.last_name) AS student_name, 
                       c.course_name,
                       DATE(e.enrollment_date) AS enrollment_date,
                       COALESCE(e.final_grade, 'Not graded') AS final_grade,
                       sem.semester_name,
                       ay.year_name
                FROM enrollments e
                JOIN students s ON e.student_id = s.student_id
                JOIN courses c ON e.course_id = c.course_id
                JOIN semesters sem ON e.semester_id = sem.semester_id
                JOIN academic_years ay ON e.academic_year_id = ay.year_id
                WHERE 1=1
                {semester_filter_clause}
                ORDER BY e.enrollment_id DESC
            """)
        else:
            df = run_query(f"SELECT * FROM {table}")
        st.dataframe(df, use_container_width=True)

# Dashboard with key metrics and recent activity
elif menu == "Dashboard":
    # Check if semester is selected
    if st.session_state.selected_semester_id is None:
        st.warning("⚠️ Please select an academic year and semester from the sidebar first.")
        st.info("If no options appear, run the database migration script to set up academic years and semesters.")
    else:
        st.subheader(f"School Dashboard")
        
        semester_filter = f"WHERE semester_id = {st.session_state.selected_semester_id}"
        
        # Get counts
        try:
            student_count = run_query(f"""
                SELECT COUNT(DISTINCT student_id) as count 
                FROM enrollments 
                {semester_filter}
            """).iloc[0]['count']
            
            course_count = run_query(f"""
                SELECT COUNT(DISTINCT course_id) as count 
                FROM enrollments 
                {semester_filter}
            """).iloc[0]['count']
            
            enrollment_count = run_query(f"SELECT COUNT(*) as count FROM enrollments {semester_filter}").iloc[0]['count']
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Active Students", student_count)
            with col2:
                st.metric("Active Courses", course_count)
            with col3:
                st.metric("Total Enrollments", enrollment_count)
            
            # Top Students by GPA
            st.subheader("🏆 Top Students This Semester")
            
            grade_points = {'S': 4.0, 'A': 3.5, 'B': 3.0, 'C': 2.0, 'D': 1.0}
            
            top_students_df = run_query(f"""
                SELECT 
                    s.student_id,
                    CONCAT(s.first_name, ' ', COALESCE(s.middle_name, ''), ' ', s.last_name) AS student_name,
                    s.grade_level,
                    e.final_grade
                FROM enrollments e
                JOIN students s ON e.student_id = s.student_id
                WHERE e.semester_id = {st.session_state.selected_semester_id}
                AND e.final_grade IS NOT NULL
                {grade_condition}
            """)
            
            if not top_students_df.empty:
                # Calculate GPA per student
                gpa_results = []
                for student_id in top_students_df['student_id'].unique():
                    student_grades = top_students_df[top_students_df['student_id'] == student_id]
                    points = [grade_points[g] for g in student_grades['final_grade'] if g in grade_points]
                    if points:
                        avg_gpa = sum(points) / len(points)
                        gpa_results.append({
                            'student_name': student_grades['student_name'].iloc[0],
                            'grade_level': student_grades['grade_level'].iloc[0],
                            'gpa': avg_gpa,
                            'courses_taken': len(points)
                        })
                
                if gpa_results:
                    top_gpa_df = pd.DataFrame(gpa_results).sort_values('gpa', ascending=False).head(10)
                    
                    for idx, row in top_gpa_df.iterrows():
                        col1, col2, col3 = st.columns([3,1,1])
                        with col1:
                            st.write(f"**{row['student_name']}** (Grade {row['grade_level']})")
                        with col2:
                            st.write(f"GPA: {row['gpa']:.2f}")
                        with col3:
                            st.write(f"{row['courses_taken']} courses")
                    
                    # Bar chart of top 5
                    st.subheader("Top 5 Students GPA Comparison")
                    chart_data = top_gpa_df.head(5)[['student_name', 'gpa']]
                    st.bar_chart(chart_data.set_index('student_name'))
                else:
                    st.info("No complete grade records found.")
            else:
                st.info("No grades recorded yet this semester.")
            
            # Grade distribution
            st.subheader("📊 Semester Grade Distribution")
            grade_dist = run_query(f"""
                SELECT 
                    final_grade,
                    COUNT(*) as count
                FROM enrollments
                WHERE semester_id = {st.session_state.selected_semester_id}
                AND final_grade IS NOT NULL
                GROUP BY final_grade
                ORDER BY FIELD(final_grade, 'S', 'A', 'B', 'C', 'D')
            """)
            
            if not grade_dist.empty:
                st.bar_chart(grade_dist.set_index('final_grade'))
            else:
                st.info("No grades recorded this semester.")
                
        except Exception as e:
            st.error(f"Error loading dashboard data: {str(e)}")
            st.info("Make sure your database has enrollments with valid semester_id values.")

# Add new students and teachers with validation
elif menu == "Add Records":
    st.subheader("Add a New Student")
    with st.form("New Student"):
        fname = st.text_input("First Name")
        mname = st.text_input("Middle Name (Optional)")
        lname = st.text_input("Last Name")
        email = st.text_input("Email")
        grade_level = st.number_input("Grade level (9-12)", min_value=9, max_value=12, step=1)
        submitted = st.form_submit_button("Add Student")
        if submitted:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO students (first_name, middle_name, last_name, email, grade_level) VALUES (%s, %s, %s, %s, %s)",
                            (fname, mname if mname else None, lname, email, grade_level)
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
    # Show enrollments table at the top (filtered by semester)
    st.subheader(f"Current Enrollments - Semester {st.session_state.selected_semester_id if st.session_state.selected_semester_id else 'All'}")

    semester_filter_clause = ""
    if st.session_state.selected_semester_id:
        semester_filter_clause = f"AND e.semester_id = {st.session_state.selected_semester_id}"

    enrollments_view = run_query(f"""
        SELECT
            CONCAT(s.first_name, ' ', COALESCE(s.middle_name, ''), ' ', s.last_name) AS student_name,
            c.course_name AS course,
            DATE(e.enrollment_date) AS enrollment_on,
            COALESCE(e.final_grade, 'Not graded') AS grade
        FROM enrollments e
        JOIN students s ON e.student_id = s.student_id
        JOIN courses c ON e.course_id = c.course_id
        WHERE 1=1
        {semester_filter_clause}
        ORDER BY e.enrollment_id DESC
    """)
    st.dataframe(enrollments_view, use_container_width=True)

    # Enroll
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
        if st.session_state.selected_semester_id is None:
            st.error("Please select an academic year and semester from the sidebar first.")
        else:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO enrollments (student_id, course_id, semester_id, academic_year_id) VALUES (%s, %s, %s, %s)",
                    (student_id, course_id, st.session_state.selected_semester_id, st.session_state.selected_year_id)
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
    semester_filter_clause = ""
    if st.session_state.selected_semester_id:
        semester_filter_clause = f"AND e.semester_id = {st.session_state.selected_semester_id}"

    enrollments_df = run_query(f"""
        SELECT e.enrollment_id, 
            CONCAT(s.first_name, ' ', IFNULL(s.middle_name, ''), ' ', s.last_name) AS student_name, 
            c.course_name, 
            COALESCE(e.final_grade, 'Not graded') AS final_grade
        FROM enrollments e
        JOIN students s ON e.student_id = s.student_id
        JOIN courses c ON e.course_id = c.course_id
        WHERE 1=1
        {semester_filter_clause}
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
            st.session_state.grade_update_message = f"Grade updated to {new_grade} for {selected_enrollment_label}"
            cursor.close()
            st.rerun()  # Refresh the app

        # Display message if exists
        if st.session_state.grade_update_message:
            st.success(st.session_state.grade_update_message)
            st.session_state.grade_update_message = None  # Clear message after displaying
        if 'grade_update_message' not in st.session_state:
            st.session_state.grade_update_message = None
elif menu == "Student Summary":
    st.subheader("Student Academic Summary")
    
    # Select student
    students_df = run_query("""
        SELECT student_id, 
               CONCAT(first_name, ' ', COALESCE(middle_name, ''), ' ', last_name) AS full_name, grade_level
        FROM students 
        ORDER BY last_name
    """)
    if students_df.empty:
        st.warning("No students found. Please add students first.")
    else:
        student_names = {row['full_name']: row['student_id'] for _, row in students_df.iterrows()}
        selected_student = st.selectbox("Select Student", list(student_names.keys()))
        student_id = student_names[selected_student]
    
        if selected_student:
            # Get student info with parametized query to prevent SQL injection
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT first_name, middle_name, last_name, email, grade_level, enrollment_date
                FROM students WHERE student_id = %s
            """, (student_id,))
            student_info = cursor.fetchone()
            cursor.close()
            
            # Format full name properly
            middle = f" {student_info['middle_name']} " if student_info['middle_name'] else " "
            full_name = f"{student_info['first_name']}{middle}{student_info['last_name']}"
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Student", full_name)
                st.metric("Grade Level", str(student_info['grade_level']))
            with col2:
                st.metric("Email", student_info['email'])
                # Fix the date error here:
                st.metric("Enrolled Since", student_info['enrollment_date'].strftime('%Y-%m-%d'))
            
            # Get grades with parametized query
            grades_df = run_query(f"""
                SELECT c.course_name,
                    COALESCE(e.final_grade, 'Not graded') AS grade,
                    DATE(e.enrollment_date) AS enrolled_date,
                    sem.semester_name,
                    ay.year_name
                FROM enrollments e
                JOIN courses c ON e.course_id = c.course_id
                JOIN semesters sem ON e.semester_id = sem.semester_id
                JOIN academic_years ay ON e.academic_year_id = ay.year_id
                WHERE e.student_id = {student_id}
                {"AND e.semester_id = " + str(st.session_state.selected_semester_id) if st.session_state.selected_semester_id else ""}
                ORDER BY c.course_name
            """)
            
            if not grades_df.empty:
                st.subheader("Course Grades")
                st.dataframe(grades_df, use_container_width=True)
                
                # Grade distribution (only graded courses)
                graded = grades_df[grades_df['grade'] != 'Not graded']
                if not graded.empty:
                    st.subheader("Grade Summary")
                    grade_counts = graded['grade'].value_counts()
                    st.bar_chart(grade_counts)
                    
                    # Add GPA-like summary (optional)
                    grade_points = {'S': 4.0, 'A': 3.5, 'B': 3.0, 'C': 2.0, 'D': 1.0}
                    if all(g in grade_points for g in graded['grade']):
                        avg_points = graded['grade'].map(grade_points).mean()
                        st.metric("Average Grade Point", f"{avg_points:.2f}")
            else:
                st.info("This student is not enrolled in any courses yet.")

elif menu == "Course Summary":
    st.subheader("Course Enrollment Summary")
    
    # Get courses with teacher info
    courses_df = run_query("""
        SELECT course_id, course_name, capacity,
               CONCAT(t.first_name, ' ', t.last_name) AS teacher
        FROM courses c
        JOIN teachers t ON c.teacher_id = t.teacher_id
        ORDER BY course_name
    """)
    
    if courses_df.empty:
        st.warning("No courses found. Please add courses first.")
    else:
        course_options = {row['course_name']: row['course_id'] for _, row in courses_df.iterrows()}
        selected_course_name = st.selectbox("Select Course", list(course_options.keys()))
        course_id = course_options[selected_course_name]
        
        # Get the selected course info
        selected_course = courses_df[courses_df['course_id'] == course_id].iloc[0]
        
        # Show course details (now consistent with selection)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Course", selected_course['course_name'])  # Fixed: shows selected course
            st.metric("Teacher", selected_course['teacher'])
        with col2:
            st.metric("Capacity", selected_course['capacity'])
            
            # Current enrollment count (filtered by semester)
            cursor = conn.cursor()
            if st.session_state.selected_semester_id:
                cursor.execute("SELECT COUNT(*) as count FROM enrollments WHERE course_id = %s AND semester_id = %s", 
                            (course_id, st.session_state.selected_semester_id))
            else:
                cursor.execute("SELECT COUNT(*) as count FROM enrollments WHERE course_id = %s", (course_id,))
            enrollment_count = cursor.fetchone()[0]
            cursor.close()
            st.metric("Enrolled Students", enrollment_count)
        
        # Show enrolled students (filtered by current semester)
        semester_filter_clause = ""
        if st.session_state.selected_semester_id:
            semester_filter_clause = f"AND e.semester_id = {st.session_state.selected_semester_id}"

        students_in_course = run_query(f"""
            SELECT CONCAT(s.first_name, ' ', COALESCE(s.middle_name, ''), ' ', s.last_name) AS student,
                s.grade_level,
                COALESCE(e.final_grade, 'Not graded') AS grade,
                DATE(e.enrollment_date) AS enrolled_on
            FROM enrollments e
            JOIN students s ON e.student_id = s.student_id
            WHERE e.course_id = {course_id}
            {semester_filter_clause}
            ORDER BY s.last_name
        """)
        
        if not students_in_course.empty:
            st.subheader("Enrolled Students")
            st.dataframe(students_in_course, use_container_width=True)
            
            # Grade distribution for this course
            graded = students_in_course[students_in_course['grade'] != 'Not graded']
            if not graded.empty:
                st.subheader("Grade Distribution")
                grade_counts = graded['grade'].value_counts()
                st.bar_chart(grade_counts)
                
                # Show percentage breakdown
                st.subheader("Grade Breakdown (%)")
                percentages = (grade_counts / len(graded) * 100).round(1)
                for grade, pct in percentages.items():
                    st.write(f"{grade}: {pct}%")
        else:
            st.info("No students enrolled in this course yet.")
