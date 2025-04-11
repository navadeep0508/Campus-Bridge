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
    return render_template('dashboard.html')

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
                     # Store the user's role in the session
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
    return render_template('compiler.html')

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

@app.route('/myinstitution')
def my_institution():
    return render_template('myinstution.html', section='institution')

@app.route('/regulations')
def regulations():
    return render_template('myinstution.html', section='regulations')

if __name__ == '__main__':
    app.run(debug=True)
