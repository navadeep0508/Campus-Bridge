# Campus-Bridge 🎓

A comprehensive educational platform that bridges the gap between students and faculty, providing a seamless learning experience with integrated coding assessments, assignment management, and attendance tracking.

![Campus-Bridge](https://img.shields.io/badge/Status-Active-brightgreen)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-lightgrey)
![Supabase](https://img.shields.io/badge/Supabase-Database-orange)

## ✨ Features

### For Students
- 📚 Access course materials and assignments
- 💻 Real-time coding environment with multiple language support
- 📝 Submit assignments with Google Drive integration
- 📊 Track attendance and academic progress
- 👥 Collaborative coding rooms for group projects
- 🎯 Practice coding problems with instant feedback

### For Faculty
- 📝 Create and manage assignments
- 🎯 Design coding assessments with custom test cases
- 📊 Monitor student attendance
- 📈 Track student progress and performance
- 💬 Real-time communication with students
- 🔍 Review and grade assignments

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- Supabase account
- Google Drive API credentials (for assignment submissions)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Campus-Bridge.git
cd Campus-Bridge
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
# Create a .env file with the following variables
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
JUDGE0_API_KEY=your_judge0_api_key
```

5. Initialize the database:
```bash
python app.py
```

6. Access the application:
```
http://localhost:5000
```

## 🛠️ Tech Stack

- **Backend**: Python Flask
- **Database**: Supabase
- **Code Execution**: Judge0 API
- **Authentication**: Supabase Auth
- **Frontend**: HTML, CSS, JavaScript
- **Real-time Features**: WebSocket

## 📁 Project Structure

```
Campus-Bridge/
├── app.py              # Main application file
├── templates/          # HTML templates
├── static/            # Static files (CSS, JS, images)
├── requirements.txt   # Python dependencies
└── README.md         # Project documentation
```

## 🤝 Contributing

We welcome contributions! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Judge0 API for code execution
- Supabase for database and authentication
- Flask community for the amazing web framework

## 📞 Support

For support, email support@campusbridge.com or join our Slack channel.

---

Made with ❤️ by the Campus-Bridge Team