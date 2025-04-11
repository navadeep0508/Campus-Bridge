require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.21.2/min/vs' }});
require(['vs/editor/editor.main'], function() {
    var editor = monaco.editor.create(document.getElementById('editor'), {
        value: '// Write your code here\n',
        language: 'javascript',
        theme: 'vs-light',
        automaticLayout: true
    });

    document.getElementById('submit').addEventListener('click', function() {
        var code = editor.getValue();
        var language = document.getElementById('language').value;
        var input = document.getElementById('custom-input').value;

        fetch('/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                code: code,
                language: language,
                input: input
            })
        })
        .then(response => response.json())
        .then(data => {
            const output = data.stdout || data.stderr || 'No output available';
            document.getElementById('output').innerText = output;
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('output').innerText = 'Error executing code';
        });
    });
}); 