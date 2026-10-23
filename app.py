from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import requests
import os
from dotenv import load_dotenv
load_dotenv()
import time
import bcrypt
from functools import wraps
import json
import threading
from collections import defaultdict
from datetime import datetime as dt, timezone
from urllib.parse import urlsplit
from db import supabase, init_db, _get_connection, USING_SUPABASE

# Explicitly import Cohere to handle potential import issues
try:
    import cohere
except ImportError:
    cohere = None

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(32)
app.config.update(
    MAX_CONTENT_LENGTH=1_000_000,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '').lower() in {'1', 'true', 'yes'},
)

LANGUAGE_IDS = {'python': 71, 'javascript': 63, 'java': 62, 'c': 50, 'cpp': 54, 'c++': 54}
EXECUTION_INTERVAL = 1.0
_execution_lock = threading.Lock()
_last_execution_by_client = defaultdict(float)
_login_attempts = defaultdict(list)

ROLE_ACCESS = {
    'change_password': {'student', 'faculty', 'admin'},
    'update_password': {'student', 'faculty', 'admin'},
    'mycourse': {'student'}, 'compiler': {'student'}, 'run_code': {'student'},
    'coding_tracks': {'student'}, 'c_plus_plus': {'student'}, 'python': {'student'},
    'timetable': {'student'}, 'myverse': {'student'}, 'get_problem': {'student'},
    'submit_solution': {'student'}, 'c': {'student'}, 'java': {'student'},
    'assignment': {'student'}, 'institution': {'student'}, 'attendance': {'student'},
    'student_coding_assesment': {'student'}, 'submit_assessment': {'student'},
    'student_assignments': {'student'}, 'submit_assignment': {'student'},
    'job_match_recommender': {'student'}, 'job_match_recomender1': {'student'},
    'student_leaderboard': {'student'}, 'code_review': {'student'},
    'review_code_api': {'student'}, 'ai_code_assistant': {'student'}, 'solve_code_problem': {'student'}, 'recommend_jobs': {'student'},
    'faculty_home': {'faculty'}, 'faculty_attendance': {'faculty'},
    'timetable_faculty': {'faculty'}, 'delete_timetable_entry': {'faculty'}, 'faculty_assignments': {'faculty'},
    'faculty_coding_assessment': {'faculty'}, 'get_sections': {'faculty'},
    'get_students': {'faculty'}, 'mark_attendance': {'faculty'}, 'get_courses': {'faculty'},
    'get_faculty_assignments': {'faculty'}, 'faculty_chat': {'faculty'},
    'create_faculty_chat_room': {'faculty'},
    'test_db': {'admin'}, 'create_assessments_table': {'admin'},
    'create_assignment_submissions_table': {'admin'},
    'faculty_admin': {'admin'}, 'students_admin': {'admin'}, 'dashboard_admin': {'admin'},
    'add_faculty': {'admin'}, 'add_student': {'admin'}, 'edit_student': {'admin'}, 'delete_student': {'admin'},
    'get_assignment_submissions': {'faculty', 'admin'},
    'get_assessment_links': {'student', 'faculty', 'admin'},
    'add_assessment_link': {'faculty'},
    'code_room': {'student', 'faculty'}, 'create_code_room': {'student', 'faculty'},
    'join_code_room': {'student', 'faculty'}, 'update_code': {'student', 'faculty'},
    'leave_code_room': {'student', 'faculty'}, 'get_room_messages': {'student', 'faculty'},
    'send_code_room_message': {'student', 'faculty'}, 'code_room_page': {'student', 'faculty'},
    'chat_page': {'student', 'faculty'}, 'create_chat_room': {'student', 'faculty'},
    'send_chat_message': {'student', 'faculty'}, 'get_users': {'student', 'faculty'},
    'get_current_user_id': {'student', 'faculty', 'admin'},
    'get_chat_messages': {'student', 'faculty'},
}

# Initialize local SQLite database (replaces Supabase)
init_db()


@app.before_request
def enforce_role_access():
    """Use the persisted role for protected routes instead of trusting cookie fields."""
    allowed_roles = ROLE_ACCESS.get(request.endpoint)
    if not allowed_roles:
        return None

    user_id = session.get('user_id')
    if not user_id:
        if request.is_json or request.path.startswith(('/api/', '/get_', '/send_', '/create_', '/submit_', '/mark_', '/update_')):
            return jsonify({'error': 'Authentication required'}), 401
        return redirect(url_for('login'))

    try:
        result = supabase.table('users').select('id', 'role').eq('id', user_id).limit(1).execute()
        user = result.data[0] if result.data else None
    except Exception:
        app.logger.exception('Could not verify the current account')
        return jsonify({'error': 'Unable to verify your account'}), 503

    if not user:
        session.clear()
        return jsonify({'error': 'Authentication required'}), 401

    role = user.get('role')
    if role not in allowed_roles:
        if request.is_json or request.path.startswith(('/api/', '/get_', '/send_', '/create_', '/submit_', '/mark_', '/update_')):
            return jsonify({'error': 'You do not have access to this action'}), 403
        return redirect(url_for('home_page'))

    session['role'] = role
    if role == 'faculty':
        session['faculty_id'] = user['id']
    else:
        session.pop('faculty_id', None)
    return None


@app.before_request
def reject_cross_origin_writes():
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return None
    origin = request.headers.get('Origin') or request.headers.get('Referer')
    if origin:
        parsed = urlsplit(origin)
        if parsed.netloc and parsed.netloc.casefold() != request.host.casefold():
            return jsonify({'error': 'Cross-origin request rejected'}), 403
    return None


@app.after_request
def add_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    if request.is_secure:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    # Let the shared legacy-navigation adapter choose the correct role menu on
    # older standalone templates that predate the common Jinja app layout.
    if response.mimetype == 'text/html' and not response.direct_passthrough:
        role = session.get('role')
        if role in {'student', 'faculty', 'admin'}:
            html = response.get_data(as_text=True)
            body_start = html.find('<body')
            body_end = html.find('>', body_start) if body_start >= 0 else -1
            if body_end >= 0 and 'data-user-role=' not in html[body_start:body_end]:
                html = html[:body_end] + f' data-user-role="{role}"' + html[body_end:]
                response.set_data(html)
    return response


@app.context_processor
def expose_active_navigation():
    endpoint_groups = {
        'dashboard': {'home_page', 'faculty_home', 'dashboard_admin'},
        'courses': {'mycourse'},
        'institution': {'institution'},
        'chat': {'chat_page', 'faculty_chat'},
        'attendance': {'attendance', 'faculty_attendance'},
        'assignments': {'student_assignments', 'faculty_assignments'},
        'timetable': {'timetable', 'timetable_faculty'},
        'tracks': {'coding_tracks', 'c_plus_plus', 'python', 'c', 'java'},
        'myverse': {'myverse', 'get_problem', 'submit_solution'},
        'compiler': {'compiler', 'run_code'},
        'coding_assessments': {'student_coding_assesment', 'submit_assessment'},
        'coding': {'faculty_coding_assessment'},
        'code_room': {'code_room', 'create_code_room', 'join_code_room', 'update_code', 'leave_code_room', 'get_room_messages', 'send_code_room_message', 'code_room_page'},
        'ai_assistant': {'ai_code_assistant', 'solve_code_problem'},
        'code_review': {'code_review', 'review_code_api'},
        'jobs': {'job_match_recomender1', 'job_match_recommender', 'recommend_jobs'},
        'leaderboard': {'student_leaderboard'},
        'faculty': {'faculty_admin'},
        'students': {'students_admin'},
    }
    endpoint = request.endpoint or ''
    active_nav = next((key for key, endpoints in endpoint_groups.items() if endpoint in endpoints), '')
    return {'active_nav': active_nav}

JUDGE0_API_URL = 'https://judge0-ce.p.rapidapi.com/submissions'
JUDGE0_API_HEADERS = {
    'x-rapidapi-host': 'judge0-ce.p.rapidapi.com',
    'x-rapidapi-key': os.environ.get('JUDGE0_API_KEY', ''),
    'content-type': 'application/json',
    'accept': 'application/json'
}

# Sample coding problems data (replace with database later)
CODING_PROBLEMS = {
    1: {
        'id': 1,
        'title': 'Two Sum',
        'description': 'Read a JSON integer array on the first line and a target integer on the second. Print the two matching indices as a JSON array.',
        'difficulty': 'easy',
        'points': 100,
        'test_cases': [
            {'input': '[2,7,11,15]\n9\n', 'output': '[0,1]'},
            {'input': '[3,2,4]\n6\n', 'output': '[1,2]'},
            {'input': '[3,3]\n6\n', 'output': '[0,1]'}
        ]
    },
    2: {
        'id': 2,
        'title': 'Merge Sort Implementation',
        'description': 'Read a JSON integer array from standard input and print the sorted array as JSON.',
        'difficulty': 'medium',
        'points': 200,
        'test_cases': [
            {'input': '[64,34,25,12,22,11,90]\n', 'output': '[11,12,22,25,34,64,90]'},
            {'input': '[5,2,8,1,9]\n', 'output': '[1,2,5,8,9]'},
            {'input': '[38,27,43,3,9,82,10]\n', 'output': '[3,9,10,27,38,43,82]'}
        ]
    },
    3: {
        'id': 3,
        'title': 'Longest Common Subsequence',
        'description': 'Read two strings, one per line, and print the length of their longest common subsequence.',
        'difficulty': 'hard',
        'points': 300,
        'test_cases': [
            {'input': 'abcde\nace\n', 'output': '3'},
            {'input': 'abc\nabc\n', 'output': '3'},
            {'input': 'abc\ndef\n', 'output': '0'}
        ]
    }
}

