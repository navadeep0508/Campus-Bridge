from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import requests
import os
from dotenv import load_dotenv
import time
from supabase import create_client, Client
import bcrypt
import traceback
from functools import wraps

import json

# Explicitly import Cohere to handle potential import issues
try:
    import cohere
except ImportError:
    cohere = None

app = Flask(__name__)
app.secret_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkdm1nenF2cXp1YWVndnFrYXhkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NDM1MjYxNSwiZXhwIjoyMDU5OTI4NjE1fQ.qeufhcj6ypy97jOu0BHIRfqTnz9ZJNHoktibYy_p2NY'  # Ensure a proper secret key is set

# Initialize Supabase client
SUPABASE_URL = 'https://vdvmgzqvqzuaegvqkaxd.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkdm1nenF2cXp1YWVndnFrYXhkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNTI2MTUsImV4cCI6MjA1OTkyODYxNX0.uN8oZhbR1ujwwNpUDULigx5wJQ8XVM5DNxYXDOTvlTU'
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

JUDGE0_API_URL = 'https://judge0-ce.p.rapidapi.com/submissions'
JUDGE0_API_HEADERS = {
    'x-rapidapi-host': 'judge0-ce.p.rapidapi.com',
    'x-rapidapi-key': '2d4a7d825cmsh702550f2a4c30e2p138e11jsn467d292624aa',
    'content-type': 'application/json',
    'accept': 'application/json'
}

# Simple rate limiting
last_request_time = 0
REQUEST_INTERVAL = 1  # Minimum interval between requests in seconds

# Sample coding problems data (replace with database later)
CODING_PROBLEMS = {
    1: {
        'id': 1,
        'title': 'Two Sum',
        'description': 'Given an array of integers nums and an integer target, return indices of the two numbers that add up to target.',
        'difficulty': 'easy',
        'points': 100,
        'test_cases': [
            {'input': '[2,7,11,15], 9', 'output': '[0,1]'},
            {'input': '[3,2,4], 6', 'output': '[1,2]'},
            {'input': '[3,3], 6', 'output': '[0,1]'}
        ]
    },
    2: {
        'id': 2,
        'title': 'Merge Sort Implementation',
        'description': 'Implement the merge sort algorithm to sort an array in ascending order.',
        'difficulty': 'medium',
        'points': 200,
        'test_cases': [
            {'input': '[64,34,25,12,22,11,90]', 'output': '[11,12,22,25,34,64,90]'},
            {'input': '[5,2,8,1,9]', 'output': '[1,2,5,8,9]'},
            {'input': '[38,27,43,3,9,82,10]', 'output': '[3,9,10,27,38,43,82]'}
        ]
    },
    3: {
        'id': 3,
        'title': 'Longest Common Subsequence',
        'description': 'Find the length of the longest common subsequence between two strings.',
        'difficulty': 'hard',
        'points': 300,
        'test_cases': [
            {'input': '"abcde", "ace"', 'output': '3'},
            {'input': '"abc", "abc"', 'output': '3'},
            {'input': '"abc", "def"', 'output': '0'}
        ]
    }
}

# Initialize the code review bot

# Initialize the job match bot


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('landingpage.html')

@app.route('/mycourse')
def mycourse():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    try:
        # Fetch the user's semester
        response = supabase.table('users').select('semester').eq('id', user_id).execute()
        user_data = response.data[0] if response.data else None

        if not user_data:
            return render_template('mycourse.html', error='User not found')

        semester = user_data['semester']
        table_name = f'semester{semester}'

        # Fetch courses for the user's semester
        courses_response = supabase.table(table_name).select('*').execute()
        courses = courses_response.data if courses_response.data else []

        return render_template('mycourse.html', courses=courses)
    except Exception as e:
        print(f"Error fetching courses: {e}")
        traceback.print_exc()
        return render_template('mycourse.html', error='An error occurred')

@app.route('/home')
def home_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    try:
        # Fetch user details with proper query syntax
        response = supabase.table('users')\
            .select('*')\
            .eq('id', user_id)\
            .execute()
        
        if not response.data:
            return render_template('dashboard.html', error='User not found')
            
        user = response.data[0]
        
        if user['role'] == 'faculty':
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['faculty_id'] = user['id']  # Set faculty_id in session
            return redirect(url_for('faculty_home'))
        else:
            return render_template('dashboard.html', user=user)
    except Exception as e:
        print(f"Error fetching user details: {e}")
        traceback.print_exc()
        return render_template('dashboard.html', error='An error occurred')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Fetch user by email with proper query syntax
            response = supabase.table('users')\
                .select('*')\
                .eq('email', email.strip())\
                .execute()
            
            if not response.data:
                return render_template('login.html', error='Invalid credentials')
                
            user = response.data[0]

            if user:
                # Verify password
                if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                    session['user_id'] = user['id']
                    session['role'] = user['role']  # Store the user's role in the session
                    
                    # Check if user is admin
                    if user['role'] == 'admin':
                        return redirect(url_for('dashboard_admin'))
                    elif user['role'] == 'faculty':
                        session['faculty_id'] = user['id']  # Set faculty_id for faculty users
                        return redirect(url_for('faculty_home'))
                    else:
                        return redirect(url_for('home_page'))
                else:
                    return render_template('login.html', error='Invalid credentials')
            else:
                return render_template('login.html', error='Invalid credentials')
        except Exception as e:
            print(f"Error signing in: {e}")
            traceback.print_exc()
            return render_template('login.html', error='An error occurred during login')

    return render_template('login.html')

@app.route('/compiler')
def compiler():
    problem_id = request.args.get('problem_id', type=int)
    problem = CODING_PROBLEMS.get(problem_id) if problem_id else None
    return render_template('compiler.html', problem=problem)

@app.route('/run', methods=['POST'])
def run_code():
    global last_request_time
    current_time = time.time()
    if current_time - last_request_time < REQUEST_INTERVAL:
        return jsonify({'error': 'Rate limit exceeded. Please wait before trying again.'}), 429

    last_request_time = current_time

    data = request.json
    code = data.get('code')
    language = data.get('language')
    input_data = data.get('input')

    if not code or not language:
        return jsonify({'error': 'Missing required fields: code and language'}), 400

    # Map language to Judge0 language_id
    language_map = {
        'python': 71,
        'javascript': 63,
        'java': 62,
        'c': 50,
        'cpp': 54
    }
    language_id = language_map.get(language.lower())

    if not language_id:
        return jsonify({'error': 'Unsupported language'}), 400

    # Prepare the payload for Judge0 API
    payload = {
        'source_code': code,
        'language_id': language_id,
        'stdin': input_data or '',
        'base64_encoded': False
    }

    try:
        # Send the request to Judge0 API
        response = requests.post(JUDGE0_API_URL, headers=JUDGE0_API_HEADERS, json=payload)
        response.raise_for_status()
        token = response.json().get('token')
        
        if not token:
            return jsonify({'error': 'Failed to get submission token'}), 500

        # Poll for the result
        result_url = f"{JUDGE0_API_URL}/{token}"
        max_attempts = 10
        attempts = 0
        
        while attempts < max_attempts:
            result_response = requests.get(result_url, headers=JUDGE0_API_HEADERS)
            result_response.raise_for_status()
            result = result_response.json()
            
            status_id = result.get('status', {}).get('id')
            if status_id in [1, 2]:  # In Queue or Processing
                time.sleep(1)
                attempts += 1
            else:
                break

        if attempts >= max_attempts:
            return jsonify({'error': 'Execution timed out'}), 504

        # Return the result
        return jsonify({
            'stdout': result.get('stdout', ''),
            'stderr': result.get('stderr', ''),
            'status': result.get('status', {}).get('description', 'Unknown'),
            'time': result.get('time', ''),
            'memory': result.get('memory', '')
        })
    except requests.exceptions.RequestException as e:
        print("Error during API request:", e)
        return jsonify({'error': 'Failed to execute code. Please try again.'}), 500
    except Exception as e:
        print("Unexpected error:", e)
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/test-supabase')
def test_supabase():
    try:
        # Query a known table in Supabase
        response = supabase.table('users').select('*').limit(1).execute()
        print("Supabase test response:", response.data)  # Log the response data
        return jsonify({"success": "Supabase connection is working!", "data": response.data}), 200
    except Exception as e:
        print("Error testing Supabase connection:", e)
        return jsonify({"error": "Failed to connect to Supabase."}), 500

