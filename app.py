from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import requests
import time
from supabase import create_client, Client
import bcrypt
import traceback

app = Flask(__name__)
app.secret_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkdm1nenF2cXp1YWVndnFrYXhkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NDM1MjYxNSwiZXhwIjoyMDU5OTI4NjE1fQ.qeufhcj6ypy97jOu0BHIRfqTnz9ZJNHoktibYy_p2NY'  # Ensure a proper secret key is set

# Initialize Supabase client
SUPABASE_URL = 'https://vdvmgzqvqzuaegvqkaxd.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkdm1nenF2cXp1YWVndnFrYXhkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNTI2MTUsImV4cCI6MjA1OTkyODYxNX0.uN8oZhbR1ujwwNpUDULigx5wJQ8XVM5DNxYXDOTvlTU'
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

JUDGE0_API_URL = 'https://judge0-ce.p.rapidapi.com/submissions'
JUDGE0_API_HEADERS = {
    'x-rapidapi-host': 'judge0-ce.p.rapidapi.com',
    'x-rapidapi-key': '4be4a0b098msha12e9d5e92eda12p12960ejsn03f80d153530',  # Replace with your actual RapidAPI key
    'content-type': 'application/json'
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

    # Map language to Judge0 language_id
    language_map = {
        'python': 71,
        'javascript': 63,
        'java': 62,
        'c': 50,
        'cpp': 54
    }
    language_id = language_map.get(language)

    if not language_id:
        return jsonify({'error': 'Unsupported language'}), 400

    # Prepare the payload for Judge0 API
    payload = {
        'source_code': code,
        'language_id': language_id,
        'stdin': input_data
    }

    try:
        # Send the request to Judge0 API
        response = requests.post(JUDGE0_API_URL, headers=JUDGE0_API_HEADERS, json=payload)
        response.raise_for_status()  # Raise an error for bad responses
        token = response.json().get('token')
        print("Judge0 API Token:", token)  # Log the token

        # Poll for the result
        result_url = f"{JUDGE0_API_URL}/{token}"
        while True:
            result_response = requests.get(result_url, headers=JUDGE0_API_HEADERS)
            result_response.raise_for_status()
            result = result_response.json()
            if result.get('status', {}).get('id') in [1, 2]:  # In Queue or Processing
                time.sleep(1)  # Wait before polling again
            else:
                break

        # Return the result
        return jsonify({
            'stdout': result.get('stdout'),
            'stderr': result.get('stderr'),
            'status': result.get('status', {}).get('description')
        })
    except requests.exceptions.RequestException as e:
        print("Error during API request:", e)
        return jsonify({'error': 'Failed to execute code'}), 500

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
    return render_template('faculty_attendance.html')
@app.route('/attendance')

def attendance():
    return render_template('student attendance.html')
@app.route('/coding_tracks')

def coding_tracks():
    return render_template('coding tracksss.html')

@app.route('/c_plus_plus')

def c_plus_plus():
    return render_template('c++languagee.html')
@app.route('/python')

def python():
    return render_template('python.html')

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

if __name__ == '__main__':
    app.run(debug=True)
