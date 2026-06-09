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

st.title("School Database Dashboard")

#show students data
if st.checkbox("Show all students"):
    students_df = run_query("SELECT * FROM students")
    st.dataframe(students_df)

# add a new student
with st.form("Add Student"):
    fname = st.text_input("First Name")
    lname = st.text_input("Last Name")
    email = st.text_input("Email")
    grade = st.number_input("Grade level (0-12)", min_value=0, max_value=12, step=1)
    submitted = st.form_submit_button("Add Student")
    if submitted:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO students (first_name, last_name, email, grade) VALUES (%s, %s, %s, %s)",
                           (fname, lname, email, grade))
            conn.commit()
            st.success("Student added!")
        except mysql.connector.Error as err:
            st.error(f"Error: {err}")
        finally:
            cursor.close()