# Initialize the code review bot

# Initialize the job match bot


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))
        try:
            user = supabase.table('users').select('role').eq('id', user_id).limit(1).execute().data
        except Exception:
            app.logger.exception('Admin authorization check failed')
            return jsonify({'error': 'Unable to verify your account'}), 503
        if not user or user[0].get('role') != 'admin':
            return redirect(url_for('home_page'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('landing_redesign.html')

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

        semester = str(user_data.get('semester') or '')
        if semester not in {str(number) for number in range(1, 9)}:
            return render_template('mycourse.html', courses=[], error='Your semester is not configured yet')
        table_name = f'semester{semester}'

        # Fetch courses for the user's semester
        courses_response = supabase.table(table_name).select('*').execute()
        courses = courses_response.data if courses_response.data else []

        return render_template('mycourse.html', courses=courses)
    except Exception as e:
        app.logger.exception('Request processing failed')
        return render_template('mycourse.html', error='An error occurred')

@app.route('/home')
def home_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    try:
        # Fetch user details
        response = supabase.table('users').select('id', 'name', 'role', 'points', 'semester', 'branch', 'section').eq('id', user_id).limit(1).execute()
        user = response.data[0] if response.data else None

        if not user:
            return render_template('dashboard_redesign.html', error='User not found')

        if user['role'] == 'faculty':
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['faculty_id'] = user['id']  # Set faculty_id in session
            return redirect(url_for('faculty_home'))
        elif user['role'] == 'admin':
            session['role'] = 'admin'
            return redirect(url_for('dashboard_admin'))
        else:
            # Render the dashboard directly instead of redirecting
            return render_template('dashboard_redesign.html', user=user)
    except Exception as e:
        app.logger.exception('Request processing failed')
        return render_template('dashboard_redesign.html', error='An error occurred')

@app.route('/login', methods=['GET', 'POST'])
def login():
    demo_credentials_enabled = (
        os.environ.get('VERCEL') == '1'
        and os.environ.get('SEED_DEMO_DATA', '').strip().lower() in {'1', 'true', 'yes'}
    )
    if request.method == 'POST':
        now = time.monotonic()
        address = request.remote_addr or 'unknown'
        with _execution_lock:
            attempts = [stamp for stamp in _login_attempts[address] if now - stamp < 300]
            _login_attempts[address] = attempts
            if len(attempts) >= 10:
                return render_template('login_redesign.html', error='Too many sign-in attempts. Wait a few minutes and try again.', demo_credentials_enabled=demo_credentials_enabled), 429
        email = request.form.get('email', '').strip().casefold()
        password = request.form.get('password', '')
        if not email or len(email) > 254 or not password or len(password.encode('utf-8')) > 72:
            return render_template('login_redesign.html', error='Invalid credentials', demo_credentials_enabled=demo_credentials_enabled)

        try:
            # Fetch user by email
            response = supabase.table('users').select('*').eq('email', email).execute()
            user = response.data[0] if response.data else None

            if user:
                # Verify password
                if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                    session.clear()
                    with _execution_lock:
                        _login_attempts.pop(address, None)
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
                    with _execution_lock:
                        _login_attempts[address].append(now)
                    return render_template('login_redesign.html', error='Invalid credentials', demo_credentials_enabled=demo_credentials_enabled)
            else:
                with _execution_lock:
                    _login_attempts[address].append(now)
                    return render_template('login_redesign.html', error='Invalid credentials', demo_credentials_enabled=demo_credentials_enabled)
        except Exception as e:
            app.logger.exception('Request processing failed')
            return render_template('login_redesign.html', error='An error occurred', demo_credentials_enabled=demo_credentials_enabled)

    return render_template('login_redesign.html', demo_credentials_enabled=demo_credentials_enabled)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/compiler')
def compiler():
    problem_id = request.args.get('problem_id', type=int)
    problem = CODING_PROBLEMS.get(problem_id) if problem_id else None
    return render_template('compiler.html', problem=problem)

def _execution_rate_limit():
    now = time.monotonic()
    client_key = str(session.get('user_id') or request.remote_addr or 'anonymous')
    with _execution_lock:
        previous = _last_execution_by_client[client_key]
        if now - previous < EXECUTION_INTERVAL:
            return jsonify({'error': 'Please wait a moment before another code submission.'}), 429
        _last_execution_by_client[client_key] = now
        if len(_last_execution_by_client) > 10000:
            cutoff = now - 60
            for key, timestamp in list(_last_execution_by_client.items()):
                if timestamp < cutoff:
                    _last_execution_by_client.pop(key, None)
    return None


def _award_points_once(table_name, id_column, source_id, user_id, points):
    """Atomically record a unique solve before awarding its points."""
    now = dt.now(timezone.utc).isoformat()
    points = max(0, int(points or 0))
    if USING_SUPABASE:
        if table_name == 'problem_solutions':
            rpc = supabase.rpc('award_problem_points', {'p_user_id': user_id, 'p_problem_id': source_id, 'p_points': points}).execute()
        else:
            rpc = supabase.rpc('award_assessment_points', {'p_user_id': user_id, 'p_assessment_id': source_id, 'p_points': points}).execute()
        awarded = bool(rpc.data)
        return (points, False) if awarded else (0, True)

    conn = _get_connection()
    try:
        cursor = conn.execute(f'INSERT OR IGNORE INTO {table_name} (user_id, {id_column}, solved_at) VALUES (?, ?, ?)', (user_id, source_id, now))
        if not cursor.rowcount:
            return 0, True
        conn.execute('UPDATE users SET points = COALESCE(points, 0) + ? WHERE id = ?', (points, user_id))
        conn.commit()
        return points, False
    finally:
        conn.close()

@app.route('/run', methods=['POST'])
def run_code():
    throttled = _execution_rate_limit()
    if throttled:
        return throttled

    if not JUDGE0_API_HEADERS['x-rapidapi-key']:
        return jsonify({'error': 'Code execution is not configured. Set JUDGE0_API_KEY on the server.'}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Expected a JSON object.'}), 400

    code = data.get('code')
    language = data.get('language')
    input_data = data.get('input', '')
    if not isinstance(code, str) or not isinstance(language, str):
        return jsonify({'error': 'Code and language are required.'}), 400
    if len(code) > 50000 or not isinstance(input_data, str) or len(input_data) > 10000:
        return jsonify({'error': 'Code or input exceeds the allowed size.'}), 413

    language_id = LANGUAGE_IDS.get(language.strip().lower())
    if not language_id:
        return jsonify({'error': 'Unsupported language.'}), 400

    payload = {
        'source_code': code,
        'language_id': language_id,
        'stdin': input_data,
        'base64_encoded': False
    }

    try:
        response = requests.post(JUDGE0_API_URL, headers=JUDGE0_API_HEADERS, json=payload, timeout=12)
        response.raise_for_status()
        token = response.json().get('token')
        if not token:
            return jsonify({'error': 'The execution service did not return a submission token.'}), 502

        result_url = f"{JUDGE0_API_URL}/{token}"
        deadline = time.monotonic() + 18
        result = {}
        while time.monotonic() < deadline:
            result_response = requests.get(result_url, headers=JUDGE0_API_HEADERS, timeout=8)
            result_response.raise_for_status()
            result = result_response.json()
            if result.get('status', {}).get('id') not in (1, 2):
                break
            time.sleep(0.5)
        else:
            return jsonify({'error': 'Execution timed out. Try a smaller program.'}), 504

        return jsonify({
            'stdout': result.get('stdout') or '',
            'stderr': result.get('stderr') or '',
            'status': result.get('status', {}).get('description', 'Unknown'),
            'time': result.get('time') or '',
            'memory': result.get('memory') or ''
        })
    except requests.exceptions.Timeout:
        return jsonify({'error': 'The execution service timed out. Please try again.'}), 504
    except requests.exceptions.RequestException:
        app.logger.exception('Judge0 request failed')
        return jsonify({'error': 'Could not reach the code execution service.'}), 502
    except (ValueError, TypeError):
        app.logger.exception('Invalid response from Judge0')
        return jsonify({'error': 'The execution service returned an invalid response.'}), 502

@app.route('/test-db')
def test_db():
    try:
        response = supabase.table('users').select('id').limit(1).execute()
        return jsonify({"success": "SQLite connection is working", "user_count": supabase.table('users').select('count').execute().data[0]['count']}), 200
    except Exception:
        app.logger.exception("Database health check failed")
        return jsonify({"error": "Database health check failed"}), 500

@app.route('/update_password', methods=['POST'])
def update_password():
    user_id = session.get('user_id')
    old_password = request.form.get('old-password', '')
    new_password = request.form.get('new-password', '')
    confirm_password = request.form.get('confirm-password', '')
    if not user_id:
        return redirect(url_for('login'))
    if not 12 <= len(new_password.encode('utf-8')) <= 72:
        return render_template('confirm_password.html', error='Use a password between 12 and 72 bytes')
    if new_password != confirm_password:
        return render_template('confirm_password.html', error='New passwords do not match')
    try:
        response = supabase.table('users').select('password').eq('id', user_id).limit(1).execute()
        user = response.data[0] if response.data else None
        if not user or not bcrypt.checkpw(old_password.encode('utf-8'), user['password'].encode('utf-8')):
            return render_template('confirm_password.html', error='Current password is incorrect')
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        supabase.table('users').update({'password': hashed}).eq('id', user_id).execute()
        session.clear()
        return redirect(url_for('login'))
    except Exception:
        app.logger.exception('Password update failed')
        return render_template('confirm_password.html', error='Unable to update password right now')

@app.route('/change_password')
def change_password():
    return render_template('confirm_password.html')

@app.route('/faculty')
def faculty_home():
    faculty_id = session.get('faculty_id')
    if not faculty_id:
        return redirect(url_for('login'))

    try:
        response = supabase.table('users').select('name', 'roll_number', 'branch', 'subject').eq('id', faculty_id).eq('role', 'faculty').execute()
        faculty = response.data[0] if response.data else None
        if faculty:
            return render_template('faculty_dashboard_redesign.html', faculty=faculty)
        else:
            return render_template('faculty_dashboard_redesign.html', error='Faculty not found')
    except Exception as e:
        app.logger.exception('Request processing failed')
        return render_template('faculty_dashboard_redesign.html', error='An error occurred')

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
        app.logger.exception('Request processing failed')
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

@app.route('/timetable/faculty', methods=['GET', 'POST'])
def timetable_faculty():
    faculty_id = session.get('faculty_id')
    if not faculty_id:
        return redirect(url_for('login'))

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

    def view_data():
        sections_response = supabase.table('faculty_sections').select('section').eq('faculty_id', faculty_id).execute()
        sections = list(dict.fromkeys(row.get('section', '').strip() for row in (sections_response.data or []) if row.get('section')))
        entries_response = supabase.table('timetable_entries').select('*').eq('faculty_id', faculty_id).execute()
        day_order = {day: index for index, day in enumerate(days)}
        entries = sorted(entries_response.data or [], key=lambda item: (day_order.get(item.get('day_of_week'), 7), item.get('starts_at', '')))
        return entries, sections

    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        section = request.form.get('section', '').strip()
        day = request.form.get('day_of_week', '')
        room = request.form.get('room', '').strip()
        try:
            semester = int(request.form.get('semester', ''))
            start_time = request.form.get('starts_at', '')
            end_time = request.form.get('ends_at', '')
            start_value = dt.strptime(start_time, '%H:%M')
            end_value = dt.strptime(end_time, '%H:%M')
            if not subject or len(subject) > 120 or not section or len(section) > 40:
                raise ValueError
            if semester < 1 or semester > 8 or day not in days or (room and len(room) > 80):
                raise ValueError
            if end_value <= start_value:
                raise ValueError
        except (TypeError, ValueError):
            entries, sections = view_data()
            return render_template(
                'timetable_faculty.html',
                entries=entries,
                sections=sections,
                days=days,
                error='Check the class name, section, semester, day, and time range.',
            ), 400

        try:
            entries, sections = view_data()
            if sections and section not in sections:
                return render_template(
                    'timetable_faculty.html', entries=entries, sections=sections, days=days,
                    error='Choose a section assigned to your faculty account.',
                ), 403

            scheduled = supabase.table('timetable_entries').select('*')\
                .eq('semester', semester).eq('section', section).eq('day_of_week', day).execute()
            for entry in scheduled.data or []:
                overlaps = start_time < entry['ends_at'] and end_time > entry['starts_at']
                if overlaps:
                    return render_template(
                        'timetable_faculty.html', entries=entries, sections=sections, days=days,
                        error=f'This overlaps with {entry["subject"]} ({entry["starts_at"]}–{entry["ends_at"]}).',
                    ), 409

            supabase.table('timetable_entries').insert({
                'faculty_id': faculty_id,
                'subject': subject,
                'semester': semester,
                'section': section,
                'day_of_week': day,
                'starts_at': start_time,
                'ends_at': end_time,
                'room': room or None,
                'created_at': dt.now(timezone.utc).isoformat(),
            }).execute()
            return redirect(url_for('timetable_faculty'))
        except Exception:
            app.logger.exception('Faculty timetable entry could not be saved')
            try:
                entries, sections = view_data()
            except Exception:
                entries, sections = [], []
            return render_template(
                'timetable_faculty.html', entries=entries, sections=sections, days=days,
                error='The timetable could not be saved. Check that the latest database schema is installed.',
            ), 503

    try:
        entries, sections = view_data()
        return render_template('timetable_faculty.html', entries=entries, sections=sections, days=days)
    except Exception:
        app.logger.exception('Faculty timetable could not be loaded')
        return render_template(
            'timetable_faculty.html', entries=[], sections=[], days=days,
            error='The timetable could not be loaded. Check that the latest database schema is installed.',
        ), 503


@app.route('/timetable/faculty/<int:entry_id>/delete', methods=['POST'])
def delete_timetable_entry(entry_id):
    faculty_id = session.get('faculty_id')
    if not faculty_id:
        return redirect(url_for('login'))
    try:
        supabase.table('timetable_entries').delete().eq('id', entry_id).eq('faculty_id', faculty_id).execute()
        return redirect(url_for('timetable_faculty'))
    except Exception:
        app.logger.exception('Faculty timetable entry could not be deleted')
        return redirect(url_for('timetable_faculty'))

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

            if not all([subject, year, branch, description, deadline, faculty_id]):
                missing_fields = []
                if not subject: missing_fields.append('subject')
                if not year: missing_fields.append('year')
                if not branch: missing_fields.append('branch')
                if not description: missing_fields.append('description')
                if not deadline: missing_fields.append('deadline')
                if not faculty_id: missing_fields.append('faculty_id')
                return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

            if len(subject) > 120 or len(description) > 5000 or len(branch) > 80 or len(year) > 16:
                return jsonify({'error': 'One or more assignment fields are too long'}), 400
            faculty_profile = supabase.table('users').select('branch').eq('id', faculty_id).limit(1).execute()
            if faculty_profile.data and faculty_profile.data[0].get('branch') and faculty_profile.data[0]['branch'].casefold() != branch.casefold():
                return jsonify({'error': 'Assignments can only be created for your department'}), 403

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
            
            
            response = supabase.table('assessments').insert(assessment_data).execute()
            
            
            if response.data:
                return jsonify({
                    'message': 'Assignment created successfully',
                    'assessment_id': response.data[0]['id']
                })
            
            return jsonify({'error': 'Failed to create assignment - no data returned from database'}), 500

        except Exception as e:
            app.logger.exception('Request processing failed')
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
    throttled = _execution_rate_limit()
    if throttled:
        return throttled
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Expected a JSON object'}), 400
    problem_id = data.get('problem_id')
    code = data.get('code')
    language_id = data.get('language_id')
    if not isinstance(code, str) or len(code) > 50000 or not isinstance(language_id, int) or language_id not in LANGUAGE_IDS.values():
        return jsonify({'error': 'Invalid code or language'}), 400
    try:
        problem_id = int(problem_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid problem'}), 400
    problem = CODING_PROBLEMS.get(problem_id)
    if not problem:
        return jsonify({'error': 'Problem not found'}), 404
    if not JUDGE0_API_HEADERS['x-rapidapi-key']:
        return jsonify({'error': 'Code execution is not configured'}), 503
    results = []
    try:
        for test_case in problem['test_cases']:
            payload = {'source_code': code, 'language_id': language_id, 'stdin': test_case['input'], 'base64_encoded': False}
            created = requests.post(JUDGE0_API_URL, headers=JUDGE0_API_HEADERS, json=payload, timeout=12)
            created.raise_for_status()
            token = created.json().get('token')
            if not token:
                return jsonify({'error': 'Execution service did not return a token'}), 502
            result = {}
            deadline = time.monotonic() + 18
            while time.monotonic() < deadline:
                response = requests.get(f'{JUDGE0_API_URL}/{token}', headers=JUDGE0_API_HEADERS, timeout=8)
                response.raise_for_status()
                result = response.json()
                if result.get('status', {}).get('id') not in (1, 2):
                    break
                time.sleep(.5)
            else:
                return jsonify({'error': 'Execution timed out'}), 504
            actual = (result.get('stdout') or '').strip()
            expected = test_case['output'].strip()
            results.append({'input': test_case['input'], 'expected': expected, 'actual': actual,
                            'status': result.get('status', {}).get('description', 'Unknown'), 'passed': result.get('status', {}).get('id') == 3 and actual == expected})
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Execution service timed out'}), 504
    except requests.exceptions.RequestException:
        app.logger.exception('Challenge execution request failed')
        return jsonify({'error': 'Could not reach the execution service'}), 502
    all_passed = bool(results) and all(item['passed'] for item in results)
    points_earned = 0
    already_solved = False
    if all_passed:
        points_earned, already_solved = _award_points_once('problem_solutions', 'problem_id', problem_id, session['user_id'], problem['points'])
    return jsonify({'results': results, 'all_passed': all_passed, 'points_earned': points_earned, 'already_solved': already_solved})

@app.route('/c')
def c():
    return render_template('c language.html')

@app.route('/java')
def java():
    return render_template('java programming.html')

@app.route('/assignment')
def assignment():
    return redirect(url_for('student_assignments'))

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
        app.logger.exception('Request processing failed')
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
        app.logger.exception('Request processing failed')
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
        assignments_response = supabase.table('assessments').select('subject', 'description', 'created_at').order('created_at', desc=True).limit(5).execute()
        coding_assessments_response = supabase.table('coding_assessments').select('title', 'description', 'created_at').order('created_at', desc=True).limit(5).execute()
        
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
        
        return render_template('admin_dashboard_redesign.html',
            stats={
                'total_students': students_response.data[0]['count'],
                'total_faculty': faculty_response.data[0]['count'],
                'total_courses': courses_response.data[0]['count'],
                'avg_attendance': avg_attendance
            },
            recent_activities=recent_activities
        )
    except Exception as e:
        app.logger.exception('Request processing failed')
        return render_template('admin_dashboard_redesign.html',
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
        # Fetch the user's semester and section for schedule filtering.
        response = supabase.table('users').select('semester', 'section').eq('id', user_id).execute()
        user_data = response.data[0] if response.data else None

        if not user_data:
            return render_template('timetable.html', error='User not found')

        semester = user_data.get('semester')
        section = user_data.get('section')
        entries = []
        if semester and section:
            response = supabase.table('timetable_entries').select('*')\
                .eq('semester', int(semester)).eq('section', section).execute()
            day_order = {day: index for index, day in enumerate(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'])}
            entries = sorted(response.data or [], key=lambda item: (day_order.get(item.get('day_of_week'), 7), item.get('starts_at', '')))
        return render_template('timetable.html', user_semester=semester, user_section=section, entries=entries)
    except Exception:
        app.logger.exception('Request processing failed')
        return render_template('timetable.html', error='The timetable could not be loaded. Please try again later.', entries=[])
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
            allowed = {'python', 'javascript', 'java', 'cpp', 'c'}
            test_inputs = request.form.getlist('test_inputs[]')
            test_outputs = request.form.getlist('test_outputs[]')
            if not isinstance(title, str) or not title.strip() or len(title) > 160:
                raise ValueError('Enter an assessment title of 160 characters or fewer')
            if not isinstance(description, str) or not description.strip() or len(description) > 5000:
                raise ValueError('Enter a description of 5,000 characters or fewer')
            if difficulty not in {'easy', 'medium', 'hard'} or not (1 <= points <= 1000):
                raise ValueError('Choose a valid difficulty and points value')
            if not (1 <= time_limit <= 300 and 32 <= memory_limit <= 2048):
                raise ValueError('Choose valid time and memory limits')
            if not languages or len(languages) > 5 or any(item not in allowed for item in languages):
                raise ValueError('Choose one or more supported languages')
            if not (1 <= len(test_inputs) == len(test_outputs) <= 10):
                raise ValueError('Add between 1 and 10 complete test cases')
            if any(len(value) > 10000 for value in test_inputs + test_outputs):
                raise ValueError('Each test case must be 10,000 characters or fewer')

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
                'allowed_languages': json.dumps(languages),
                'created_at': 'now()'  # Add creation timestamp
            }
            
            response = supabase.table('coding_assessments').insert(assessment_data).execute()
            
            if response.data:
                assessment_id = response.data[0]['id']

                # Save the validated test cases
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
            app.logger.exception('Request processing failed')
            return render_template('faculty_coding_assesment.html', error='Please fill all required fields correctly')

    return render_template('faculty_coding_assesment.html')
@app.route('/student_coding_assesment')
def student_coding_assesment():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    try:
        
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

        return render_template('student_coding_assesment.html', 
                            assessments=assessments,
                            stats={
                                'total': len(assessments),
                                'completed': 0,
                                'attempts': 0,
                                'time_spent': 0
                            })
                            
    except Exception as e:
        app.logger.exception('Request processing failed')
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
    throttled = _execution_rate_limit()
    if throttled:
        return throttled
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Expected a JSON object'}), 400
    assessment_id = data.get('assessment_id')
    code = data.get('code')
    language = data.get('language')

    if not isinstance(code, str) or not code or len(code) > 50000:
        return jsonify({'error': 'Code is required and must be under 50,000 characters'}), 400
    if assessment_id is None or not isinstance(language, str):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        if not JUDGE0_API_HEADERS['x-rapidapi-key']:
            return jsonify({'error': 'Code execution is not configured'}), 503
        language_key = language.strip().lower() if isinstance(language, str) else ''
        canonical_language = {'c++': 'cpp'}.get(language_key, language_key)
        language_id = LANGUAGE_IDS.get(language_key)
        if not language_id:
            return jsonify({'error': 'Unsupported language'}), 400
        # Fetch assessment and its test cases
        assessment_response = supabase.table('coding_assessments').select('*').eq('id', assessment_id).execute()
        assessment = assessment_response.data[0] if assessment_response.data else None

        if not assessment:
            return jsonify({'error': 'Assessment not found'}), 404
        try:
            allowed_languages = json.loads(assessment.get('allowed_languages') or '[]')
        except (TypeError, json.JSONDecodeError):
            allowed_languages = []
        if allowed_languages and canonical_language not in allowed_languages:
            return jsonify({'error': 'This language is not enabled for the assessment'}), 400

        test_cases_response = supabase.table('assessment_test_cases').select('*').eq('assessment_id', assessment_id).execute()
        test_cases = test_cases_response.data if test_cases_response.data else []

        if not test_cases:
            return jsonify({'error': 'No test cases found for this assessment'}), 404
        if len(test_cases) > 50 or any(len(str(tc.get('input_data') or '')) > 10000 for tc in test_cases):
            return jsonify({'error': 'Assessment test data exceeds execution limits'}), 400

        results = []
        all_passed = True

        for test_case in test_cases:
            # Prepare the payload for Judge0 API
            payload = {
                'source_code': code,
                'language_id': language_id,
                'stdin': test_case['input_data'],
                'expected_output': test_case['expected_output'],
                'base64_encoded': False
            }

            # Send the request to Judge0 API
            response = requests.post(JUDGE0_API_URL, headers=JUDGE0_API_HEADERS, json=payload, timeout=12)
            response.raise_for_status()
            token = response.json().get('token')

            if not token:
                return jsonify({'error': 'Failed to get submission token'}), 500

            # Poll for the result
            result_url = f"{JUDGE0_API_URL}/{token}"
            max_attempts = 10
            attempts = 0

            while attempts < max_attempts:
                result_response = requests.get(result_url, headers=JUDGE0_API_HEADERS, timeout=8)
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
            passed = result.get('status', {}).get('id') == 3 and result.get('stdout', '').strip() == test_case['expected_output'].strip()
            all_passed = all_passed and passed

            results.append({
                'input': test_case['input_data'],
                'expected': test_case['expected_output'],
                'actual': result.get('stdout', '').strip(),
                'status': result.get('status', {}).get('description', 'Unknown'),
                'passed': passed
            })

        points_earned = 0
        already_solved = False
        if all_passed:
            points_earned, already_solved = _award_points_once('assessment_solutions', 'assessment_id', int(assessment_id), session['user_id'], assessment.get('points'))

        return jsonify({
            'results': results,
            'all_passed': all_passed,
            'points_earned': points_earned,
            'already_solved': already_solved
        })

    except requests.exceptions.RequestException as e:
        app.logger.exception('Request processing failed')
        return jsonify({'error': 'Failed to execute code. Please try again.'}), 500
    except Exception as e:
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
        app.logger.exception('Request processing failed')
        return jsonify({'error': 'Failed to fetch sections'}), 500

@app.route('/get_students')
def get_students():
    faculty_id = session.get('faculty_id')
    section = request.args.get('section', '').strip()
    if not section:
        return jsonify({'error': 'Section is required'}), 400
    assigned = supabase.table('faculty_sections').select('id').eq('faculty_id', faculty_id).eq('section', section).limit(1).execute()
    if not assigned.data:
        return jsonify({'error': 'You are not assigned to this section'}), 403
    try:
        response = supabase.table('users').select('id', 'name', 'roll_number', 'section').eq('role', 'student').eq('section', section).order('name').limit(500).execute()
        students = []
        for student in response.data:
            record = supabase.table('attendance').select('total_classes', 'attended_classes').eq('student_id', student['id']).eq('section', section).limit(1).execute()
            attendance = record.data[0] if record.data else {'attended_classes': 0, 'total_classes': 0}
            students.append({'id': student['id'], 'name': student['name'], 'roll_number': student['roll_number'], 'attendance': f"{attendance['attended_classes']}/{attendance['total_classes']}"})
        return jsonify(students)
    except Exception:
        app.logger.exception('Could not fetch section roster')
        return jsonify({'error': 'Failed to fetch students'}), 500

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Expected a JSON object'}), 400
    section = data.get('section')
    attendance_data = data.get('attendance')
    try:
        attendance_date = dt.strptime(data.get('date', ''), '%Y-%m-%d').date().isoformat()
    except (TypeError, ValueError):
        return jsonify({'error': 'Date must use YYYY-MM-DD format'}), 400
    if not isinstance(section, str) or not section.strip() or not isinstance(attendance_data, list) or not 1 <= len(attendance_data) <= 500:
        return jsonify({'error': 'A section and a valid attendance list are required'}), 400
    faculty_id = session['faculty_id']
    assigned = supabase.table('faculty_sections').select('id').eq('faculty_id', faculty_id).eq('section', section).limit(1).execute()
    if not assigned.data:
        return jsonify({'error': 'You are not assigned to this section'}), 403
    conn = None if USING_SUPABASE else _get_connection()
    results = []
    try:
        # Validate the complete roster before changing any records.
        for item in attendance_data:
            if not isinstance(item, dict) or item.get('status') not in {'present', 'absent'}:
                return jsonify({'error': 'Each student must have a valid attendance status'}), 400
            try:
                student_id = int(item.get('student_id'))
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid student ID'}), 400
            if USING_SUPABASE:
                valid = supabase.table('users').select('id').eq('id', student_id).eq('role', 'student').eq('section', section).limit(1).execute().data
            else:
                valid = conn.execute("SELECT id FROM users WHERE id = ? AND role = 'student' AND section = ?", (student_id, section)).fetchone()
            if not valid:
                return jsonify({'error': 'The list contains a student outside this section'}), 403

        for item in attendance_data:
            student_id = int(item['student_id'])
            status = item['status']
            if USING_SUPABASE:
                dated_response = supabase.table('attendance_records').select('id', 'status').eq('student_id', student_id).eq('section', section).eq('attendance_date', attendance_date).limit(1).execute()
                rollup_response = supabase.table('attendance').select('id', 'attended_classes', 'total_classes').eq('student_id', student_id).eq('section', section).limit(1).execute()
                dated_record = dated_response.data[0] if dated_response.data else None
                rollup = rollup_response.data[0] if rollup_response.data else None
                total = (rollup['total_classes'] if rollup else 0) + (0 if dated_record else 1)
                attended = (rollup['attended_classes'] if rollup else 0) + (1 if status == 'present' else 0) - (1 if dated_record and dated_record['status'] == 'present' else 0)
                attendance_record = {'student_id': student_id, 'section': section, 'faculty_id': faculty_id, 'attendance_date': attendance_date, 'status': status}
                if dated_record:
                    supabase.table('attendance_records').update({'faculty_id': faculty_id, 'status': status}).eq('id', dated_record['id']).execute()
                else:
                    supabase.table('attendance_records').insert(attendance_record).execute()
                rollup_data = {'total_classes': total, 'attended_classes': attended}
                if rollup:
                    supabase.table('attendance').update(rollup_data).eq('id', rollup['id']).execute()
                else:
                    supabase.table('attendance').insert({'student_id': student_id, 'section': section, **rollup_data}).execute()
            else:
                dated_record = conn.execute('SELECT status FROM attendance_records WHERE student_id = ? AND section = ? AND attendance_date = ?', (student_id, section, attendance_date)).fetchone()
                rollup = conn.execute('SELECT id, attended_classes, total_classes FROM attendance WHERE student_id = ? AND section = ?', (student_id, section)).fetchone()
                total = (rollup['total_classes'] if rollup else 0) + (0 if dated_record else 1)
                attended = (rollup['attended_classes'] if rollup else 0) + (1 if status == 'present' else 0) - (1 if dated_record and dated_record['status'] == 'present' else 0)
                conn.execute("INSERT INTO attendance_records (student_id, section, faculty_id, attendance_date, status) VALUES (?, ?, ?, ?, ?) ON CONFLICT(student_id, section, attendance_date) DO UPDATE SET faculty_id = excluded.faculty_id, status = excluded.status", (student_id, section, faculty_id, attendance_date, status))
                if rollup:
                    conn.execute('UPDATE attendance SET total_classes = ?, attended_classes = ? WHERE id = ?', (total, attended, rollup['id']))
                else:
                    conn.execute('INSERT INTO attendance (student_id, section, total_classes, attended_classes) VALUES (?, ?, ?, ?)', (student_id, section, total, attended))
            results.append({'student_id': student_id, 'attendance': f"{attended}/{total}"})
        if conn:
            conn.commit()
        return jsonify({'message': 'Attendance saved', 'results': results})
    except Exception:
        if conn:
            conn.rollback()
        app.logger.exception('Could not save attendance')
        return jsonify({'error': 'Failed to save attendance'}), 500
    finally:
        if conn:
            conn.close()

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
        app.logger.exception('Request processing failed')
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
        app.logger.exception('Request processing failed')
        return render_template('code_room.html', error='Failed to load code rooms')

@app.route('/create_code_room', methods=['POST'])
def create_code_room():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'error': 'A valid JSON object is required'}), 400
        name = data.get('name')
        language = data.get('language')
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        supported_languages = {'python', 'javascript', 'java', 'c', 'cpp', 'c++'}
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            return jsonify({'error': 'Room names must be 1 to 100 characters'}), 400
        if not isinstance(language, str) or language.strip().lower() not in supported_languages:
            return jsonify({'error': 'Choose a supported programming language'}), 400
            
        # Create new code room
        room_data = {
            'name': name.strip(),
            'created_by': user_id,
            'language': language.strip().lower(),
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
        app.logger.exception('Request processing failed')
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
        room_response = supabase.table('code_rooms').select('*').eq('id', room_id).eq('is_active', True).execute()
        if not room_response.data:
            return jsonify({'error': 'Room not found or inactive'}), 404

        # Check if user is already a participant
        existing_participant = supabase.table('code_room_participants').select('*').eq('room_id', room_id).eq('user_id', user_id).execute()
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
            .execute()
            
        messages = messages_response.data if messages_response.data else []
        
        return render_template('code_room_page.html', 
                             room=room, 
                             participants=participants,
                             messages=messages)
    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({'error': f'Failed to join code room: {str(e)}'}), 500

@app.route('/update_code/<room_id>', methods=['POST'])
def update_code(room_id):
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'error': 'A valid JSON object is required'}), 400
        code = data.get('code')
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        if not isinstance(code, str) or len(code) > 100_000:
            return jsonify({'error': 'Code must be text and 100,000 characters or fewer'}), 413
            
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
        app.logger.exception('Request processing failed')
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
        app.logger.exception('Request processing failed')
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
        
        # Fetch messages for the room
        messages_response = supabase.table('code_room_messages').select('*').eq('room_id', room_id).order('created_at', desc=True).execute()
        
        # Sort messages by created_at
        if messages_response.data and 'created_at' in messages_response.data[0]:
            messages_response.data.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        elif messages_response.data and 'id' in messages_response.data[0]:
            # Fallback to sorting by ID if no created_at
            messages_response.data.sort(key=lambda x: x.get('id', 0), reverse=True)
        
        # Enrich messages with sender details
        messages = messages_response.data or []
        
        # Fetch sender details for each message
        sender_ids = list(set(msg['sender_id'] for msg in messages))
        users_response = supabase.table('users').select('id', 'name', 'role').in_('id', sender_ids).execute()
        
        # Create a lookup dictionary for user details
        users_lookup = {user['id']: user for user in users_response.data}
        
        # Enrich messages with sender information
        enriched_messages = []
        for msg in messages:
            sender = users_lookup.get(msg['sender_id'], {'name': 'Unknown', 'role': 'Unknown'})
            enriched_msg = {
                **msg,
                'sender_name': sender['name'],
                'sender_role': sender['role']
            }
            enriched_messages.append(enriched_msg)
        
        return jsonify({
            'messages': enriched_messages
        })

    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({'error': 'Failed to fetch messages'}), 500

@app.route('/send_code_room_message/<room_id>', methods=['POST'])
def send_code_room_message(room_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get('message'), str) or not data['message'].strip():
            return jsonify({'error': 'A non-empty message is required'}), 400
        if len(data['message']) > 2000:
            return jsonify({'error': 'Messages must be 2,000 characters or fewer'}), 413

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

        # Prepare message data
        message_data = {
            'room_id': room_id,
            'sender_id': user_id,
            'message': data['message'].strip(),
            'created_at': dt.now(timezone.utc).isoformat()
        }
        
        # Insert message
        message_response = supabase.table('code_room_messages').insert(message_data).execute()
        
        if message_response.data:
            return jsonify({
                'data': {
                    'id': message_response.data[0]['id'],
                    'room_id': room_id,
                    'user_id': user_id,
                    'user_name': user_name,
                    'message': data['message'].strip(),
                    'created_at': message_response.data[0]['created_at']
                }
            })

    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({'error': 'Failed to send message'}), 500

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
        
        # Get messages for the room
        messages_response = supabase.table('code_room_messages')\
            .select('*, user:users(name)')\
            .eq('room_id', room_id)\
            .order('created_at', desc=True)\
            .execute()
            
        # Sort messages by created_at
        if messages_response.data and 'created_at' in messages_response.data[0]:
            messages_response.data.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        elif messages_response.data and 'id' in messages_response.data[0]:
            # Fallback to sorting by ID if no created_at
            messages_response.data.sort(key=lambda x: x.get('id', 0), reverse=True)
        
        messages = messages_response.data if messages_response.data else []
        
        return render_template('code_room_page.html', 
                             room=room, 
                             participants=participants,
                             messages=messages)
    except Exception as e:
        app.logger.exception('Request processing failed')
        return redirect(url_for('code_room'))

@app.route('/create_assessments_table')
def create_assessments_table():
    try:
        init_db()
        return jsonify({"message": "Tables already ensured in SQLite"})
    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({"error": f"Failed to create tables: {str(e)}"}), 500

@app.route('/student/assignments')
def student_assignments():
    try:
        student = supabase.table('users').select('branch', 'semester').eq('id', session['user_id']).limit(1).execute().data
        if not student:
            return render_template('student assignment.html', assignments=[], error='Student account not found')
        cohort = student[0]
        response = supabase.table('assessments').select('*').eq('branch', cohort.get('branch')).eq('year', cohort.get('semester')).order('deadline').limit(200).execute()
        assignments = response.data if response.data else []
        
        return render_template('student assignment.html', assignments=assignments)
    except Exception as e:
        app.logger.exception('Request processing failed')
        return render_template('student assignment.html', error='Failed to load assignments')

@app.route('/submit_assignment', methods=['POST'])
def submit_assignment():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'error': 'Expected a JSON object'}), 400
        assignment_id = data.get('assignment_id')
        link = data.get('drive_link')  # Changed from 'link' to 'drive_link'
        user_id = session.get('user_id')


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

        assignment = supabase.table('assessments').select('id').eq('id', assignment_id).limit(1).execute()
        if not assignment.data:
            return jsonify({'error': 'Assignment not found'}), 404
        if not isinstance(link, str) or len(link) > 2000 or not link.startswith(('https://', 'http://')):
            return jsonify({'error': 'Enter a valid http(s) submission link'}), 400

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

        response = supabase.table('assignment_submissions').insert(submission_data).execute()
        
        if response.data:
            return jsonify({
                'message': 'Assignment submitted successfully',
                'submission_id': response.data[0]['id']
            })
        
        return jsonify({'error': 'Failed to submit assignment - no data returned from database'}), 500

    except Exception as e:
        app.logger.exception('Assignment submission failed')
        return jsonify({'error': 'Failed to submit assignment'}), 500

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

        owner = supabase.table('assessments').select('id').eq('id', assessment_id).eq('faculty_id', session.get('faculty_id')).limit(1).execute()
        if not owner.data:
            return jsonify({'error': 'Assignment not found or not owned by you'}), 404
        if not isinstance(link_url, str) or len(link_url) > 2000 or not link_url.startswith(('https://', 'http://')):
            return jsonify({'error': 'Enter a valid http(s) link'}), 400

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
        app.logger.exception('Request processing failed')
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
        app.logger.exception('Request processing failed')
        return jsonify({'error': 'Failed to fetch links'}), 500

@app.route('/create_assignment_submissions_table')
def create_assignment_submissions_table():
    try:
        init_db()
        return jsonify({"message": "Assignment submissions table already ensured in SQLite"})
    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({"error": f"Failed to create table: {str(e)}"}), 500

@app.route('/get_assignment_submissions/<assignment_id>')
def get_assignment_submissions(assignment_id):
    try:
        assignment = supabase.table('assessments').select('id').eq('id', assignment_id).limit(1).execute()
        if not assignment.data:
            return jsonify({'error': 'Assignment not found'}), 404
        if session.get('role') == 'faculty' and not supabase.table('assessments').select('id').eq('id', assignment_id).eq('faculty_id', session.get('faculty_id')).limit(1).execute().data:
            return jsonify({'error': 'You do not own this assignment'}), 403
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
        app.logger.exception('Request processing failed')
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
        app.logger.exception('Request processing failed')
        return jsonify({'error': 'Failed to fetch assignments'}), 500

@app.route('/add_faculty', methods=['POST'])
@admin_required
def add_faculty():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Expected a JSON object'}), 400
        data['email'] = data.get('email', '').strip().casefold() if isinstance(data.get('email'), str) else ''
        if not isinstance(data.get('password'), str) or not (12 <= len(data['password'].encode('utf-8')) <= 72):
            return jsonify({'success': False, 'message': 'Password must be 12 to 72 bytes long'}), 400
        if not isinstance(data.get('sections'), str):
            return jsonify({'success': False, 'message': 'Sections must be a comma-separated list'}), 400
        # Validate required fields
        required_fields = ['name', 'email', 'password', 'roll_number', 'branch', 'subject', 'sections']
        for field in required_fields:
            value = data.get(field)
            if not isinstance(value, str) or not value.strip():
                return jsonify({'success': False, 'message': f'Missing or invalid field: {field}'}), 400
            if len(value) > 500:
                return jsonify({'success': False, 'message': f'Field is too long: {field}'}), 400
        if '@' not in data['email'] or '.' not in data['email'].rsplit('@', 1)[-1] or len(data['email']) > 254:
            return jsonify({'success': False, 'message': 'Enter a valid email address'}), 400

        sections = list(dict.fromkeys(part.strip() for part in data['sections'].split(',') if part.strip()))
        if not sections or len(sections) > 20 or any(len(section) > 40 for section in sections):
            return jsonify({'success': False, 'message': 'Enter between 1 and 20 valid sections'}), 400

        # Check if email already exists
        existing_user = supabase.table('users').select('id').eq('email', data['email']).execute()
        if existing_user.data:
            return jsonify({'success': False, 'message': 'Email already exists'}), 400

        # Hash the password
        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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

        # Insert faculty into users table
        response = supabase.table('users').insert(faculty_data).execute()
        
        if not response.data:
            return jsonify({'success': False, 'message': 'Failed to add faculty'}), 500

        # Add faculty sections
        faculty_id = response.data[0]['id']
        for section in sections:
            section_data = {
                'faculty_id': faculty_id,
                'section': section
            }
            supabase.table('faculty_sections').insert(section_data).execute()

        return jsonify({'success': True, 'message': 'Faculty added successfully'})
    except Exception as e:
        app.logger.exception('Unable to add faculty')
        return jsonify({'success': False, 'message': 'Failed to add faculty'}), 500

@app.route('/add_student', methods=['POST'])
@admin_required
def add_student():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Expected a JSON object'}), 400
        data['email'] = data.get('email', '').strip().casefold() if isinstance(data.get('email'), str) else ''
        if not isinstance(data.get('password'), str) or not (12 <= len(data['password'].encode('utf-8')) <= 72):
            return jsonify({'success': False, 'message': 'Password must be 12 to 72 bytes long'}), 400
        # Validate required fields
        required_fields = ['name', 'email', 'password', 'roll_number', 'branch', 'section', 'semester']
        for field in required_fields:
            value = data.get(field)
            if not isinstance(value, str) or not value.strip():
                return jsonify({'success': False, 'message': f'Missing or invalid field: {field}'}), 400
            if len(value) > 500:
                return jsonify({'success': False, 'message': f'Field is too long: {field}'}), 400
        if '@' not in data['email'] or '.' not in data['email'].rsplit('@', 1)[-1] or len(data['email']) > 254:
            return jsonify({'success': False, 'message': 'Enter a valid email address'}), 400

        if data['semester'] not in {str(number) for number in range(1, 9)}:
            return jsonify({'success': False, 'message': 'Semester must be between 1 and 8'}), 400

        # Check if email already exists
        existing_user = supabase.table('users').select('id').eq('email', data['email']).execute()
        if existing_user.data:
            return jsonify({'success': False, 'message': 'Email already exists'}), 400

        # Hash the password
        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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

        # Insert student into users table
        response = supabase.table('users').insert(student_data).execute()
        
        if not response.data:
            return jsonify({'success': False, 'message': 'Failed to add student'}), 500

        # Initialize attendance record
        attendance_data = {
            'student_id': response.data[0]['id'],
            'section': data['section'],
            'attended_classes': 0,
            'total_classes': 0
        }
        supabase.table('attendance').insert(attendance_data).execute()

        return jsonify({'success': True, 'message': 'Student added successfully'})
    except Exception as e:
        app.logger.exception('Unable to add student')
        return jsonify({'success': False, 'message': 'Failed to add student'}), 500

@app.route('/edit_student/<int:student_id>', methods=['PUT'])
@admin_required
def edit_student(student_id):
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Expected a JSON object'}), 400
        # Validate required fields
        required_fields = ['name', 'email', 'roll_number', 'branch', 'section', 'semester']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'Missing required field: {field}'}), 400

        # Check if email already exists for another student
        data['email'] = data['email'].strip().casefold()
        existing_user = supabase.table('users')\
            .select('id')\
            .eq('email', data['email'])\
            .neq('id', student_id)\
            .execute()
        if existing_user.data:
            return jsonify({'success': False, 'message': 'Email already exists'}), 400
        target = supabase.table('users').select('id').eq('id', student_id).eq('role', 'student').limit(1).execute()
        if not target.data:
            return jsonify({'success': False, 'message': 'Student not found'}), 404

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
            .eq('role', 'student')\
            .execute()
        
        if not response.data:
            return jsonify({'success': False, 'message': 'Failed to update student'}), 500

        return jsonify({'success': True, 'message': 'Student updated successfully'})
    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({'success': False, 'message': 'Failed to update student'}), 500

