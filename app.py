from flask import Flask, request, jsonify, render_template
import requests
import time

app = Flask(__name__)

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

if __name__ == '__main__':
    app.run(debug=True)
