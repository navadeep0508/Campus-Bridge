document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('.attendance-table');
    form.addEventListener('submit', function(event) {
        event.preventDefault();

        const formData = new FormData(form);
        const attendanceData = {};

        formData.forEach((value, key) => {
            attendanceData[key] = value;
        });

        fetch('/attendance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(attendanceData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Attendance submitted successfully!');
            } else {
                alert('Failed to submit attendance.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while submitting attendance.');
        });
    });
}); 