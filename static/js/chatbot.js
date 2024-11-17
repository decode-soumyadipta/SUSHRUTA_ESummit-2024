document.getElementById('send-btn').addEventListener('click', function () {
    const userInput = document.getElementById('user-input').value;
    const messageBox = document.getElementById('messages');
    
    // Display user's message
    const userMessage = document.createElement('div');
    userMessage.className = 'message user-message';
    userMessage.textContent = userInput;
    messageBox.appendChild(userMessage);
    
    // Send the message to the backend
    fetch('/chatbot', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: userInput }),
    })
    .then(response => response.json())
    .then(data => {
        // Display chatbot's response
        const botMessage = document.createElement('div');
        botMessage.className = 'message bot-message';
        botMessage.textContent = data.response;
        messageBox.appendChild(botMessage);
    })
    .catch(error => console.error('Error:', error));
    
    document.getElementById('user-input').value = '';
});