@app.route('/update_password', methods=['POST'])
def update_password():
    email = request.form.get('email')
    old_password = request.form.get('old-password')
    new_password = request.form.get('new-password')
    confirm_password = request.form.get('confirm-password')

    if new_password != confirm_password:
        return render_template('confirm_password.html', error='New passwords do not match')

    try:
        # Fetch user by email
        response = supabase.table('users').select('*').eq('email', email).execute()
        user = response.data[0] if response.data else None

        if user:
            # Verify current password
            if bcrypt.checkpw(old_password.encode('utf-8'), user['password'].encode('utf-8')):
                # Hash the new password
                hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                # Update the password in Supabase
                supabase.table('users').update({'password': hashed_new_password.decode('utf-8')}).eq('email', email).execute()
                return redirect(url_for('home_page'))
            else:
                return render_template('confirm_password.html', error='Current password is incorrect')
        else:
            return render_template('confirm_password.html', error='User not found')
    except Exception as e:
        print(f"Error updating password: {e}")
        traceback.print_exc()
        return render_template('confirm_password.html', error='An error occurred')

@app.route('/change_password')
def change_password():
    return render_template('confirm_password.html')

@app.route('/faculty')
def faculty_home():
    faculty_id = session.get('faculty_id')
    if not faculty_id:
        return redirect(url_for('login'))

    print(f"Session faculty_id: {faculty_id}")  # Log the session faculty_id
    try:
        print("Executing query to fetch faculty details...")  # Log query execution
        response = supabase.table('users').select('name', 'roll_number', 'branch', 'subject').eq('id', faculty_id).eq('role', 'faculty').execute()
        faculty = response.data[0] if response.data else None
        print(f"Query response: {response.data}")  # Log the query response
        if faculty:
            return render_template('faculty_dashboard.html', faculty=faculty)
        else:
            print("Faculty not found, rendering error")  # Log faculty not found
            return render_template('faculty_dashboard.html', error='Faculty not found')
    except Exception as e:
        print(f"Error fetching faculty details: {e}")
        traceback.print_exc()
        return render_template('faculty_dashboard.html', error='An error occurred')

@app.route('/faculty/attendance')
def faculty_attendance():
    faculty_id = session.get('faculty_id')
    if not faculty_id:
        return redirect(url_for('login'))
    return render_template('faculty_attendance.html')


@app.route('/attendance')
def attendance():
    try:
        # Get student ID from session
        student_id = session.get('user_id')
        if not student_id:
            return redirect(url_for('login'))

        # Fetch student details
        student_response = supabase.table('users')\
            .select('id, name, roll_number, branch, section')\
            .eq('id', student_id)\
            .execute()
        
        student = student_response.data[0] if student_response.data else None
        if not student:
            return redirect(url_for('login'))

        # Fetch attendance records for the student
        attendance_response = supabase.table('attendance')\
            .select('*')\
            .eq('student_id', student_id)\
            .execute()
        
        # Process attendance data
        attendance_data = {}
        for record in attendance_response.data:
            section = record['section']
            if section not in attendance_data:
                attendance_data[section] = {
                    'attended': record['attended_classes'],
                    'total': record['total_classes'],
                    'percentage': round((record['attended_classes'] / record['total_classes'] * 100) if record['total_classes'] > 0 else 0, 2)
                }

        return render_template('student attendance.html', 
                            student=student,
                            attendance=attendance_data)
    except Exception as e:
        print(f"Error fetching attendance: {e}")
        traceback.print_exc()
        return render_template('student attendance.html', error='Failed to load attendance data')

@app.route('/coding_tracks')
def coding_tracks():
    return render_template('coding tracksss.html')

@app.route('/c_plus_plus')
def c_plus_plus():
    return render_template('c++languagee.html')

@app.route('/python')
def python():
    return render_template('python.html')

@app.route('/timetable/faculty')
def timetable_faculty():
    return render_template('timetable for tac.html')

