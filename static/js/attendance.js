document.addEventListener('DOMContentLoaded', function() {
    const studentList = document.querySelector('.student-list');
    const semesterFilter = document.getElementById('semester');
    const branchFilter = document.getElementById('branch');
    const sectionFilter = document.getElementById('section');

    // Function to fetch and display students based on filters
    function fetchStudents() {
        const filters = {
            semester: semesterFilter.value,
            branch: branchFilter.value,
            section: sectionFilter.value
        };

        fetch('/attendance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(filters)
        })
        .then(response => response.json())
        .then(data => {
            studentList.innerHTML = '';
            data.students.forEach(student => {
                const studentCard = document.createElement('div');
                studentCard.className = 'student-card';
                const title = document.createElement('h3');
                title.textContent = student.name || 'Student';
                const roll = document.createElement('p');
                roll.textContent = `Roll Number: ${student.roll_number || 'N/A'}`;
                const action = document.createElement('button');
                action.className = 'mark-present';
                action.dataset.id = String(student.id);
                action.textContent = 'Mark as Present';
                studentCard.append(title, roll, action);
                studentList.appendChild(studentCard);
            });
        })
        .catch(error => {
            console.error('Error fetching students:', error);
        });
    }

    // Event listeners for filter changes
    semesterFilter.addEventListener('change', fetchStudents);
    branchFilter.addEventListener('change', fetchStudents);
    sectionFilter.addEventListener('change', fetchStudents);

    // Initial fetch of students
    fetchStudents();
}); 