@app.route('/delete_student/<int:student_id>', methods=['DELETE'])
@admin_required
def delete_student(student_id):
    try:
        if USING_SUPABASE:
            result = supabase.table('users').select('id', 'roll_number').eq('id', student_id).eq('role', 'student').limit(1).execute()
            student = result.data[0] if result.data else None
            if not student:
                return jsonify({'success': False, 'message': 'Student not found'}), 404
            supabase.table('chat_rooms').delete().or_(f"user1_id = {student_id}", f"user2_id = {student_id}").execute()
            supabase.table('code_rooms').delete().eq('created_by', student_id).execute()
            supabase.table('code_room_messages').delete().eq('user_id', student_id).execute()
            supabase.table('code_room_messages').delete().eq('sender_id', student_id).execute()
            supabase.table('attendance_records').delete().eq('student_id', student_id).execute()
            supabase.table('attendance').delete().eq('student_id', student_id).execute()
            supabase.table('problem_solutions').delete().eq('user_id', student_id).execute()
            supabase.table('assessment_solutions').delete().eq('user_id', student_id).execute()
            supabase.table('assignment_submissions').delete().eq('roll_number', student['roll_number']).execute()
            supabase.table('users').delete().eq('id', student_id).eq('role', 'student').execute()
        else:
            conn = _get_connection()
            try:
                student = conn.execute("SELECT id, roll_number FROM users WHERE id = ? AND role = 'student'", (student_id,)).fetchone()
                if not student:
                    return jsonify({'success': False, 'message': 'Student not found'}), 404
                # Remove dependent rows explicitly for older local databases too.
                conn.execute('DELETE FROM chat_rooms WHERE user1_id = ? OR user2_id = ?', (student_id, student_id))
                conn.execute('DELETE FROM code_rooms WHERE created_by = ?', (student_id,))
                conn.execute('DELETE FROM code_room_messages WHERE user_id = ? OR sender_id = ?', (student_id, student_id))
                conn.execute('DELETE FROM attendance_records WHERE student_id = ?', (student_id,))
                conn.execute('DELETE FROM attendance WHERE student_id = ?', (student_id,))
                conn.execute('DELETE FROM problem_solutions WHERE user_id = ?', (student_id,))
                conn.execute('DELETE FROM assessment_solutions WHERE user_id = ?', (student_id,))
                conn.execute('DELETE FROM assignment_submissions WHERE roll_number = ?', (student['roll_number'],))
                conn.execute("DELETE FROM users WHERE id = ? AND role = 'student'", (student_id,))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

        return jsonify({'success': True, 'message': 'Student deleted successfully'})
    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({'success': False, 'message': 'Failed to delete student'}), 500



