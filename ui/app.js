// VoxaOS Browser Client
// WebSocket audio streaming + push-to-talk + terminal log

(function () {
    'use strict';

    // --- DOM refs ---
    const log = document.getElementById('log');
    const statusDot = document.getElementById('status-dot');
    const pipelineState = document.getElementById('pipeline-state');
    const pttBtn = document.getElementById('ptt-btn');
    const pttLabel = document.getElementById('ptt-label');
    const textInput = document.getElementById('text-input');
    const sendBtn = document.getElementById('send-btn');

    // --- State ---
    let ws = null;
    let audioCtx = null;
    let mediaStream = null;
    let audioWorklet = null;
    let scriptProcessor = null;
    let pttActive = false;
    let reconnectTimer = null;
    let reconnectDelay = 1000; // exponential backoff: 1s, 2s, 4s, 8s, max 15s

    // Audio playback queue
    let audioQueue = [];
    let isPlaying = false;

    // --- WebSocket ---
    function connect() {
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }

        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(proto + '//' + window.location.host + '/ws/audio');
        ws.binaryType = 'arraybuffer';

        ws.onopen = function () {
            statusDot.className = 'status-dot connected';
            reconnectDelay = 1000; // reset backoff on successful connect
            appendLog('state', 'Connected to VoxaOS');
        };

        ws.onmessage = function (event) {
            if (event.data instanceof ArrayBuffer) {
                playAudio(event.data);
            } else {
                var msg = JSON.parse(event.data);
                handleMessage(msg);
            }
        };

        ws.onclose = function () {
            statusDot.className = 'status-dot disconnected';
            appendLog('state', 'Disconnected — reconnecting...');
            scheduleReconnect();
        };

        ws.onerror = function () {
            statusDot.className = 'status-dot disconnected';
        };
    }

    function scheduleReconnect() {
        if (!reconnectTimer) {
            reconnectTimer = setTimeout(connect, reconnectDelay);
            reconnectDelay = Math.min(reconnectDelay * 2, 15000); // cap at 15s
        }
    }

    function sendJSON(obj) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(obj));
        }
    }

    function sendBinary(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(data);
        }
    }

    // --- Message handling ---
    function handleMessage(msg) {
        switch (msg.type) {
            case 'transcript':
                appendLog('user', msg.text);
                break;
            case 'thinking':
                appendLog('thinking', msg.text);
                break;
            case 'response':
                appendLog('assistant', msg.text);
                if (msg.tools_used && msg.tools_used.length) {
                    appendLog('tool', 'Tools: ' + msg.tools_used.join(', '));
                }
                break;
            case 'state':
                updatePipelineState(msg.pipeline);
                break;
            case 'error':
                appendLog('error', msg.text || 'Unknown error');
                break;
        }
    }

    function updatePipelineState(state) {
        pipelineState.textContent = state;

        // Update PTT button visual
        pttBtn.className = 'ptt-btn';
        if (state === 'listening') {
            pttBtn.classList.add('listening');
            pttLabel.textContent = 'Listening...';
        } else if (state === 'processing') {
            pttBtn.classList.add('processing');
            pttLabel.textContent = 'Processing...';
        } else if (state === 'speaking') {
            pttBtn.classList.add('speaking');
            pttLabel.textContent = 'Speaking...';
        } else {
            pttLabel.textContent = 'Press & hold to talk';
        }
    }

    // --- Terminal log ---
    function appendLog(type, text) {
        if (!text || !text.trim()) return;

        var entry = document.createElement('div');
        entry.className = 'log-entry log-' + type;

        var prefixes = {
            user: '> ',
            assistant: 'VoxaOS: ',
            tool: '  [tool] ',
            thinking: '  ... ',
            error: '  [error] ',
            state: ''
        };
        var prefix = prefixes[type] || '';
        entry.textContent = prefix + text;
        log.appendChild(entry);
        log.scrollTop = log.scrollHeight;
    }

    // --- Audio playback ---
    function ensureAudioCtx() {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 22050
            });
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
    }

    function playAudio(arrayBuffer) {
        ensureAudioCtx();
        var int16 = new Int16Array(arrayBuffer);
        var float32 = new Float32Array(int16.length);
        for (var i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768.0;
        }
        audioQueue.push(float32);
        if (!isPlaying) playNext();
    }

    function playNext() {
        if (audioQueue.length === 0) {
            isPlaying = false;
            return;
        }
        isPlaying = true;
        var samples = audioQueue.shift();
        var buffer = audioCtx.createBuffer(1, samples.length, 22050);
        buffer.getChannelData(0).set(samples);
        var source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.connect(audioCtx.destination);
        source.onended = playNext;
        source.start();
    }

    // --- Mic capture ---
    async function initMic() {
        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            ensureAudioCtx();
            var micCtx = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });
            var source = micCtx.createMediaStreamSource(mediaStream);

            // Use ScriptProcessorNode (widely supported)
            // bufferSize=4096 gives ~256ms chunks at 16kHz
            scriptProcessor = micCtx.createScriptProcessor(4096, 1, 1);
            scriptProcessor.onaudioprocess = function (e) {
                if (!pttActive) return;
                var float32 = e.inputBuffer.getChannelData(0);
                // Convert float32 -> int16 PCM
                var int16 = new Int16Array(float32.length);
                for (var i = 0; i < float32.length; i++) {
                    var s = Math.max(-1, Math.min(1, float32[i]));
                    int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                sendBinary(int16.buffer);
            };

            source.connect(scriptProcessor);
            scriptProcessor.connect(micCtx.destination);
        } catch (err) {
            appendLog('error', 'Mic access denied: ' + err.message);
        }
    }

    // --- Push-to-talk ---
    function pttStart() {
        if (pttActive) return;
        pttActive = true;
        ensureAudioCtx();
        sendJSON({ type: 'push_to_talk', state: 'start' });
        pttBtn.classList.add('listening');
        pttLabel.textContent = 'Listening...';
    }

    function pttStop() {
        if (!pttActive) return;
        pttActive = false;
        sendJSON({ type: 'push_to_talk', state: 'stop' });
        pttBtn.classList.remove('listening');
        pttLabel.textContent = 'Press & hold to talk';
    }

    // Keyboard: spacebar
    document.addEventListener('keydown', function (e) {
        if (e.code === 'Space' && e.target !== textInput) {
            e.preventDefault();
            pttStart();
        }
    });

    document.addEventListener('keyup', function (e) {
        if (e.code === 'Space' && e.target !== textInput) {
            e.preventDefault();
            pttStop();
        }
    });

    // Mouse/touch on button
    pttBtn.addEventListener('mousedown', function (e) {
        e.preventDefault();
        pttStart();
    });
    pttBtn.addEventListener('mouseup', pttStop);
    pttBtn.addEventListener('mouseleave', pttStop);
    pttBtn.addEventListener('touchstart', function (e) {
        e.preventDefault();
        pttStart();
    });
    pttBtn.addEventListener('touchend', function (e) {
        e.preventDefault();
        pttStop();
    });

    // --- Text input ---
    function sendTextInput() {
        var text = textInput.value.trim();
        if (!text) return;
        appendLog('user', text);
        sendJSON({ type: 'text_input', text: text });
        textInput.value = '';
    }

    textInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendTextInput();
        }
    });

    sendBtn.addEventListener('click', sendTextInput);

    // --- Init ---
    connect();
    initMic();
})();
