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
                studentCard.innerHTML = `
                    <h3>${student.name}</h3>
                    <p>Roll Number: ${student.roll_number}</p>
                    <button class="mark-present" data-id="${student.id}">Mark as Present</button>
                `;
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