# Instead of directly hardcoding the key, use a more secure method
COHERE_API_KEY = os.environ.get('COHERE_API_KEY', '')
COHERE_MODEL = os.environ.get('COHERE_MODEL', 'command-a-plus-05-2026')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')

# Safely initialize Cohere client
co = None
try:
    if cohere and COHERE_API_KEY:
        co = cohere.ClientV2(api_key=COHERE_API_KEY)
except Exception as e:
    app.logger.exception('Request processing failed')

def ai_provider_configured():
    return bool(GROQ_API_KEY or co)


def generate_with_ai(prompt, max_tokens=500, temperature=0.7):
    if GROQ_API_KEY:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}'},
            json={
                'model': GROQ_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_completion_tokens': max_tokens,
                'temperature': temperature,
            },
            timeout=(5, 45),
        )
        response.raise_for_status()
        content = response.json().get('choices', [{}])[0].get('message', {}).get('content')
        if content:
            return content
        raise RuntimeError('Groq returned an empty response')

    if not co:
        raise RuntimeError('No AI provider is configured')
    response = co.chat(
        model=COHERE_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = getattr(response.message, 'content', [])
    for item in content:
        text = getattr(item, 'text', None)
        if text:
            return text
    raise RuntimeError('The AI provider returned an empty response')


# Backwards-compatible name used by older integrations.
generate_with_cohere = generate_with_ai
@app.route('/job_match_recommender')
def job_match_recommender():
    return redirect(url_for('job_match_recomender1'))
@app.route('/code-review')
def code_review():
    return render_template('code_review.html')


@app.route('/api/review', methods=['POST'])
def review_code_api():
    code = request.form.get('code', '')
    language = request.form.get('language', 'python')
    if not code or len(code) > 30000:
        return jsonify({'error': 'Code is required and must be under 30,000 characters'}), 400
    if not ai_provider_configured():
        return jsonify({'error': 'Code review is not configured on this server'}), 503

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
        feedback = generate_with_ai(prompt, max_tokens=300, temperature=0.7)
        return jsonify({'feedback': feedback})

    except Exception:
        app.logger.exception('AI code review failed')
        return jsonify({'error': 'Code review is temporarily unavailable'}), 502
@app.route('/job_match_recomender', methods=['GET'])
def job_match_recomender1():
    return render_template('job_match_recomender.html')
@app.route('/student leaderboard', methods=['GET'])
def student_leaderboard():
    user_id = session.get('user_id')
    try:
        response = supabase.table('users').select('id', 'name', 'roll_number', 'points')\
            .eq('role', 'student').order('points', desc=True).limit(100).execute()
        learners = response.data or []
        for learner in learners:
            learner['points'] = int(learner.get('points') or 0)
        learners.sort(key=lambda learner: (-learner['points'], (learner.get('name') or '').casefold()))
        current_rank = next((index for index, learner in enumerate(learners, 1) if str(learner['id']) == str(user_id)), None)
        return render_template(
            'student leaderboard.html',
            learners=learners,
            current_rank=current_rank,
            stats={
                'learners': len(learners),
                'top_score': learners[0]['points'] if learners else 0,
                'participants': sum(1 for learner in learners if learner['points'] > 0),
            },
        )
    except Exception:
        app.logger.exception('Coding leaderboard could not be loaded')
        return render_template(
            'student leaderboard.html',
            learners=[],
            current_rank=None,
            stats={'learners': 0, 'top_score': 0, 'participants': 0},
            error='The leaderboard could not be loaded. Please try again later.',
        )

@app.route('/recommend', methods=['POST'])
def recommend_jobs():
    skills_input = request.form.get('skills', '').strip()
    if not skills_input or len(skills_input) > 2000:
        return render_template('job_match_recomender.html', error='Enter skills in 2,000 characters or fewer')
    if not ai_provider_configured():
        return render_template('job_match_recomender.html', error='Recommendations are not configured on this server')

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
        recommendation = generate_with_ai(prompt, max_tokens=400, temperature=0.7)
    except Exception:
        app.logger.exception('Career recommendations failed')
        recommendation = 'Recommendations are temporarily unavailable. Please try again later.'

    return render_template('job_match_recomender.html', recommendation=recommendation)
@app.route('/ai_code_assistant')
def ai_code_assistant():
    return render_template('ai_code_assistant.html')

@app.route('/solve', methods=['POST'])
def solve_code_problem():
    question = request.form.get('question', '').strip()
    if not question or len(question) > 3000:
        return render_template('ai_code_assistant.html', error='Enter a question in 3,000 characters or fewer')
    if not ai_provider_configured():
        return render_template('ai_code_assistant.html', error='The AI assistant is not configured on this server')

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
        result = generate_with_ai(prompt, max_tokens=500, temperature=0.7)
    except Exception:
        app.logger.exception('AI assistant request failed')
        result = 'The assistant is temporarily unavailable. Please try again later.'

    return render_template('ai_code_assistant.html', result=result)

@app.route('/chat')
def chat_page():
    """
    Render the chat page for users
    """
    user_id = session.get('user_id')
    user_role = session.get('role')
    
    if not user_id:
        return redirect(url_for('login'))
    
    try:
        # Fetch user details
        user_response = supabase.table('users').select('*').eq('id', user_id).execute()
        user_details = user_response.data[0] if user_response.data else None
        
        # Fetch recent chat rooms or create a default room
        chat_rooms_response = supabase.table('chat_rooms').select('*').or_(
            f"user1_id = {user_id}",
            f"user2_id = {user_id}"
        ).execute()
        
        return render_template('chat.html', 
                               user=user_details, 
                               chat_rooms=chat_rooms_response.data,
                               user_role=user_role)
    
    except Exception as e:
        return render_template('chat.html', error=str(e))

@app.route('/create_chat_room', methods=['POST'])
def create_chat_room():
    """
    Create a new chat room between two users
    Using integer-based IDs
    """
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        # Get the other user's ID from the request
        other_user_id = request.form.get('other_user_id')
        
        # Validate inputs
        if not other_user_id:
            return jsonify({'status': 'error', 'message': 'Recipient user ID is required'}), 400
        
        # Convert to integers
        try:
            user_id = int(user_id)
            other_user_id = int(other_user_id)
        except (ValueError, TypeError):
            return jsonify({'status': 'error', 'message': 'Invalid user IDs'}), 400
        
        # Validate that the other user exists and is of the appropriate role
        other_user_response = supabase.table('users').select('id', 'role').eq('id', other_user_id).execute()
        
        if not other_user_response.data:
            return jsonify({'status': 'error', 'message': 'Recipient user not found'}), 404
        
        expected_role = 'faculty' if session.get('role') == 'student' else 'student'
        if other_user_response.data[0]['role'] != expected_role:
            return jsonify({'status': 'error', 'message': 'Invalid chat participants'}), 403
        
        # Prevent creating chat rooms with the same user
        if user_id == other_user_id:
            return jsonify({'status': 'error', 'message': 'Cannot create a chat room with yourself'}), 400
        
        # Check if a chat room already exists
        existing_room_query1 = supabase.table('chat_rooms').select('id').eq('user1_id', user_id).eq('user2_id', other_user_id)
        existing_room_query2 = supabase.table('chat_rooms').select('id').eq('user1_id', other_user_id).eq('user2_id', user_id)
        
        existing_room_response1 = existing_room_query1.execute()
        existing_room_response2 = existing_room_query2.execute()
        
        # Combine results
        existing_rooms = existing_room_response1.data + existing_room_response2.data
        
        if existing_rooms:
            return jsonify({
                'status': 'success', 
                'room_id': existing_rooms[0]['id'],
                'message': 'Existing chat room found'
            })
        
        # Create a new chat room
        new_room_data = {
            'user1_id': user_id,
            'user2_id': other_user_id,
            'created_at': dt.now(timezone.utc).isoformat()
        }
        
        room_response = supabase.table('chat_rooms').insert(new_room_data).execute()
        
        if room_response.data:
            return jsonify({
                'status': 'success', 
                'room_id': room_response.data[0]['id'],
                'message': 'New chat room created'
            })
        else:
            return jsonify({'status': 'error', 'message': 'Failed to create chat room'}), 500
    
    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({'status': 'error', 'message': 'Failed to send message'}), 500

@app.route('/send_chat_message', methods=['POST'])
def send_chat_message():
    """
    Send a message in a specific chat room
    Validates sender's participation in the room
    """
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        # Get message details
        room_id = request.form.get('room_id')
        message_content = request.form.get('message')
        
        # Validate inputs
        if not room_id or not isinstance(message_content, str) or not message_content.strip():
            return jsonify({'status': 'error', 'message': 'Missing room_id or message'}), 400
        if len(message_content) > 2000:
            return jsonify({'status': 'error', 'message': 'Messages must be 2,000 characters or fewer'}), 413
        
        # Convert to integers
        try:
            room_id = int(room_id)
            user_id = int(user_id)
        except (ValueError, TypeError):
            return jsonify({'status': 'error', 'message': 'Invalid room_id or user_id'}), 400
        
        # Verify the user is part of this chat room
        room_response = supabase.table('chat_rooms').select('user1_id', 'user2_id').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({'status': 'error', 'message': 'Chat room not found'}), 404
        
        room_data = room_response.data[0]
        if user_id not in [room_data['user1_id'], room_data['user2_id']]:
            return jsonify({'status': 'error', 'message': 'Unauthorized to send message in this room'}), 403
        
        # Prepare message data
        message_data = {
            'room_id': room_id,
            'sender_id': user_id,
            'message': message_content,
            'created_at': dt.now(timezone.utc).isoformat()
        }
        
        # Insert message
        message_response = supabase.table('chat_messages').insert(message_data).execute()
        
        if message_response.data:
            return jsonify({
                'status': 'success', 
                'message_id': message_response.data[0]['id'],
                'message': 'Message sent successfully'
            })
        else:
            return jsonify({'status': 'error', 'message': 'Failed to send message'}), 500
    
    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_users', methods=['POST'])
def get_users():
    search_term = request.form.get('search_term', '').strip()
    if len(search_term) > 80:
        return jsonify({'error': 'Search is too long'}), 400
    # Students can find faculty; faculty can find students. Never expose arbitrary role directories.
    role = 'faculty' if session.get('role') == 'student' else 'student'
    try:
        query = supabase.table('users').select('id', 'name', 'role').eq('role', role)
        if search_term:
            query = query.filter('name', 'ilike', f'%{search_term}%')
        return jsonify(query.order('name').limit(50).execute().data or [])
    except Exception:
        app.logger.exception('User directory lookup failed')
        return jsonify({'error': 'Unable to search users'}), 500

@app.route('/get_current_user_id')
def get_current_user_id():
    """
    Retrieve the current logged-in user's ID
    """
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        # Validate user exists
        user_response = supabase.table('users').select('id', 'role').eq('id', user_id).execute()
        
        if not user_response.data:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
        
        return jsonify({
            'status': 'success', 
            'user_id': int(user_id),
            'role': user_response.data[0]['role']
        })
    
    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/faculty_chat')
def faculty_chat():
    """
    Render the chat page for faculty members
    """
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    try:
        # Fetch user details to confirm faculty role
        user_response = supabase.table('users').select('role', 'name').eq('id', user_id).execute()
        user_data = user_response.data[0] if user_response.data else None
        
        if not user_data or user_data['role'] != 'faculty':
            return redirect(url_for('login'))
        
        return render_template('faculty_chat.html', user_name=user_data['name'])
    
    except Exception as e:
        app.logger.exception('Request processing failed')
        return redirect(url_for('login'))

@app.route('/create_faculty_chat_room', methods=['POST'])
def create_faculty_chat_room():
    """
    Create a chat room between a faculty member and a student
    Ensures only one unique chat room exists between two users
    """
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        # Get student and faculty IDs from the request
        student_id = request.form.get('student_id')
        faculty_id = request.form.get('faculty_id')
        
        # Validate inputs
        if not student_id or not faculty_id:
            return jsonify({'status': 'error', 'message': 'Missing student_id or faculty_id'}), 400
        
        # Convert to integers
        try:
            student_id = int(student_id)
            faculty_id = int(faculty_id)
            user_id = int(user_id)
        except (ValueError, TypeError):
            return jsonify({'status': 'error', 'message': 'Invalid user IDs'}), 400
        
        # Validate that the other user exists and is of the appropriate role
        other_user_response = supabase.table('users').select('id', 'role').eq('id', student_id).execute()
        
        if not other_user_response.data:
            return jsonify({'status': 'error', 'message': 'Recipient user not found'}), 404
        
        # The signed-in faculty member may only open a room with a student.
        if faculty_id != user_id or other_user_response.data[0]['role'] != 'student':
            return jsonify({'status': 'error', 'message': 'Invalid chat participants'}), 403
        
        # Prevent creating chat rooms with the same user
        if user_id != faculty_id or user_id == student_id:
            return jsonify({'status': 'error', 'message': 'Invalid chat participants'}), 400
        
        # Check if a chat room already exists (in either direction)
        existing_room_query1 = supabase.table('chat_rooms').select('id').eq('user1_id', faculty_id).eq('user2_id', student_id)
        existing_room_query2 = supabase.table('chat_rooms').select('id').eq('user1_id', student_id).eq('user2_id', faculty_id)
        
        existing_room_response1 = existing_room_query1.execute()
        existing_room_response2 = existing_room_query2.execute()
        
        # Combine results
        existing_rooms = existing_room_response1.data + existing_room_response2.data
        
        if existing_rooms:
            return jsonify({
                'status': 'success', 
                'room_id': existing_rooms[0]['id'],
                'message': 'Existing chat room found'
            })
        
        # Create new room data
        new_room_data = {
            'user1_id': faculty_id,
            'user2_id': student_id,
            'created_at': dt.now(timezone.utc).isoformat()
        }
        
        # Insert new room
        room_response = supabase.table('chat_rooms').insert(new_room_data).execute()
        
        if not room_response.data:
            return jsonify({'status': 'error', 'message': 'Failed to create chat room'}), 500
        
        # Return the new room ID
        return jsonify({
            'status': 'success', 
            'room_id': room_response.data[0]['id'],
            'message': 'Chat room created successfully'
        })
    
    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_chat_messages/<int:room_id>')
def get_chat_messages(room_id):
    """
    Retrieve messages for a specific chat room
    Supports bidirectional chat rooms
    """
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        # Verify room exists and user is a participant
        room_response = supabase.table('chat_rooms').select('user1_id', 'user2_id').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({'status': 'error', 'message': 'Chat room not found'}), 404
        
        room_data = room_response.data[0]
        if user_id not in [room_data['user1_id'], room_data['user2_id']]:
            return jsonify({'status': 'error', 'message': 'Unauthorized to access this chat room'}), 403
        
        # Fetch messages for the room, using the existing timestamp column
        messages_response = supabase.table('chat_messages').select('*').eq('room_id', room_id).order('created_at', desc=True).execute()
        
        # Sort messages by timestamp if created_at is not available
        if messages_response.data and 'created_at' not in messages_response.data[0]:
            if 'timestamp' in messages_response.data[0]:
                messages_response.data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            elif 'id' in messages_response.data[0]:
                # Fallback to sorting by ID if no timestamp
                messages_response.data.sort(key=lambda x: x.get('id', 0), reverse=True)
        
        # Enrich messages with sender details
        messages = messages_response.data or []
        
        # Fetch sender details for each message
        sender_ids = list(set(msg['sender_id'] for msg in messages))
        users_response = supabase.table('users').select('id', 'name', 'role').in_('id', sender_ids).execute()
        
        # Create a lookup dictionary for user details
        users_lookup = {user['id']: user for user in users_response.data}
        
        # Enrich messages with sender information
        enriched_messages = []
        for msg in messages:
            sender = users_lookup.get(msg['sender_id'], {'name': 'Unknown', 'role': 'Unknown'})
            enriched_msg = {
                **msg,
                'sender_name': sender['name'],
                'sender_role': sender['role']
            }
            enriched_messages.append(enriched_msg)
        
        return jsonify({
            'status': 'success', 
            'messages': enriched_messages,
            'current_user_id': user_id,
            'room_details': {
                'user1_id': room_data['user1_id'],
                'user2_id': room_data['user2_id']
            }
        })
    
    except Exception as e:
        app.logger.exception('Request processing failed')
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    app.run(host=host, port=port)
