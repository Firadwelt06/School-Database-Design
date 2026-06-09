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
