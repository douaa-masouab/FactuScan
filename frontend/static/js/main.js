document.addEventListener('DOMContentLoaded', () => {
    const voiceBtn = document.getElementById('voice-assistant-btn');
    const modal = document.getElementById('voice-modal');
    const closeBtn = document.getElementById('close-voice-modal');
    const startBtn = document.getElementById('start-record');
    const status = document.getElementById('voice-status');
    const hint = document.getElementById('voice-hint');
    const conv = document.getElementById('voice-conv');
    const userTxt = document.querySelector('.user-txt');
    const aiTxt = document.querySelector('.ai-txt');

    let recognition;
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SR();
        recognition.lang = 'fr-FR';
        recognition.interimResults = false;

        recognition.onstart = () => {
            status.classList.add('recording');
            hint.textContent = 'Écoute en cours...';
            startBtn.innerHTML = '<i class="bi bi-mic-fill"></i> Parlez maintenant...';
            startBtn.disabled = true;
        };

        recognition.onresult = async (event) => {
            const command = event.results[0][0].transcript;
            userTxt.textContent = "Vous : " + command;
            conv.style.display = 'block';
            status.classList.remove('recording');
            hint.textContent = 'Analyse de votre demande...';

            await processCommand(command);
        };

        recognition.onerror = (event) => {
            status.classList.remove('recording');
            startBtn.disabled = false;
            startBtn.innerHTML = '<i class="bi bi-record-circle"></i> Parler';
            
            if (event.error === 'not-allowed') {
                hint.textContent = "Accès micro refusé. Vérifiez vos paramètres ou l'HTTPS.";
                alert("Erreur: L'accès au micro est bloqué. Note: La reconnaissance vocale nécessite souvent une connexion HTTPS ou d'être sur localhost.");
            } else if (event.error === 'network') {
                hint.textContent = "Erreur réseau. Vérifiez votre connexion.";
            } else {
                hint.textContent = "Erreur: " + event.error;
            }
        };

        recognition.onend = () => {
            status.classList.remove('recording');
            if (startBtn.disabled) {
                startBtn.disabled = false;
                startBtn.innerHTML = '<i class="bi bi-record-circle"></i> Parler';
            }
        };
    }

    voiceBtn.addEventListener('click', () => {
        modal.style.display = 'flex';
        conv.style.display = 'none';
        hint.textContent = 'Dites "Résumé" ou "Total"';
    });

    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    startBtn.addEventListener('click', () => {
        if (recognition) {
            recognition.start();
        } else {
            alert("Votre navigateur ne supporte pas la reconnaissance vocale.");
        }
    });

    async function processCommand(text) {
        try {
            // 1. Get AI response
            const response = await fetch('/voice/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: text })
            });
            const data = await response.json();
            aiTxt.textContent = "Assistant : " + data.response;
            hint.textContent = "Prêt";

            // 2. Synthesize & Play
            const synthRes = await fetch('/voice/synthesize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: data.response })
            });
            const synthData = await synthRes.json();

            if (synthData.audio) {
                const audio = new Audio("data:audio/mp3;base64," + synthData.audio);
                audio.play();
            }
        } catch (e) {
            console.error(e);
            aiTxt.textContent = "Désolé, une erreur est survenue.";
        }
    }
});