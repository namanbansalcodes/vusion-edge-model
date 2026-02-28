// Stock-Out Detection Demo - Frontend Logic

const video = document.getElementById('shelfVideo');
const canvas = document.getElementById('frameCanvas');
const pauseBtn = document.getElementById('pauseBtn');
const analyzeBtn = document.getElementById('analyzeBtn');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');

let isProcessing = false;
let autoAnalyze = true;
const ANALYSIS_INTERVAL = 3000; // Analyze every 3 seconds

// Check model status on load
async function checkModelStatus() {
    try {
        const response = await fetch('/api/model-status/');
        const data = await response.json();

        if (data.loaded) {
            statusIndicator.className = 'status-ready';
            statusText.textContent = '✓ Model Ready';
            analyzeBtn.disabled = false;

            // Start auto-analysis if enabled
            if (autoAnalyze) {
                startAutoAnalysis();
            }
        } else {
            statusIndicator.className = 'status-loading';
            statusText.textContent = 'Loading model...';
            // Retry in 2 seconds
            setTimeout(checkModelStatus, 2000);
        }
    } catch (error) {
        statusIndicator.className = 'status-error';
        statusText.textContent = '✗ Model Error';
        console.error('Model status check failed:', error);
    }
}

// Capture current video frame as base64
function captureFrame() {
    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.8);
}

// Process a frame through the ML pipeline
async function processFrame() {
    if (isProcessing) return;

    isProcessing = true;
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = '⏳ Processing...';

    try {
        // Reset workflow UI
        updateStepStatus('paligemma', 'processing');
        updateLogs('paligemma', ['Capturing frame...', 'Running PaliGemma detection...']);

        // Capture frame
        const frameData = captureFrame();

        // Send to backend
        const response = await fetch('/api/process-frame/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ image: frameData })
        });

        const result = await response.json();

        if (result.success) {
            // Update PaliGemma step
            updatePaliGemmaStep(result.steps.paligemma);

            // Update Gemma step
            updateGemmaStep(result.steps.gemma);

            // Update Function Calls step
            updateFunctionCallsStep(result.steps.function_calls);
        } else {
            updateLogs('paligemma', [`Error: ${result.error}`]);
            updateStepStatus('paligemma', 'error');
        }

    } catch (error) {
        console.error('Frame processing failed:', error);
        updateLogs('paligemma', [`Error: ${error.message}`]);
        updateStepStatus('paligemma', 'error');
    } finally {
        isProcessing = false;
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = '🔍 Analyze Current Frame';
    }
}

// Update PaliGemma step UI
function updatePaliGemmaStep(data) {
    updateStepStatus('paligemma', data.status);
    updateLogs('paligemma', data.logs);

    const outputDiv = document.getElementById('paligemma-output');

    if (data.detected_zones.length > 0) {
        const zones = data.detected_zones.map(zone =>
            `<span class="zone-badge">${zone}</span>`
        ).join('');

        outputDiv.innerHTML = `
            <div style="margin-bottom: 10px;">
                <strong>Stock-out detected!</strong> (${data.zone_count} zones)
            </div>
            <div>${zones}</div>
        `;

        // Highlight this step
        document.getElementById('step-paligemma').classList.add('active');
    } else {
        outputDiv.innerHTML = `
            <div style="color: #00ff00;">
                ✓ No stock-outs detected
            </div>
        `;
        document.getElementById('step-paligemma').classList.remove('active');
    }
}

// Update Gemma step UI
function updateGemmaStep(data) {
    updateStepStatus('gemma', data.status);
    updateLogs('gemma', data.logs);

    const outputDiv = document.getElementById('gemma-output');

    if (data.enabled) {
        if (data.output) {
            // Teammate's integration will populate this
            outputDiv.innerHTML = `<div>${data.output}</div>`;
            document.getElementById('step-gemma').classList.add('active');
        } else {
            outputDiv.innerHTML = `
                <span class="placeholder">
                    🔄 Gemma integration pending (teammate)
                </span>
            `;
        }
    } else {
        outputDiv.innerHTML = `
            <span class="placeholder">
                Skipped (no stock-out detected)
            </span>
        `;
        document.getElementById('step-gemma').classList.remove('active');
    }
}

// Update Function Calls step UI
function updateFunctionCallsStep(data) {
    updateStepStatus('functions', data.status);
    updateLogs('functions', data.logs);

    const outputDiv = document.getElementById('functions-output');

    if (data.calls && data.calls.length > 0) {
        const callsList = data.calls.map(call =>
            `<div style="margin-bottom: 8px;">
                <strong>${call.name}</strong>: ${call.result}
            </div>`
        ).join('');
        outputDiv.innerHTML = callsList;
        document.getElementById('step-functions').classList.add('active');
    } else {
        outputDiv.innerHTML = `
            <span class="placeholder">
                No function calls yet
            </span>
        `;
        document.getElementById('step-functions').classList.remove('active');
    }
}

// Helper: Update step status
function updateStepStatus(step, status) {
    const statusElement = document.getElementById(`${step}-status`);
    statusElement.textContent = status.charAt(0).toUpperCase() + status.slice(1);

    // Update visual state
    const stepElement = document.getElementById(`step-${step}`);
    stepElement.classList.remove('active');

    if (status === 'processing') {
        stepElement.style.borderColor = '#ffa500';
    } else if (status === 'complete') {
        stepElement.style.borderColor = '#00ff00';
    } else if (status === 'error') {
        stepElement.style.borderColor = '#ff0000';
    } else {
        stepElement.style.borderColor = 'rgba(255, 255, 255, 0.1)';
    }
}

// Helper: Update logs
function updateLogs(step, logs) {
    const logsDiv = document.getElementById(`${step}-logs`);
    logsDiv.innerHTML = logs.map(log =>
        `<p class="log-entry">${log}</p>`
    ).join('');
}

// Auto-analysis loop
let autoAnalysisInterval;
function startAutoAnalysis() {
    autoAnalysisInterval = setInterval(() => {
        if (!video.paused && !isProcessing) {
            processFrame();
        }
    }, ANALYSIS_INTERVAL);
}

function stopAutoAnalysis() {
    if (autoAnalysisInterval) {
        clearInterval(autoAnalysisInterval);
    }
}

// Event Listeners
pauseBtn.addEventListener('click', () => {
    if (video.paused) {
        video.play();
        pauseBtn.textContent = '⏸️ Pause';
        if (autoAnalyze) startAutoAnalysis();
    } else {
        video.pause();
        pauseBtn.textContent = '▶️ Play';
        stopAutoAnalysis();
    }
});

analyzeBtn.addEventListener('click', () => {
    processFrame();
});

// Initialize on load
window.addEventListener('load', () => {
    checkModelStatus();

    // Wait for video metadata to load
    video.addEventListener('loadedmetadata', () => {
        console.log('Video loaded:', video.videoWidth, 'x', video.videoHeight);
    });
});
