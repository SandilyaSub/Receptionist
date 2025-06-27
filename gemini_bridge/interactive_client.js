document.addEventListener('DOMContentLoaded', () => {
    const connectButton = document.getElementById('connectButton');
    const disconnectButton = document.getElementById('disconnectButton');
    const recordButton = document.getElementById('recordButton');
    const statusArea = document.getElementById('statusArea');
    const audioPlayback = document.getElementById('audioPlayback');
    const transcriptArea = document.getElementById('transcriptArea');

    let websocket = null;
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;
    const serverUrl = `ws://${window.location.host}/ws/gemini_bridge`;

    function updateStatus(message, isError = false) {
        console.log(isError ? `Error: ${message}` : `Status: ${message}`);
        statusArea.innerHTML = `<p style="${isError ? 'color: red;' : ''}">${message}</p>`;
    }

    function appendTranscript(speaker, text) {
        // Clear previous content before adding new
        if (speaker === 'You') {
            transcriptArea.innerHTML = ''; 
        }
        const p = document.createElement('p');
        p.innerHTML = `<strong>${speaker}:</strong> ${text}`;
        transcriptArea.appendChild(p);
        transcriptArea.scrollTop = transcriptArea.scrollHeight; // Auto-scroll
    }

    connectButton.addEventListener('click', () => {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            updateStatus('Already connected.');
            return;
        }

        updateStatus('Connecting to server...');
        websocket = new WebSocket(serverUrl);

        websocket.onopen = () => {
            updateStatus('Connected to server.');
            connectButton.disabled = true;
            disconnectButton.disabled = false;
            recordButton.disabled = false;
        };

        websocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                console.log('Received message:', message);

                if (message.type === 'connection_ack') {
                    updateStatus(message.message);
                } else if (message.type === 'bot_text') {
                    appendTranscript('Bot', message.data);
                } else if (message.type === 'error') {
                    updateStatus(`Server error: ${message.message}`, true);
                }
            } catch (e) {
                updateStatus(`Received non-JSON message: ${event.data}`, true);
            }
        };

        websocket.onerror = (error) => {
            updateStatus('WebSocket error. See console for details.', true);
            console.error('WebSocket Error:', error);
            cleanupConnection();
        };

        websocket.onclose = (event) => {
            updateStatus(`Disconnected. Code: ${event.code}, Reason: ${event.reason || 'N/A'}`);
            cleanupConnection();
        };
    });

    disconnectButton.addEventListener('click', () => {
        if (websocket) {
            websocket.close();
        }
    });

    recordButton.addEventListener('click', () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    async function startRecording() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            updateStatus('Your browser does not support audio recording.', true);
            return;
        }

        updateStatus('Requesting microphone...');
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                updateStatus('Recording finished. Processing and sending...');
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const arrayBuffer = await audioBlob.arrayBuffer();
                
                if (websocket && websocket.readyState === WebSocket.OPEN) {
                    websocket.send(arrayBuffer);
                    updateStatus('Audio sent to server. Waiting for response...');
                } else {
                    updateStatus('Cannot send audio. Not connected to server.', true);
                }
                // Clean up the stream
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            isRecording = true;
            recordButton.textContent = 'Stop Recording';
            recordButton.style.backgroundColor = '#ffc107';
            updateStatus('Recording...');
            appendTranscript('You', '[Speaking...]');

        } catch (err) {
            updateStatus(`Microphone access denied: ${err.message}`, true);
        }
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            isRecording = false;
            recordButton.textContent = 'Start Recording';
            recordButton.style.backgroundColor = '#007bff';
        }
    }

    function cleanupConnection() {
        if (isRecording) {
            stopRecording();
        }
        if (websocket) {
            websocket.onopen = websocket.onmessage = websocket.onerror = websocket.onclose = null;
            if (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING) {
                websocket.close();
            }
            websocket = null;
        }
        connectButton.disabled = false;
        disconnectButton.disabled = true;
        recordButton.disabled = true;
        recordButton.textContent = 'Start Recording';
        recordButton.style.backgroundColor = '#007bff';
        updateStatus('Disconnected.');
    }
});
