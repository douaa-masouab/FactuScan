document.addEventListener('DOMContentLoaded', function () {
    // Voice assistant
    const voiceAssistantBtn = document.getElementById('voice-assistant-btn');
    const voiceAssistantModal = new bootstrap.Modal(document.getElementById('voiceAssistantModal'));
    const recordBtn = document.getElementById('record-btn');
    const voiceStatus = document.getElementById('voice-status');
    const voiceResult = document.getElementById('voice-result');
    const userCommand = document.getElementById('user-command');
    const assistantResponse = document.getElementById('assistant-response');
    const responseAudio = document.getElementById('response-audio');

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    // Open voice assistant modal
    voiceAssistantBtn.addEventListener('click', function () {
        voiceAssistantModal.show();
    });

    // Record button click
    recordBtn.addEventListener('click', function () {
        if (!isRecording) {
            startRecording();
        } else {
            stopRecording();
        }
    });

    // Start recording
    function startRecording() {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    processAudio(audioBlob);
                };

                mediaRecorder.start();
                isRecording = true;

                // Update UI
                recordBtn.innerHTML = '<i class="bi bi-stop-fill"></i> Arrêter';
                recordBtn.classList.remove('btn-primary');
                recordBtn.classList.add('btn-danger');
                voiceStatus.classList.add('recording');
                voiceStatus.querySelector('p').textContent = 'Enregistrement en cours...';
            })
            .catch(error => {
                console.error('Error accessing microphone:', error);
                alert('Impossible d\'accéder au microphone. Veuillez vérifier les permissions.');
            });
    }

    // Stop recording
    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());

            isRecording = false;

            // Update UI
            recordBtn.innerHTML = '<i class="bi bi-mic-fill"></i> Enregistrer';
            recordBtn.classList.remove('btn-danger');
            recordBtn.classList.add('btn-primary');
            voiceStatus.classList.remove('recording');
            voiceStatus.querySelector('p').textContent = 'Traitement en cours...';
        }
    }

    // Process audio
    function processAudio(audioBlob) {
        // Create FormData
        const formData = new FormData();
        formData.append('audio', audioBlob);

        // Send to server for speech-to-text
        fetch('/api/voice/recognize', {
            method: 'POST',
            body: formData
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                const command = data.text || '';

                // Update UI
                userCommand.textContent = command;
                voiceStatus.style.display = 'none';
                voiceResult.style.display = 'block';

                // Process command
                return fetch('/api/voice/command', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        command: command
                    })
                });
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                const response = data.response || '';
                assistantResponse.textContent = response;

                // Synthesize speech
                return fetch('/api/voice/synthesize', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        text: response
                    })
                });
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.audio) {
                    // Create audio element from base64
                    const audioSrc = `data:audio/mp3;base64,${data.audio}`;
                    responseAudio.src = audioSrc;
                    responseAudio.style.display = 'block';
                    responseAudio.play();
                }
            })
            .catch(error => {
                console.error('Error processing voice command:', error);
                voiceStatus.querySelector('p').textContent = 'Erreur lors du traitement. Veuillez réessayer.';

                // Reset UI after delay
                setTimeout(() => {
                    voiceStatus.style.display = 'block';
                    voiceResult.style.display = 'none';
                    voiceStatus.querySelector('p').textContent = 'Cliquez sur le bouton pour parler';
                }, 3000);
            });
    }
});