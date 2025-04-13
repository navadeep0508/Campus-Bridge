# Campus-Bridge

## Overview
Campus-Bridge is a comprehensive web application designed to enhance the educational experience by providing a suite of tools for students, faculty, and administrators. The platform offers features such as course management, coding assessments, code collaboration, job matching, and more.

## Features

### 1. User Authentication
- Secure login system for students, faculty, and administrators
- Role-based access control
- Password management and recovery

### 2. Course Management
- Course tracking
- Semester-based course listings
- Personalized course dashboards

### 3. Coding Assessment Platform
- Coding problem repository
- Multiple programming language support (C, C++, Java, Python)
- Automated code submission and evaluation
- Difficulty-based coding challenges

### 4. Code Collaboration
- Code Room feature for real-time collaborative coding
- Messaging and interaction within code rooms
- Code sharing and peer programming

### 5. Additional Tools
- Code Review AI Assistant
- Job Match Recommender
- Attendance Tracking
- Faculty and Student Dashboards
- Time Table Management

## Technology Stack
- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Database**: Supabase
- **External APIs**: 
  - Judge0 (Code Compilation)
  - Cohere AI (Code Review, Job Matching)

## Prerequisites
- Python 3.8+
- Flask
- Supabase Account
- Cohere API Key
- Judge0 API Key

## Installation

1. Clone the repository
```bash
git clone https://github.com/navadeep0508/Campus-Bridge.git
cd Campus-Bridge
```

2. Install dependencies
```bash
pip install -r requirements.txt
```



3. Run the application
```bash
python app.py
```

## Configuration
- Modify `app.py` to update API configurations
- Customize templates in the `templates/` directory
- Update styles in `static/css/style.css`

## Security Notes
- Use strong, unique passwords
- Rotate API keys periodically
- Keep sensitive information in environment variables

## Contributing
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License
[Specify your license, e.g., MIT License]

## Contact
[Your contact information or project maintainer details]