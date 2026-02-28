# Task 09: Browser UI (HTML + CSS + JS)

## Priority: 9
## Depends on: Task 08 (FastAPI server)
## Estimated time: 60-90 min

## Objective

Build the browser-based UI: mic capture, WebSocket communication, audio playback, and a terminal-style interface. Vanilla HTML/JS — no build step, no frameworks.

## What to create

### 1. `ui/index.html`

Single page app structure:
- Header: "VoxaOS" title + connection status indicator (green dot / red dot)
- Main area: scrolling terminal-style log showing transcripts, responses, tool outputs
- Bottom: push-to-talk button (big, centered) + waveform visualizer
- Link to `/ui/style.css` and `/ui/app.js`

### 2. `ui/style.css`

Dark terminal aesthetic:
- Background: `#0d1117` (GitHub dark)
- Monospace font: `'JetBrains Mono', 'Fira Code', 'Consolas', monospace`
- Text colors:
  - User messages: cyan (`#58a6ff`)
  - System responses: green (`#3fb950`)
  - Tool execution: yellow/amber (`#d29922`)
  - Errors: red (`#f85149`)
  - Thinking/status: dim gray (`#8b949e`)
- Push-to-talk button:
  - Large circle, centered at bottom
  - Default: dark gray border
  - Active (held): pulsing green glow + "Listening..." label
  - Processing: amber pulse
  - Speaking: blue pulse
- Scrolling log: auto-scroll to bottom, each entry has a left border color matching its type
- Connection status: small dot in header, green=connected, red=disconnected
- Responsive: works on mobile (button large enough for thumb)

### 3. `ui/app.js`

Browser logic — this is the meaty file:

**WebSocket connection:**
```javascript
const ws = new WebSocket(`ws://${window.location.host}/ws/audio`);
ws.binaryType = 'arraybuffer';

ws.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
        // Binary = TTS audio — queue for playback
        playAudio(event.data);
    } else {
        // JSON = control message
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    }
};
```

**Message handler:**
```javascript
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
            if (msg.tools_used?.length) {
                appendLog('tool', `Tools: ${msg.tools_used.join(', ')}`);
            }
            break;
        case 'state':
            updatePipelineState(msg.pipeline);
            break;
        case 'confirm_request':
            showConfirmDialog(msg.tool_name, msg.args);
            break;
    }
}
```

**Mic capture:**
- `navigator.mediaDevices.getUserMedia({audio: true})`
- Use `AudioWorklet` (preferred) or `ScriptProcessorNode` (fallback)
- Capture at 16kHz mono, convert to int16 PCM
- Send binary frames over WebSocket while push-to-talk is active

**Push-to-talk:**
- Spacebar keydown → send `{"type": "push_to_talk", "state": "start"}`, start sending audio
- Spacebar keyup → send `{"type": "push_to_talk", "state": "stop"}`, stop sending audio
- Also works with mouse/touch on the big button
- Visual feedback: button glows while held

**Audio playback:**
- Use Web Audio API (`AudioContext`)
- Queue incoming binary audio frames
- Play them sequentially (buffer to avoid gaps)
- Decode int16 PCM → Float32 for AudioContext

```javascript
const audioCtx = new AudioContext({sampleRate: 22050});
let audioQueue = [];
let isPlaying = false;

function playAudio(arrayBuffer) {
    const int16 = new Int16Array(arrayBuffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768.0;
    }
    audioQueue.push(float32);
    if (!isPlaying) playNext();
}

function playNext() {
    if (audioQueue.length === 0) { isPlaying = false; return; }
    isPlaying = true;
    const samples = audioQueue.shift();
    const buffer = audioCtx.createBuffer(1, samples.length, 22050);
    buffer.getChannelData(0).set(samples);
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);
    source.onended = playNext;
    source.start();
}
```

**Terminal log:**
```javascript
function appendLog(type, text) {
    const log = document.getElementById('log');
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;

    const prefix = {
        user: '> ',
        assistant: 'VoxaOS: ',
        tool: '  [tool] ',
        thinking: '  ...',
        error: '  [error] ',
    }[type] || '';

    entry.textContent = prefix + text;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}
```

**Text input fallback:**
- Add a text input field at the bottom for testing without mic
- Send via `{"type": "text_input", "text": "..."}`

**Connection status:**
- WebSocket `onopen` → green dot
- WebSocket `onclose`/`onerror` → red dot, attempt reconnect after 3s

## Verification

```bash
python main.py
# Open http://localhost:7860 in Chrome

# Test 1: Text input
#   Type "Hello" in text input → should see response in log

# Test 2: Push-to-talk
#   Hold spacebar, say "What time is it?" → should see transcript + hear response

# Test 3: Connection status
#   Kill server → red dot, restart → auto-reconnect → green dot

# Test 4: Tool execution
#   "List files in this directory" → should see tool output in log
```

## Quality Gate

No Python tests for this task — it's all vanilla JS/HTML/CSS. Use manual checks and a lightweight lint pass.

### Checks

```bash
# Verify files exist
ls -la ui/index.html ui/style.css ui/app.js

# Validate HTML (optional, if html5validator is installed)
# pip install html5validator
# html5validator --root ui/ --also-check-css

# JS lint: check for common issues with a basic grep
# No console.log left in production paths (appendLog is fine):
grep -n "console\.log" ui/app.js || echo "No stray console.logs"

# Verify no hardcoded localhost (should use window.location.host):
grep -n "localhost" ui/app.js | grep -v "//" || echo "OK: no hardcoded localhost"
```

### Manual Browser Checks

| Check | How | Pass? |
|-------|-----|-------|
| Page loads | Open `http://localhost:7860` — no console errors | |
| Dark theme renders | Background is dark, text is colored per type | |
| WebSocket connects | Green dot in header | |
| Text input works | Type "hello", press enter → response appears | |
| Push-to-talk visual | Hold spacebar → button glows green | |
| Log scrolls | Multiple messages auto-scroll to bottom | |
| Mobile responsive | Resize to 375px width — button still usable | |

### Lint the server-side static mount

```bash
ruff check server/app.py
```

| Check | Command | Pass? |
|-------|---------|-------|
| All 3 UI files exist | `ls ui/index.html ui/style.css ui/app.js` | |
| No hardcoded hosts | grep check above | |
| Server serves static | `curl -s http://localhost:7860/ | head -5` returns HTML | |
| CSS linked | `index.html` links to `/ui/style.css` | |
| JS linked | `index.html` links to `/ui/app.js` | |

## Design reference

See PLAN.md sections: Phase 4 (Server + Browser UI), "Architecture" diagram, WebSocket protocol in audio_handler