@app.route('/faculty/assignments', methods=['GET', 'POST'])
def faculty_assignments():
    if request.method == 'POST':
        try:
            # Get form data
            subject = request.form.get('subject')
            year = request.form.get('year')
            branch = request.form.get('branch')
            description = request.form.get('description')
            deadline = request.form.get('deadline')
            faculty_id = session.get('faculty_id')

            print(f"Received form data: subject={subject}, year={year}, branch={branch}, deadline={deadline}, faculty_id={faculty_id}")

            if not all([subject, year, branch, description, deadline, faculty_id]):
                missing_fields = []
                if not subject: missing_fields.append('subject')
                if not year: missing_fields.append('year')
                if not branch: missing_fields.append('branch')
                if not description: missing_fields.append('description')
                if not deadline: missing_fields.append('deadline')
                if not faculty_id: missing_fields.append('faculty_id')
                print(f"Missing required fields: {', '.join(missing_fields)}")
                return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

            # Insert into assessments table
            assessment_data = {
                'faculty_id': faculty_id,
                'subject': subject,
                'year': year,
                'branch': branch,
                'description': description,
                'deadline': deadline,
                'created_at': 'now()'
            }
            
            print(f"Attempting to insert assessment data: {assessment_data}")
            
            response = supabase.table('assessments').insert(assessment_data).execute()
            
            print(f"Supabase response: {response}")
            
            if response.data:
                print(f"Successfully created assessment with ID: {response.data[0]['id']}")
                return jsonify({
                    'message': 'Assignment created successfully',
                    'assessment_id': response.data[0]['id']
                })
            
            print("Failed to create assessment - no data returned from Supabase")
            return jsonify({'error': 'Failed to create assignment - no data returned from database'}), 500

        except Exception as e:
            print(f"Error creating assignment: {str(e)}")
            print(f"Error type: {type(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Failed to create assignment: {str(e)}'}), 500

    return render_template('faculty assignments.html')

@app.route('/myverse')
def myverse():
    return render_template('myverse.html', problems=CODING_PROBLEMS.values())

@app.route('/problem/<int:problem_id>')
def get_problem(problem_id):
    problem = CODING_PROBLEMS.get(problem_id)
    if not problem:
        return jsonify({'error': 'Problem not found'}), 404
    return jsonify(problem)

@app.route('/submit', methods=['POST'])
def submit_solution():
    data = request.get_json()
    problem_id = data.get('problem_id')
    code = data.get('code')
    language_id = data.get('language_id')

    if not all([problem_id, code, language_id]):
        return jsonify({'error': 'Missing required fields'}), 400

    problem = CODING_PROBLEMS.get(problem_id)
    if not problem:
        return jsonify({'error': 'Problem not found'}), 404

    results = []
    for test_case in problem['test_cases']:
        # Prepare the code with test case input
        full_code = f"{code}\n\n# Test case\nprint({test_case['input']})"
        
        # Run the code using Judge0
        submission = {
            'source_code': full_code,
            'language_id': language_id,
            'stdin': '',
            'expected_output': test_case['output']
        }

        try:
            response = requests.post(
                f'{JUDGE0_API_URL}?base64_encoded=false',
                headers=JUDGE0_API_HEADERS,
                json=submission
            )
            
            submission_token = response.json().get('token')
            if not submission_token:
                return jsonify({'error': 'Failed to create submission'}), 500

            # Get the result
            time.sleep(2)  # Wait for processing
            result = requests.get(
                f'{JUDGE0_API_URL}/{submission_token}?base64_encoded=false',
                headers=JUDGE0_API_HEADERS
            ).json()

            results.append({
                'input': test_case['input'],
                'expected': test_case['output'],
                'actual': result.get('stdout', '').strip(),
                'status': result.get('status', {}).get('description', 'Unknown'),
                'passed': result.get('stdout', '').strip() == test_case['output']
            })

        except Exception as e:
            print(f"Error running test case: {e}")
            results.append({
                'input': test_case['input'],
                'error': str(e),
                'passed': False
            })

    # Calculate overall result
    all_passed = all(result.get('passed', False) for result in results)
    
    if all_passed:
        # Update user's points in the database
        try:
            user_id = session.get('user_id')
            if user_id:
                response = supabase.table('users').select('points').eq('id', user_id).execute()
                current_points = response.data[0].get('points', 0) if response.data else 0
                new_points = current_points + problem['points']
                supabase.table('users').update({'points': new_points}).eq('id', user_id).execute()
        except Exception as e:
            print(f"Error updating points: {e}")

    return jsonify({
        'results': results,
        'all_passed': all_passed,
        'points_earned': problem['points'] if all_passed else 0
    })

@app.route('/c')
def c():
    return render_template('c language.html')

@app.route('/java')
def java():
    return render_template('java programming.html')

@app.route('/assignment')
def assignment():
    return render_template('assignment.html')

@app.route('/institution')
def institution():
    return render_template('my institut.html')

@app.route('/faculty/admin')
@admin_required
def faculty_admin():
    try:
        # Fetch all faculty members
        faculty_response = supabase.table('users')\
            .select('id, name, email, subject, branch, created_at')\
            .eq('role', 'faculty')\
            .execute()
        
        faculty = faculty_response.data if faculty_response.data else []
        
        # Fetch faculty sections
        sections_response = supabase.table('faculty_sections')\
            .select('faculty_id, section')\
            .execute()
        
        # Create a map of faculty to their sections
        faculty_sections = {}
        for record in sections_response.data:
            if record['faculty_id'] not in faculty_sections:
                faculty_sections[record['faculty_id']] = []
            faculty_sections[record['faculty_id']].append(record['section'])
        
        # Add sections to faculty data
        for member in faculty:
            member['sections'] = faculty_sections.get(member['id'], [])
        
        return render_template('admin_faculty.html', faculty=faculty)
    except Exception as e:
        print(f"Error fetching faculty data: {e}")
        traceback.print_exc()
        return render_template('admin_faculty.html', error='Failed to load faculty data')

@app.route('/students/admin')
@admin_required
def students_admin():
    try:
        # Fetch all students
        students_response = supabase.table('users')\
            .select('id, name, email, roll_number, branch, section, semester, created_at')\
            .eq('role', 'student')\
            .execute()
        
        students = students_response.data if students_response.data else []
        
        # Fetch attendance for each student
        attendance_response = supabase.table('attendance')\
            .select('student_id, attended_classes, total_classes')\
            .execute()
        
        # Create a map of student to their attendance
        student_attendance = {}
        for record in attendance_response.data:
            student_attendance[record['student_id']] = {
                'attended': record['attended_classes'],
                'total': record['total_classes'],
                'percentage': round((record['attended_classes'] / record['total_classes'] * 100) if record['total_classes'] > 0 else 0, 2)
            }
        
        # Add attendance to student data
        for student in students:
            student['attendance'] = student_attendance.get(student['id'], {
                'attended': 0,
                'total': 0,
                'percentage': 0
            })
        
        return render_template('admin_students.html', students=students)
    except Exception as e:
        print(f"Error fetching student data: {e}")
        traceback.print_exc()
        return render_template('admin_students.html', error='Failed to load student data')

@app.route('/dashboard/admin')
@admin_required
def dashboard_admin():
    try:
        # Fetch statistics
        students_response = supabase.table('users').select('count').eq('role', 'student').execute()
        faculty_response = supabase.table('users').select('count').eq('role', 'faculty').execute()
        courses_response = supabase.table('courses').select('count').execute()
        
        # Fetch attendance data
        attendance_response = supabase.table('attendance').select('attended_classes, total_classes').execute()
        total_attended = sum(record['attended_classes'] for record in attendance_response.data)
        total_classes = sum(record['total_classes'] for record in attendance_response.data)
        avg_attendance = round((total_attended / total_classes * 100) if total_classes > 0 else 0, 2)
        
        # Fetch recent activities
        assignments_response = supabase.table('assessments').select('*').order('created_at', desc=True).limit(5).execute()
        coding_assessments_response = supabase.table('coding_assessments').select('*').order('created_at', desc=True).limit(5).execute()
        
        recent_activities = []
        for assignment in assignments_response.data:
            recent_activities.append({
                'type': 'assignment',
                'title': assignment['subject'],
                'description': assignment['description'],
                'date': assignment['created_at']
            })
        
        for assessment in coding_assessments_response.data:
            recent_activities.append({
                'type': 'coding_assessment',
                'title': assessment['title'],
                'description': assessment['description'],
                'date': assessment['created_at']
            })
        
        # Sort activities by date
        recent_activities.sort(key=lambda x: x['date'], reverse=True)
        
        return render_template('admin.html', 
            stats={
                'total_students': students_response.data[0]['count'],
                'total_faculty': faculty_response.data[0]['count'],
                'total_courses': courses_response.data[0]['count'],
                'avg_attendance': avg_attendance
            },
            recent_activities=recent_activities
        )
    except Exception as e:
        print(f"Error fetching dashboard data: {e}")
        traceback.print_exc()
        return render_template('admin.html', 
            error='Failed to load dashboard data',
            stats={
                'total_students': 0,
                'total_faculty': 0,
                'total_courses': 0,
                'avg_attendance': 0
            },
            recent_activities=[]
        )
    
@app.route('/timetable')
def timetable():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

     

    try:
        # Fetch the user's semester
        response = supabase.table('users').select('semester').eq('id', user_id).execute()
        user_data = response.data[0] if response.data else None

        if not user_data:
            return render_template('timetable.html', error='User not found')

        semester = user_data['semester']
        return render_template('timetable.html', user_semester=semester)
    except Exception as e:
        print(f"Error fetching user semester: {e}")
        return render_template('timetable.html', error='An error occurred')
@app.route('/faculty/coding_assessment', methods=['GET', 'POST'])
def faculty_coding_assessment():
    faculty_id = session.get('faculty_id')
    if not faculty_id:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            # Get form data
            title = request.form.get('title')
            description = request.form.get('description')
            input_format = request.form.get('input_format')
            output_format = request.form.get('output_format')
            difficulty = request.form.get('difficulty', 'medium')
            points = int(request.form.get('points', 100))
            time_limit = int(request.form.get('time_limit', 60))
            memory_limit = int(request.form.get('memory_limit', 512))
            languages = request.form.getlist('languages[]') or ['python', 'java', 'cpp', 'c']

            print("Creating assessment with data:", {
                'title': title,
                'faculty_id': faculty_id,
                'difficulty': difficulty,
                'points': points
            })

            # Insert into coding_assessments table
            assessment_data = {
                'faculty_id': faculty_id,
                'title': title,
                'description': description,
                'input_format': input_format,
                'output_format': output_format,
                'difficulty': difficulty,
                'points': points,
                'time_limit': time_limit,
                'memory_limit': memory_limit,
                'allowed_languages': languages,
                'created_at': 'now()'  # Add creation timestamp
            }
            
            response = supabase.table('coding_assessments').insert(assessment_data).execute()
            print("Assessment creation response:", response.data)
            
            if response.data:
                assessment_id = response.data[0]['id']

                # Get test cases
                test_inputs = request.form.getlist('test_inputs[]')
                test_outputs = request.form.getlist('test_outputs[]')

                # Insert test cases
                for input_data, expected_output in zip(test_inputs, test_outputs):
                    if input_data and expected_output:
                        test_case_data = {
                            'assessment_id': assessment_id,
                            'input_data': input_data,
                            'expected_output': expected_output
                        }
                        supabase.table('assessment_test_cases').insert(test_case_data).execute()

                return render_template('faculty_coding_assesment.html', success='Assessment created successfully!')

            return render_template('faculty_coding_assesment.html', error='Failed to create assessment')

        except Exception as e:
            print(f"Error creating assessment: {e}")
            traceback.print_exc()
            return render_template('faculty_coding_assesment.html', error='Please fill all required fields correctly')

    return render_template('faculty_coding_assesment.html')
@app.route('/student_coding_assesment')
def student_coding_assesment():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    try:
        print("Fetching assessments...")
        
        # Fetch assessments with faculty information
        assessments_response = supabase.table('coding_assessments')\
            .select('''
                *,
                faculty:users!coding_assessments_faculty_id_fkey (
                    name
                )
            ''')\
            .order('created_at', desc=True)\
            .execute()
            
        assessments = assessments_response.data if assessments_response.data else []
        print(f"Found {len(assessments)} assessments:", assessments)

        if not assessments:
            print("No assessments found in the database")
        
        return render_template('student_coding_assesment.html', 
                            assessments=assessments,
                            stats={
                                'total': len(assessments),
                                'completed': 0,
                                'attempts': 0,
                                'time_spent': 0
                            })
                            
    except Exception as e:
        print(f"Error fetching assessments: {e}")
        traceback.print_exc()
        return render_template('student_coding_assesment.html', 
                            error='Failed to load assessments',
                            assessments=[],
                            stats={
                                'total': 0,
                                'completed': 0,
                                'attempts': 0,
                                'time_spent': 0
                            })
    
@app.route('/submit_assessment', methods=['POST'])
def submit_assessment():
    data = request.json
    assessment_id = data.get('assessment_id')
    code = data.get('code')
    language = data.get('language')

    if not all([assessment_id, code, language]):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        # Fetch assessment and its test cases
        assessment_response = supabase.table('coding_assessments').select('*').eq('id', assessment_id).execute()
        assessment = assessment_response.data[0] if assessment_response.data else None

        if not assessment:
            return jsonify({'error': 'Assessment not found'}), 404

        test_cases_response = supabase.table('assessment_test_cases').select('*').eq('assessment_id', assessment_id).execute()
        test_cases = test_cases_response.data if test_cases_response.data else []

        if not test_cases:
            return jsonify({'error': 'No test cases found for this assessment'}), 404

        results = []
        all_passed = True

        for test_case in test_cases:
            # Prepare the payload for Judge0 API
            payload = {
                'source_code': code,
                'language_id': language_map.get(language.lower()),
                'stdin': test_case['input_data'],
                'expected_output': test_case['expected_output'],
                'base64_encoded': False
            }

            # Send the request to Judge0 API
            response = requests.post(JUDGE0_API_URL, headers=JUDGE0_API_HEADERS, json=payload)
            response.raise_for_status()
            token = response.json().get('token')

            if not token:
                return jsonify({'error': 'Failed to get submission token'}), 500

            # Poll for the result
            result_url = f"{JUDGE0_API_URL}/{token}"
            max_attempts = 10
            attempts = 0

            while attempts < max_attempts:
                result_response = requests.get(result_url, headers=JUDGE0_API_HEADERS)
                result_response.raise_for_status()
                result = result_response.json()

                status_id = result.get('status', {}).get('id')
                if status_id in [1, 2]:  # In Queue or Processing
                    time.sleep(1)
                    attempts += 1
                else:
                    break

            if attempts >= max_attempts:
                return jsonify({'error': 'Execution timed out'}), 504

            # Check if the test case passed
            passed = result.get('stdout', '').strip() == test_case['expected_output'].strip()
            all_passed = all_passed and passed

            results.append({
                'input': test_case['input_data'],
                'expected': test_case['expected_output'],
                'actual': result.get('stdout', '').strip(),
                'status': result.get('status', {}).get('description', 'Unknown'),
                'passed': passed
            })

        # If all test cases passed, update the user's points
        if all_passed:
            try:
                user_id = session.get('user_id')
                if user_id:
                    response = supabase.table('users').select('points').eq('id', user_id).execute()
                    current_points = response.data[0].get('points', 0) if response.data else 0
                    new_points = current_points + assessment['points']
                    supabase.table('users').update({'points': new_points}).eq('id', user_id).execute()
            except Exception as e:
                print(f"Error updating points: {e}")

        return jsonify({
            'results': results,
            'all_passed': all_passed,
            'points_earned': assessment['points'] if all_passed else 0
        })

    except requests.exceptions.RequestException as e:
        print("Error during API request:", e)
        return jsonify({'error': 'Failed to execute code. Please try again.'}), 500
    except Exception as e:
        print("Unexpected error:", e)
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/get_sections')
def get_sections():
    try:
        faculty_id = session.get('faculty_id')
        if not faculty_id:
            return jsonify({'error': 'Unauthorized'}), 401

        # Fetch sections that the faculty is assigned to
        response = supabase.table('faculty_sections')\
            .select('section')\
            .eq('faculty_id', faculty_id)\
            .execute()
        
        # Get unique sections
        sections = list(set(record['section'] for record in response.data))
        return jsonify(sections)
    except Exception as e:
        print(f"Error fetching sections: {e}")
        return jsonify({'error': 'Failed to fetch sections'}), 500

@app.route('/get_students')
def get_students():
    try:
        faculty_id = session.get('faculty_id')
        if not faculty_id:
            return jsonify({'error': 'Unauthorized'}), 401

        section = request.args.get('section')
        if not section:
            return jsonify({'error': 'Section is required'}), 400

        print(f"Fetching students for section: {section}")  # Debug log

        # First, let's check if there are any students in the users table
        check_users = supabase.table('users')\
            .select('count')\
            .eq('role', 'student')\
            .execute()
        print(f"Total students in users table: {check_users.data}")  # Debug log

        # Fetch students in the selected section
        response = supabase.table('users')\
            .select('id, name, roll_number, section')\
            .eq('role', 'student')\
            .eq('section', section)\
            .execute()

        print(f"Raw response from database: {response.data}")  # Debug log

        if not response.data:
            print(f"No students found for section {section}")  # Debug log
            return jsonify([])

        students = []
        for student in response.data:
            print(f"Processing student: {student}")  # Debug log
            
            # Get attendance for each student
            attendance_response = supabase.table('attendance')\
                .select('total_classes, attended_classes')\
                .eq('student_id', student['id'])\
                .eq('section', section)\
                .execute()
            
            attendance = attendance_response.data[0] if attendance_response.data else None
            attendance_str = f"{attendance['attended_classes']}/{attendance['total_classes']}" if attendance else '0/0'

            students.append({
                'id': student['id'],
                'name': student['name'],
                'roll_number': student['roll_number'],
                'attendance': attendance_str
            })

        print(f"Final students list: {students}")  # Debug log
        return jsonify(students)
    except Exception as e:
        print(f"Error fetching students: {e}")
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch students'}), 500

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    try:
        data = request.json
        print("Received data:", data)
        
        section = data.get('section')
        date = data.get('date')
        attendance_data = data.get('attendance', [])

        if not all([section, date, attendance_data]):
            return jsonify({'error': 'Missing required fields'}), 400

        results = []
        for student_attendance in attendance_data:
            student_id = student_attendance.get('student_id')
            status = student_attendance.get('status')

            if not all([student_id, status]):
                continue

            try:
                # Check if attendance record exists
                response = supabase.table('attendance')\
                    .select('*')\
                    .eq('student_id', student_id)\
                    .eq('section', section)\
                    .execute()
                
                attendance_record = response.data[0] if response.data else None

                if attendance_record:
                    # Update existing record
                    total_classes = attendance_record['total_classes'] + 1
                    attended_classes = attendance_record['attended_classes'] + (1 if status == 'present' else 0)
                    
                    update_data = {
                        'total_classes': total_classes,
                        'attended_classes': attended_classes,
                        'status': status,
                        'date': date
                    }
                    
                    # Update the record
                    supabase.table('attendance')\
                        .update(update_data)\
                        .eq('student_id', student_id)\
                        .eq('section', section)\
                        .execute()
                    
                    results.append({
                        'student_id': student_id,
                        'attendance': f"{attended_classes}/{total_classes}"
                    })
                else:
                    # Create new record if none exists
                    new_attendance = {
                        'student_id': student_id,
                        'section': section,
                        'date': date,
                        'status': status,
                        'total_classes': 1,
                        'attended_classes': 1 if status == 'present' else 0
                    }
                    
                    supabase.table('attendance').insert(new_attendance).execute()
                    
                    results.append({
                        'student_id': student_id,
                        'attendance': f"{1 if status == 'present' else 0}/1"
                    })

            except Exception as e:
                print(f"Error processing attendance for student {student_id}: {e}")
                continue

        if not results:
            return jsonify({'error': 'No attendance records were processed'}), 400

        return jsonify({
            'message': 'Attendance marked successfully',
            'results': results
        })

    except Exception as e:
        print(f"Error in mark_attendance route: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Failed to mark attendance: {str(e)}'}), 500

@app.route('/get_courses')
def get_courses():
    try:
        faculty_id = session.get('faculty_id')
        if not faculty_id:
            return jsonify({'error': 'Unauthorized'}), 401

        # Fetch courses for the current faculty
        response = supabase.table('courses')\
            .select('*')\
            .eq('faculty_id', faculty_id)\
            .execute()
        
        return jsonify(response.data)
    except Exception as e:
        print(f"Error fetching courses: {e}")
        return jsonify({'error': 'Failed to fetch courses'}), 500

@app.route('/code_room')
def code_room():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    try:
        # Get all active code rooms
        rooms_response = supabase.table('code_rooms')\
            .select('*, participants:code_room_participants(*, user:users(name))')\
            .eq('is_active', True)\
            .execute()
        
        rooms = rooms_response.data if rooms_response.data else []
        
        return render_template('code_room.html', rooms=rooms)
    except Exception as e:
        print(f"Error fetching code rooms: {e}")
        return render_template('code_room.html', error='Failed to load code rooms')

@app.route('/create_code_room', methods=['POST'])
def create_code_room():
    try:
        data = request.json
        name = data.get('name')
        language = data.get('language')
        user_id = session.get('user_id')
        
        if not all([name, language, user_id]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Create new code room
        room_data = {
            'name': name,
            'created_by': user_id,
            'language': language,
            'code': '',
            'is_active': True
        }
        
        room_response = supabase.table('code_rooms').insert(room_data).execute()
        room = room_response.data[0] if room_response.data else None
        
        if room:
            # Add creator as participant
            participant_data = {
                'room_id': room['id'],
                'user_id': user_id,
                'is_online': True
            }
            supabase.table('code_room_participants').insert(participant_data).execute()
            
            return jsonify({
                'message': 'Code room created successfully',
                'room': room
            })
            
        return jsonify({'error': 'Failed to create code room'}), 500
    except Exception as e:
        print(f"Error creating code room: {e}")
        return jsonify({'error': 'Failed to create code room'}), 500

@app.route('/join_code_room/<room_id>', methods=['POST'])
def join_code_room(room_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Convert room_id to integer
        try:
            room_id = int(room_id)
        except ValueError:
            return jsonify({'error': 'Invalid room ID'}), 400
            
        # Check if room exists and is active
        room_response = supabase.table('code_rooms')\
            .select('*')\
            .eq('id', room_id)\
            .eq('is_active', True)\
            .execute()
            
        if not room_response.data:
            return jsonify({'error': 'Room not found or inactive'}), 404
            
        # Check if user is already a participant
        existing_participant = supabase.table('code_room_participants')\
            .select('*')\
            .eq('room_id', room_id)\
            .eq('user_id', user_id)\
            .execute()
            
        if not existing_participant.data:
            # Add user as participant if not already in the room
            participant_data = {
                'room_id': room_id,
                'user_id': user_id,
                'is_online': True
            }
            participant_response = supabase.table('code_room_participants').insert(participant_data).execute()
            if not participant_response.data:
                return jsonify({'error': 'Failed to add participant'}), 500
        
        # Get room details and participants
        room = room_response.data[0]
        participants_response = supabase.table('code_room_participants')\
            .select('*, user:users(name)')\
            .eq('room_id', room_id)\
            .execute()
            
        participants = participants_response.data if participants_response.data else []
        
        # Get messages for the room
        messages_response = supabase.table('code_room_messages')\
            .select('*, user:users(name)')\
            .eq('room_id', room_id)\
            .order('created_at', desc=True)\
            .limit(50)\
            .execute()
            
        messages = messages_response.data if messages_response.data else []
        
        return render_template('code_room_page.html', 
                             room=room, 
                             participants=participants,
                             messages=messages)
    except Exception as e:
        print(f"Error joining code room: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Failed to join code room: {str(e)}'}), 500

@app.route('/update_code/<room_id>', methods=['POST'])
def update_code(room_id):
    try:
        data = request.json
        code = data.get('code')
        user_id = session.get('user_id')
        
        if not all([code, user_id]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Convert room_id to integer
        try:
            room_id = int(room_id)
        except ValueError:
            return jsonify({'error': 'Invalid room ID'}), 400
            
        # Check if user is a participant
        participant_response = supabase.table('code_room_participants')\
            .select('*')\
            .eq('room_id', room_id)\
            .eq('user_id', user_id)\
            .execute()
            
        if not participant_response.data:
            return jsonify({'error': 'Not a participant in this room'}), 403
            
        # Update code
        supabase.table('code_rooms')\
            .update({'code': code})\
            .eq('id', room_id)\
            .execute()
            
        return jsonify({'message': 'Code updated successfully'})
    except Exception as e:
        print(f"Error updating code: {e}")
        return jsonify({'error': 'Failed to update code'}), 500

@app.route('/leave_code_room/<room_id>', methods=['POST'])
def leave_code_room(room_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Remove user from participants
        supabase.table('code_room_participants')\
            .delete()\
            .eq('room_id', room_id)\
            .eq('user_id', user_id)\
            .execute()
            
        # Check if room is empty and deactivate if needed
        participants_response = supabase.table('code_room_participants')\
            .select('*')\
            .eq('room_id', room_id)\
            .execute()
            
        if not participants_response.data:
            supabase.table('code_rooms')\
                .update({'is_active': False})\
                .eq('id', room_id)\
                .execute()
                
        return jsonify({'message': 'Left code room successfully'})
    except Exception as e:
        print(f"Error leaving code room: {e}")
        return jsonify({'error': 'Failed to leave code room'}), 500

@app.route('/get_room_messages/<int:room_id>')
def get_room_messages(room_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # Check if user is a participant
        participant_response = supabase.table('code_room_participants').select('*').eq('room_id', room_id).eq('user_id', session['user_id']).execute()
        if not participant_response.data:
            return jsonify({'error': 'You are not a participant in this room'}), 403

        # Get messages with user details
        messages_response = supabase.table('code_room_messages').select('*, user:users(name)').eq('room_id', room_id).order('created_at', desc=True).limit(50).execute()

        return jsonify({
            'messages': messages_response.data
        })

    except Exception as e:
        print(f"Error fetching messages: {str(e)}")
        return jsonify({'error': 'Failed to fetch messages'}), 500

@app.route('/send_message/<room_id>', methods=['POST'])
def send_message(room_id):
    try:
        data = request.json
        message = data.get('message')
        user_id = session.get('user_id')
        
        if not all([message, user_id]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Convert room_id to integer
        try:
            room_id = int(room_id)
        except ValueError:
            return jsonify({'error': 'Invalid room ID'}), 400
            
        # Check if user is a participant
        participant_response = supabase.table('code_room_participants')\
            .select('*')\
            .eq('room_id', room_id)\
            .eq('user_id', user_id)\
            .execute()
            
        if not participant_response.data:
            return jsonify({'error': 'Not a participant in this room'}), 403
            
        # Send message
        message_data = {
            'room_id': room_id,
            'user_id': user_id,
            'message': message,
            'created_at': 'now()'
        }
        
        supabase.table('code_room_messages').insert(message_data).execute()
        
        return jsonify({'message': 'Message sent successfully'})
    except Exception as e:
        print(f"Error sending message: {e}")
        return jsonify({'error': 'Failed to send message'}), 500

@app.route('/send_code_room_message/<int:room_id>', methods=['POST'])
def send_code_room_message(room_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400

        user_id = int(session['user_id'])

        # Check if room exists and is active
        room_response = supabase.table('code_rooms').select('*').eq('id', room_id).eq('is_active', True).execute()
        if not room_response.data:
            return jsonify({'error': 'Room not found or inactive'}), 404

        # Check if user is a participant
        participant_response = supabase.table('code_room_participants').select('*').eq('room_id', room_id).eq('user_id', user_id).execute()
        if not participant_response.data:
            return jsonify({'error': 'You are not a participant in this room'}), 403

        # Get user name
        user_response = supabase.table('users').select('name').eq('id', user_id).execute()
        user_name = user_response.data[0]['name'] if user_response.data else 'Unknown'

        # Insert message
        message_data = {
            'room_id': room_id,
            'user_id': user_id,
            'message': data['message']
        }
        
        message_response = supabase.table('code_room_messages').insert(message_data).execute()
        
        if not message_response.data:
            return jsonify({'error': 'Failed to send message'}), 500

        created_message = message_response.data[0]

        return jsonify({
            'data': {
                'id': created_message['id'],
                'room_id': room_id,
                'user_id': user_id,
                'user_name': user_name,
                'message': data['message'],
                'created_at': created_message['created_at']
            }
        })

    except Exception as e:
        print(f"Error sending message: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Failed to send message: {str(e)}'}), 500

@app.route('/code_room_page/<room_id>')
def code_room_page(room_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))
            
        # Convert room_id to integer
        try:
            room_id = int(room_id)
        except ValueError:
            return redirect(url_for('code_room'))
            
        # Get room details
        room_response = supabase.table('code_rooms')\
            .select('*')\
            .eq('id', room_id)\
            .eq('is_active', True)\
            .execute()
            
        if not room_response.data:
            return redirect(url_for('code_room'))
            
        room = room_response.data[0]
        
        # Get participants
        participants_response = supabase.table('code_room_participants')\
            .select('*, user:users(name)')\
            .eq('room_id', room_id)\
            .execute()
            
        participants = participants_response.data if participants_response.data else []
        
        # Get messages
        messages_response = supabase.table('code_room_messages')\
            .select('*, user:users(name)')\
            .eq('room_id', room_id)\
            .order('created_at', desc=True)\
            .limit(50)\
            .execute()
            
        messages = messages_response.data if messages_response.data else []
        
        return render_template('code_room_page.html', 
                             room=room, 
                             participants=participants,
                             messages=messages)
    except Exception as e:
        print(f"Error loading code room page: {e}")
        return redirect(url_for('code_room'))

@app.route('/create_assessments_table')
def create_assessments_table():
    try:
        # Create table if it doesn't exist
        create_table_query = """
        -- Drop existing tables if they exist
        DROP TABLE IF EXISTS public.assignment_submissions CASCADE;
        DROP TABLE IF EXISTS public.assessment_links CASCADE;
        DROP TABLE IF EXISTS public.assessments CASCADE;

        -- Create assessments table
        CREATE TABLE public.assessments (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            faculty_id UUID REFERENCES auth.users(id),
            subject TEXT NOT NULL,
            year TEXT NOT NULL,
            branch TEXT NOT NULL,
            description TEXT NOT NULL,
            deadline TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Create assessment_links table
        CREATE TABLE public.assessment_links (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            assessment_id UUID REFERENCES public.assessments(id),
            link_type TEXT NOT NULL,
            link_url TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Create assignment_submissions table
        CREATE TABLE public.assignment_submissions (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            assignment_id UUID REFERENCES public.assessments(id),
            student_id UUID REFERENCES auth.users(id),
            drive_link TEXT NOT NULL,
            comments TEXT,
            submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Add RLS policies for assessments
        ALTER TABLE public.assessments ENABLE ROW LEVEL SECURITY;

        CREATE POLICY "Faculty can view their own assignments"
            ON public.assessments
            FOR SELECT
            USING (faculty_id = auth.uid());

        CREATE POLICY "Faculty can insert their own assignments"
            ON public.assessments
            FOR INSERT
            WITH CHECK (faculty_id = auth.uid());

        CREATE POLICY "Faculty can update their own assignments"
            ON public.assessments
            FOR UPDATE
            USING (faculty_id = auth.uid());

        CREATE POLICY "Faculty can delete their own assignments"
            ON public.assessments
            FOR DELETE
            USING (faculty_id = auth.uid());

        -- Add RLS policies for assessment_links
        ALTER TABLE public.assessment_links ENABLE ROW LEVEL SECURITY;

        CREATE POLICY "Faculty can view links for their assignments"
            ON public.assessment_links
            FOR SELECT
            USING (
                EXISTS (
                    SELECT 1 FROM public.assessments
                    WHERE assessments.id = assessment_links.assessment_id
                    AND assessments.faculty_id = auth.uid()
                )
            );

        CREATE POLICY "Faculty can insert links for their assignments"
            ON public.assessment_links
            FOR INSERT
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM public.assessments
                    WHERE assessments.id = assessment_links.assessment_id
                    AND assessments.faculty_id = auth.uid()
                )
            );

        -- Add RLS policies for assignment_submissions
        ALTER TABLE public.assignment_submissions ENABLE ROW LEVEL SECURITY;

        CREATE POLICY "Students can view their own submissions"
            ON public.assignment_submissions
            FOR SELECT
            USING (student_id = auth.uid());

        CREATE POLICY "Students can insert their own submissions"
            ON public.assignment_submissions
            FOR INSERT
            WITH CHECK (student_id = auth.uid());

        CREATE POLICY "Faculty can view submissions for their assignments"
            ON public.assignment_submissions
            FOR SELECT
            USING (
                EXISTS (
                    SELECT 1 FROM public.assessments
                    WHERE assessments.id = assignment_submissions.assignment_id
                    AND assessments.faculty_id = auth.uid()
                )
            );
        """
        
        # Execute the query
        response = supabase.rpc('exec_sql', {'query': create_table_query}).execute()
        print("Tables created successfully")
        return jsonify({"message": "Tables created successfully"})
    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        return jsonify({"error": f"Failed to create tables: {str(e)}"}), 500

@app.route('/student/assignments')
def student_assignments():
    try:
        # Fetch all assignments from the assessments table
        response = supabase.table('assessments').select('*').execute()
        assignments = response.data if response.data else []
        
        return render_template('student assignment.html', assignments=assignments)
    except Exception as e:
        print(f"Error fetching assignments: {str(e)}")
        return render_template('student assignment.html', error='Failed to load assignments')

@app.route('/submit_assignment', methods=['POST'])
def submit_assignment():
    try:
        data = request.json
        print("Received data:", data)  # Debug log
        
        assignment_id = data.get('assignment_id')
        link = data.get('drive_link')  # Changed from 'link' to 'drive_link'
        user_id = session.get('user_id')

        print(f"Validating fields - assignment_id: {assignment_id}, drive_link: {link}, user_id: {user_id}")  # Debug log

        # Check if any required field is missing
        missing_fields = []
        if not assignment_id:
            missing_fields.append('assignment_id')
        if not link:
            missing_fields.append('drive_link')
        if not user_id:
            missing_fields.append('user_id')

        if missing_fields:
            return jsonify({
                'error': 'Missing required fields',
                'missing_fields': missing_fields
            }), 400

        # Get user details from users table
        user_response = supabase.table('users').select('name, roll_number').eq('id', user_id).execute()
        if not user_response.data:
            return jsonify({'error': 'User not found'}), 404

        user_data = user_response.data[0]

        # Insert submission into database
        submission_data = {
            'assessment_id': assignment_id,
            'name': user_data['name'],
            'roll_number': user_data['roll_number'],
            'link': link
        }

        print("Submitting data:", submission_data)  # Debug log

        response = supabase.table('assignment_submissions').insert(submission_data).execute()
        
        if response.data:
            return jsonify({
                'message': 'Assignment submitted successfully',
                'submission_id': response.data[0]['id']
            })
        
        return jsonify({'error': 'Failed to submit assignment - no data returned from database'}), 500

    except Exception as e:
        print(f"Error submitting assignment: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Failed to submit assignment: {str(e)}'}), 500

@app.route('/add_assessment_link', methods=['POST'])
def add_assessment_link():
    try:
        data = request.json
        assessment_id = data.get('assessment_id')
        link_type = data.get('link_type')
        link_url = data.get('link_url')
        description = data.get('description')

        if not all([assessment_id, link_type, link_url]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Insert link into database
        link_data = {
            'assessment_id': assessment_id,
            'link_type': link_type,
            'link_url': link_url,
            'description': description
        }

        response = supabase.table('assessment_links').insert(link_data).execute()
        
        if response.data:
            return jsonify({'message': 'Link added successfully'})
        
        return jsonify({'error': 'Failed to add link'}), 500

    except Exception as e:
        print(f"Error adding assessment link: {str(e)}")
        return jsonify({'error': 'An error occurred while adding the link'}), 500

@app.route('/get_assessment_links/<assessment_id>')
def get_assessment_links(assessment_id):
    try:
        response = supabase.table('assessment_links')\
            .select('*')\
            .eq('assessment_id', assessment_id)\
            .execute()
        
        links = response.data if response.data else []
        return jsonify(links)
    except Exception as e:
        print(f"Error fetching assessment links: {str(e)}")
        return jsonify({'error': 'Failed to fetch links'}), 500

@app.route('/create_assignment_submissions_table')
def create_assignment_submissions_table():
    try:
        # Create table if it doesn't exist
        create_table_query = """
        -- Drop existing table if it exists
        DROP TABLE IF EXISTS public.assignment_submissions CASCADE;

        -- Create assignment_submissions table
        CREATE TABLE public.assignment_submissions (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            assessment_id UUID REFERENCES public.assessments(id),
            name TEXT NOT NULL,
            roll_number TEXT NOT NULL,
            link TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Add RLS policies
        ALTER TABLE public.assignment_submissions ENABLE ROW LEVEL SECURITY;

        CREATE POLICY "Students can view their own submissions"
            ON public.assignment_submissions
            FOR SELECT
            USING (roll_number = auth.jwt()->>'roll_number');

        CREATE POLICY "Students can insert their own submissions"
            ON public.assignment_submissions
            FOR INSERT
            WITH CHECK (roll_number = auth.jwt()->>'roll_number');

        CREATE POLICY "Faculty can view all submissions"
            ON public.assignment_submissions
            FOR SELECT
            USING (auth.role() = 'faculty');
        """
        
        # Execute the query
        response = supabase.rpc('exec_sql', {'query': create_table_query}).execute()
        print("Assignment submissions table created successfully")
        return jsonify({"message": "Assignment submissions table created successfully"})
    except Exception as e:
        print(f"Error creating table: {str(e)}")
        return jsonify({"error": f"Failed to create table: {str(e)}"}), 500

@app.route('/get_assignment_submissions/<assignment_id>')
def get_assignment_submissions(assignment_id):
    try:
        # Fetch submissions for the given assignment
        response = supabase.table('assignment_submissions')\
            .select('*')\
            .eq('assessment_id', assignment_id)\
            .execute()
        
        submissions = response.data if response.data else []
        
        return jsonify({
            'submissions': submissions
        })
    except Exception as e:
        print(f"Error fetching submissions: {str(e)}")
        return jsonify({'error': 'Failed to fetch submissions'}), 500

@app.route('/get_faculty_assignments')
def get_faculty_assignments():
    try:
        faculty_id = session.get('faculty_id')
        if not faculty_id:
            return jsonify({'error': 'Unauthorized'}), 401

        # Fetch assignments for the current faculty
        response = supabase.table('assessments')\
            .select('*')\
            .eq('faculty_id', faculty_id)\
            .order('created_at', desc=True)\
            .execute()
        
        assignments = response.data if response.data else []
        
        return jsonify({
            'assignments': assignments
        })
    except Exception as e:
        print(f"Error fetching assignments: {str(e)}")
        return jsonify({'error': 'Failed to fetch assignments'}), 500

@app.route('/add_faculty', methods=['POST'])
@admin_required
def add_faculty():
    try:
        data = request.get_json()
        print("Received data:", data)  # Debug log
        
        # Validate required fields
        required_fields = ['name', 'email', 'password', 'roll_number', 'branch', 'subject', 'sections']
        for field in required_fields:
            if not data.get(field):
                print(f"Missing required field: {field}")  # Debug log
                return jsonify({'success': False, 'message': f'Missing required field: {field}'}), 400

        # Check if email already exists
        existing_user = supabase.table('users').select('id').eq('email', data['email']).execute()
        print("Existing user check:", existing_user.data)  # Debug log
        if existing_user.data:
            return jsonify({'success': False, 'message': 'Email already exists'}), 400

        # Hash the password
        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        print("Password hashed successfully")  # Debug log

        # Prepare faculty data
        faculty_data = {
            'name': data['name'],
            'email': data['email'],
            'password': hashed_password,
            'roll_number': data['roll_number'],
            'branch': data['branch'],
            'subject': data['subject'],
            'role': 'faculty'
        }
        print("Prepared faculty data:", faculty_data)  # Debug log

        # Insert faculty into users table
        response = supabase.table('users').insert(faculty_data).execute()
        print("Database response:", response.data)  # Debug log
        
        if not response.data:
            print("Failed to insert faculty data")  # Debug log
            return jsonify({'success': False, 'message': 'Failed to add faculty'}), 500

        # Add faculty sections
        faculty_id = response.data[0]['id']
        sections = [section.strip() for section in data['sections'].split(',')]
        
        for section in sections:
            section_data = {
                'faculty_id': faculty_id,
                'section': section
            }
            supabase.table('faculty_sections').insert(section_data).execute()

        return jsonify({'success': True, 'message': 'Faculty added successfully'})
    except Exception as e:
        print(f"Error adding faculty: {e}")  # Debug log
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to add faculty'}), 500

@app.route('/add_student', methods=['POST'])
@admin_required
def add_student():
    try:
        data = request.get_json()
        print("Received data:", data)  # Debug log
        
        # Validate required fields
        required_fields = ['name', 'email', 'password', 'roll_number', 'branch', 'section', 'semester']
        for field in required_fields:
            if not data.get(field):
                print(f"Missing required field: {field}")  # Debug log
                return jsonify({'success': False, 'message': f'Missing required field: {field}'}), 400

        # Check if email already exists
        existing_user = supabase.table('users').select('id').eq('email', data['email']).execute()
        print("Existing user check:", existing_user.data)  # Debug log
        if existing_user.data:
            return jsonify({'success': False, 'message': 'Email already exists'}), 400

        # Hash the password
        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        print("Password hashed successfully")  # Debug log

        # Prepare student data
        student_data = {
            'name': data['name'],
            'email': data['email'],
            'password': hashed_password,
            'roll_number': data['roll_number'],
            'branch': data['branch'],
            'section': data['section'],
            'semester': data['semester'],
            'role': 'student'
        }
        print("Prepared student data:", student_data)  # Debug log

        # Insert student into users table
        response = supabase.table('users').insert(student_data).execute()
        print("Database response:", response.data)  # Debug log
        
        if not response.data:
            print("Failed to insert student data")  # Debug log
            return jsonify({'success': False, 'message': 'Failed to add student'}), 500

        # Initialize attendance record
        attendance_data = {
            'student_id': response.data[0]['id'],
            'section': data['section'],
            'attended_classes': 0,
            'total_classes': 0
        }
        print("Initializing attendance record:", attendance_data)  # Debug log
        supabase.table('attendance').insert(attendance_data).execute()

        return jsonify({'success': True, 'message': 'Student added successfully'})
    except Exception as e:
        print(f"Error adding student: {e}")  # Debug log
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to add student'}), 500

@app.route('/edit_student/<int:student_id>', methods=['PUT'])
@admin_required
def edit_student(student_id):
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'roll_number', 'branch', 'section', 'semester']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'Missing required field: {field}'}), 400

        # Check if email already exists for another student
        existing_user = supabase.table('users')\
            .select('id')\
            .eq('email', data['email'])\
            .neq('id', student_id)\
            .execute()
        if existing_user.data:
            return jsonify({'success': False, 'message': 'Email already exists'}), 400

        # Prepare student data
        student_data = {
            'name': data['name'],
            'email': data['email'],
            'roll_number': data['roll_number'],
            'branch': data['branch'],
            'section': data['section'],
            'semester': data['semester']
        }

        # Update student in users table
        response = supabase.table('users')\
            .update(student_data)\
            .eq('id', student_id)\
            .execute()
        
        if not response.data:
            return jsonify({'success': False, 'message': 'Failed to update student'}), 500

        return jsonify({'success': True, 'message': 'Student updated successfully'})
    except Exception as e:
        print(f"Error updating student: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to update student'}), 500

@app.route('/delete_student/<int:student_id>', methods=['DELETE'])
@admin_required
def delete_student(student_id):
    try:
        # Delete student's attendance records
        supabase.table('attendance')\
            .delete()\
            .eq('student_id', student_id)\
            .execute()

        # Delete student from users table
        response = supabase.table('users')\
            .delete()\
            .eq('id', student_id)\
            .execute()
        
        if not response.data:
            return jsonify({'success': False, 'message': 'Failed to delete student'}), 500

        return jsonify({'success': True, 'message': 'Student deleted successfully'})
    except Exception as e:
        print(f"Error deleting student: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to delete student'}), 500



# Instead of directly hardcoding the key, use a more secure method
COHERE_API_KEY = os.environ.get('COHERE_API_KEY', 'tF4ybICjnFpt29D5IiFOIoDlLnRxj3M0VxdbY755')

# Safely initialize Cohere client
co = None
try:
    if cohere and COHERE_API_KEY:
        co = cohere.Client(COHERE_API_KEY)
except Exception as e:
    print(f"Failed to initialize Cohere client: {e}")
@app.route('/job_match_recommender')
def job_match_recommender():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    return render_template('job match recommender.html')
@app.route('/code-review')
def code_review():
    return render_template('code_review.html')


@app.route('/api/review', methods=['POST'])
def review_code_api():
    code = request.form['code']
    language = request.form['language']

    prompt = f"""
You are an expert code reviewer.

Evaluate the following {language} code and provide a detailed review. Include:

1. A score out of 100, considering:
   - Time complexity
   - Space complexity
   - Readability
   - Maintainability
   - Code structure and style
   - Error handling and edge cases

2. Comments on strengths and weaknesses.

3. Specific suggestions for improvement.

Format your response like this:
- **Score**: XX/100
- **Time Complexity**: 
- **Readability**: 
- **Maintainability**: 
- **Error Handling**: 
- **Suggestions**: 
- **Overall Feedback**: 

Here is the code to review:
```{language}
{code}
```
"""

    try:
        response = co.generate(
            model='command-r-plus',
            prompt=prompt,
            max_tokens=300,
            temperature=0.7
        )

        feedback = response.generations[0].text
        return jsonify({'feedback': feedback})

    except Exception as e:
        return jsonify({'error': str(e)})
@app.route('/job_match_recomender', methods=['GET'])
def job_match_recomender1():
    return render_template('job_match_recomender.html')

@app.route('/recommend', methods=['POST'])
def recommend_jobs():
    skills_input = request.form['skills']

    prompt = f"""
    You are an expert career advisor.

    A user has the following skills:
    {skills_input}

    1. Recommend 3–5 job roles that match these skills.
    2. Identify the major skills the user is missing for better job opportunities.
    3. Suggest a personalized learning path to develop those missing skills.

    Format:
    - Matching Jobs: 
    - Missing Skills:
    - Suggested Skills to Learn:
    """

    try:
        response = co.generate(
            model='command-r-plus',
            prompt=prompt,
            max_tokens=400,
            temperature=0.7
        )
        recommendation = response.generations[0].text
    except Exception as e:
        recommendation = f"Error: {str(e)}"

    return render_template('job_match_recomender.html', recommendation=recommendation)
@app.route('/ai_code_assistant')
def ai_code_assistant():
    return render_template('ai_code_assistant.html')

@app.route('/solve', methods=['POST'])
def solve_code_problem():
    question = request.form['question']

    prompt = f"""
    You are a helpful coding assistant.

    A student has the following coding question:
    "{question}"

    Please:
    1. Solve the problem with clean, well-commented code (in Python).
    2. Explain the code step-by-step in simple terms.
    3. Mention any alternatives or improvements if applicable.

    Format:
    - Code:
    - Explanation:
    """

    try:
        response = co.generate(
            model='command-r-plus',
            prompt=prompt,
            max_tokens=500,
            temperature=0.7
        )
        result = response.generations[0].text
    except Exception as e:
        result = f"Error: {str(e)}"

    return render_template('ai_code_assistant.html', result=result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

