# Campus Bridge - University Management System

## Project Title
Campus Bridge - A Comprehensive University Management System

## Selected Domain
Education Technology (EdTech) / University Management System

## Problem Statement / Use Case
The modern university ecosystem requires a centralized platform that can effectively manage academic activities, student-faculty interactions, and administrative tasks. Traditional systems often lack integration, leading to inefficiencies in communication, resource management, and academic tracking. There is a need for a secure, role-based system where university administrators can manage student and faculty accounts while providing them with specialized tools for their academic needs.

## Abstract / Problem Description
Campus Bridge is a comprehensive university management system designed to streamline academic operations and enhance collaboration between students, faculty, and administrators. The platform provides a secure, role-based access system where only administrators can create and manage user accounts, ensuring proper verification and data integrity.

### Admin Features
- User Management
  - Create and manage student accounts
  - Create and manage faculty accounts
  - View and track user activities
- Dashboard Analytics
  - View total students and faculty count
  - Monitor attendance statistics
  - Track course enrollment
  - View recent activities
- System Management
  - Manage academic departments
  - Configure system settings
  - Monitor system usage

### Faculty Features
- Course Management
  - Create and manage courses
  - Upload course materials
  - Track student enrollment
- Student Management
  - Track attendance
  - Manage assignments
- Assessment Tools
  - Create and grade assignments
  - Conduct coding assessments
### Student Features
- Academic Tools
  - Access course materials
  - Submit assignments
  - View grades and feedback
- Coding Environment
  - Real-time code collaboration
  - Practice coding problems
  - Take coding assessments
- Communication
  - Chat with faculty
  - Collaborate with peers
  - Access shared resources
- Personal Dashboard
  - View attendance
  - Track academic progress
  - Access timetable

## Tech Stack Used
- **Frontend:**
  - HTML5, CSS3, JavaScript
  - Bootstrap 5
  - CodeMirror (for code editor)
  - Font Awesome (for icons)
  - Google Fonts (Poppins)

- **Backend:**
  - Python
  - Flask (Web Framework)
  - SQLAlchemy (ORM)
  - SQLite (Database)


- **Additional Tools:**
  - Git (Version Control)
  - VS Code (Development Environment)

## Login Credentials

### Admin Access
- **Email:** admin@gmail.com
- **Password:** sunny

### Faculty Access
- **Email:** faculty@gmail.com
- **Password:** sunny

### Student Access 1
- **Email:** 23102a040719@mbu.asia
- **Password:** sunny

### Student Access 2
- **Email:** raghs@gmail.com
- **Password:** sunny

## Important Notes
1. **Account Creation Policy:**
   - Only administrators can create new student and faculty accounts
   - Students and faculty members cannot register themselves
   - This ensures proper verification and data integrity

2. **Security Features:**
   - Role-based access control
   - Secure password storage
   - Session management
   - Input validation and sanitization

3. **Key Features:**
   - Code collaboration rooms
   - Assignment management
   - Timetable scheduling
   - Academic tracking
   - Faculty-student communication
   - Resource sharing

## Project Structure
```
Campus-Bridge/
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── templates/
│   ├── admin/
│   ├── faculty/
│   └── student/
├── models/
├── routes/
├── config.py
├── app.py
└── README.md
```

## Getting Started
1. Clone the repository : git clone https://github.com/navadeep0508/Campus-Bridge.git
2. Install dependencies: `pip install -r requirements.txt`
3. Initialize the database: `python init_db.py`
4. Run the application: `python app.py`
5. Access the application at `http://localhost:5000`

## Contributing
This project is maintained by the university administration team. For any issues or suggestions, please contact the system administrator.

## License
This project is proprietary and confidential. Unauthorized copying, modification, distribution, or use of this software is strictly prohibited.
