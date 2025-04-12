from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import requests
import time
from supabase import create_client, Client
import bcrypt
import traceback
from datetime import datetime, timedelta

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
        # Fetch user details
        response = supabase.table('users').select('*').eq('id', user_id).execute()
        user = response.data[0] if response.data else None

        if not user:
            return render_template('dashboard.html', error='User not found')

        print(f"User role: {user['role']}")  # Log the user's role
        if user['role'] == 'faculty':
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['faculty_id'] = user['id']  # Set faculty_id in session
            print("Redirecting to faculty dashboard")  # Log redirection to faculty dashboard
            return redirect(url_for('faculty_home'))
        else:
            # Render the dashboard directly instead of redirecting
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
            # Fetch user by email
            response = supabase.table('users').select('*').eq('email', email).execute()
            user = response.data[0] if response.data else None

            if user:
                # Verify password
                if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                    session['user_id'] = user['id']
                    session['role'] = user['role']  # Store the user's role in the session
                    if user['role'] == 'faculty':
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
            return render_template('login.html', error='An error occurred')

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
<<<<<<< HEAD

=======
>>>>>>> b79b957974697617b7b7b872060054814d0f8d31

@app.route('/attendance')
def attendance():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    try:
        # Get user's section
        user_response = supabase.table('users').select('section').eq('id', user_id).execute()
        user_data = user_response.data[0] if user_response.data else None
        
        if not user_data:
            return render_template('student attendance.html', error='User not found')

        section = user_data['section']

        # Get current week's Monday to Friday dates
        today = datetime.now()
        current_weekday = today.weekday()  # Monday is 0, Sunday is 6
        monday = today - timedelta(days=current_weekday)
        friday = monday + timedelta(days=4)
        
        # Format dates for display
        week_dates = {
            'Monday': monday.strftime('%Y-%m-%d'),
            'Tuesday': (monday + timedelta(days=1)).strftime('%Y-%m-%d'),
            'Wednesday': (monday + timedelta(days=2)).strftime('%Y-%m-%d'),
            'Thursday': (monday + timedelta(days=3)).strftime('%Y-%m-%d'),
            'Friday': friday.strftime('%Y-%m-%d')
        }

        # Get attendance data for the current week
        response = supabase.table('attendance')\
            .select('*')\
            .eq('student_id', user_id)\
            .eq('section', section)\
            .gte('date', monday.strftime('%Y-%m-%d'))\
            .lte('date', friday.strftime('%Y-%m-%d'))\
            .execute()
        
        week_attendance = response.data if response.data else []

        # Calculate overall attendance
        total_response = supabase.table('attendance')\
            .select('total_classes, attended_classes')\
            .eq('student_id', user_id)\
            .eq('section', section)\
            .execute()
        
        total_data = total_response.data[0] if total_response.data else None
        overall_attendance = {
            'total_classes': total_data['total_classes'] if total_data else 0,
            'attended_classes': total_data['attended_classes'] if total_data else 0,
            'percentage': round((total_data['attended_classes'] / total_data['total_classes'] * 100) if total_data and total_data['total_classes'] > 0 else 0, 2)
        }

        return render_template('student attendance.html', 
                            week_dates=week_dates,
                            week_attendance=week_attendance,
                            overall_attendance=overall_attendance)
    except Exception as e:
        print(f"Error fetching attendance: {e}")
        traceback.print_exc()
        return render_template('student attendance.html', error='An error occurred')

@app.route('/coding_tracks')
def coding_tracks():
    return render_template('coding tracksss.html')

@app.route('/c_plus_plus')
def c_plus_plus():
    return render_template('c++languagee.html')

@app.route('/python')
def python():
    return render_template('python.html')

<<<<<<< HEAD
@app.route('/faculty/assignments')
def faculty_assignments():
    return render_template('faculty assignments.html')


=======
>>>>>>> b79b957974697617b7b7b872060054814d0f8d31
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

if __name__ == '__main__':
    app.run(debug=True)
