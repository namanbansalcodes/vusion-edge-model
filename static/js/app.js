// Stock-Out Detection Demo - Frontend Logic

const video = document.getElementById('shelfVideo');
const canvas = document.getElementById('frameCanvas');
const pauseBtn = document.getElementById('pauseBtn');
const analyzeBtn = document.getElementById('analyzeBtn');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const prevVideoBtn = document.getElementById('prevVideoBtn');
const nextVideoBtn = document.getElementById('nextVideoBtn');
const videoName = document.getElementById('videoName');
const videoCounter = document.getElementById('videoCounter');

let isProcessing = false;
let autoAnalyze = true; // Always running
const ANALYSIS_INTERVAL = 2000; // Analyze every 2 seconds continuously

// Video playlist management
let currentVideoIndex = 0;
const videoList = window.VIDEO_LIST || [];

// Initialize video navigation
function updateVideoNavigation() {
    // Update counter
    if (videoList.length > 0) {
        videoCounter.textContent = `${currentVideoIndex + 1} / ${videoList.length}`;
        videoName.textContent = videoList[currentVideoIndex].name;
    } else {
        videoCounter.textContent = '0 / 0';
        videoName.textContent = 'No videos available';
    }

    // Disable/enable navigation buttons
    prevVideoBtn.disabled = videoList.length <= 1;
    nextVideoBtn.disabled = videoList.length <= 1;
}

// Switch to a specific video
function switchVideo(index) {
    if (videoList.length === 0) return;

    // Ensure index is within bounds
    currentVideoIndex = ((index % videoList.length) + videoList.length) % videoList.length;

    const wasPlaying = !video.paused;
    const videoSource = document.getElementById('videoSource');

    // Update video source
    videoSource.src = videoList[currentVideoIndex].url;
    video.load();

    // Resume playing if it was playing before
    if (wasPlaying) {
        video.play();
    }

    updateVideoNavigation();

    // Update active marker if markers are initialized
    if (cameraMarkers.length > 0) {
        updateActiveMarker(currentVideoIndex);
    }
}

// Navigate to previous video
function previousVideo() {
    switchVideo(currentVideoIndex - 1);
}

// Navigate to next video
function nextVideo() {
    switchVideo(currentVideoIndex + 1);
}

// Check model status on load
async function checkModelStatus() {
    console.log('Checking model status...');
    try {
        const response = await fetch('/api/model-status/');
        const data = await response.json();
        console.log('Model status:', data);

        if (data.loaded) {
            statusIndicator.className = 'status-ready';
            statusText.textContent = 'Model ready';
            analyzeBtn.disabled = false;

            console.log('Model ready! Starting continuous analysis...');
            // Start continuous analysis immediately
            if (autoAnalyze) {
                setTimeout(() => {
                    console.log('Triggering first frame analysis...');
                    processFrame(); // Immediate first analysis
                }, 1000); // Wait 1 second for video to be ready
                startAutoAnalysis(); // Then continue every 2 seconds
            }
        } else {
            statusIndicator.className = 'status-loading';
            statusText.textContent = 'Loading model';
            console.log('Model not ready, retrying in 2 seconds...');
            setTimeout(checkModelStatus, 2000);
        }
    } catch (error) {
        statusIndicator.className = 'status-error';
        statusText.textContent = 'Model error';
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
    console.log('processFrame called, isProcessing:', isProcessing);
    if (isProcessing) {
        console.log('Already processing, skipping...');
        return;
    }

    isProcessing = true;
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = 'Processing...';

    try {
        console.log('Starting frame analysis...');
        updateStepStatus('paligemma', 'processing');
        updateLogs('paligemma', ['Capturing frame', 'Running detection']);

        // Capture frame
        console.log('Capturing video frame...');
        const frameData = captureFrame();
        console.log('Frame captured, size:', frameData.length);

        // Send to backend
        console.log('Sending frame to backend API...');
        const response = await fetch('/api/process-frame/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ image: frameData })
        });

        console.log('Backend response status:', response.status);
        const result = await response.json();
        console.log('Backend result:', result);

        if (result.success) {
            console.log('Analysis successful!');
            // Update PaliGemma step
            updatePaliGemmaStep(result.steps.paligemma);

            // If stock-out detected, show immediate processing state
            if (result.steps.paligemma.detected_zones && result.steps.paligemma.detected_zones.length > 0) {
                // Show Gemini is processing
                updateStepStatus('gemini', 'processing');
                updateLogs('gemini', ['Agent analyzing stock-out...', 'Deciding actions...']);

                // Show tool calls are pending
                updateStepStatus('functions', 'processing');
                updateLogs('functions', ['Waiting for agent decisions...']);

                // Delay to show processing state, then update with results
                setTimeout(() => {
                    updateGeminiStep(result.steps.gemini);
                    updateFunctionCallsStep(result.steps.function_calls);
                }, 800);
            } else {
                // No stock-out, update immediately
                updateGeminiStep(result.steps.gemini);
                updateFunctionCallsStep(result.steps.function_calls);
            }
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
        analyzeBtn.textContent = 'Analyze Frame';
    }
}

// Update PaliGemma step UI
function updatePaliGemmaStep(data) {
    updateStepStatus('paligemma', data.status);
    updateLogs('paligemma', data.logs);

    const outputDiv = document.getElementById('paligemma-output');

    // Build output with stock-outs and commentary
    let outputHTML = '';

    // Stock-out detection
    if (data.detected_zones.length > 0) {
        const zones = data.detected_zones.map(zone =>
            `<span class="zone-badge">${zone}</span>`
        ).join('');

        outputHTML += `
            <div style="margin-bottom: 12px;">
                <strong style="color: #ff4444;">⚠️ Stock-out detected</strong> (${data.zone_count} zones)
            </div>
            <div style="margin-bottom: 12px;">${zones}</div>
        `;

        document.getElementById('step-paligemma').classList.add('active');
    } else {
        outputHTML += `
            <div style="margin-bottom: 12px;">
                <strong style="color: #00ff00;">✓ No stock-outs</strong>
            </div>
        `;
        document.getElementById('step-paligemma').classList.remove('active');
    }

    // Shelf commentary
    if (data.commentary) {
        outputHTML += `
            <div style="border-top: 1px solid #333; padding-top: 8px; margin-top: 8px; color: #999;">
                <strong style="color: #ccc;">Shelf Observations:</strong><br>
                <span style="font-size: 0.9em;">${data.commentary}</span>
            </div>
        `;
    }

    outputDiv.innerHTML = outputHTML;
}

// Update Gemini step UI with live reasoning
function updateGeminiStep(data) {
    updateStepStatus('gemini', data.status);
    updateLogs('gemini', data.logs);

    const outputDiv = document.getElementById('gemini-output');

    if (data.enabled) {
        if (data.output) {
            let reasoningHTML = '';

            // Display live agent reasoning
            if (data.reasoning && data.reasoning.length > 0) {
                reasoningHTML = `
                    <div style="background: #0a0f1a; border-radius: 8px; padding: 12px; margin-bottom: 12px; border-left: 3px solid #818cf8;">
                        <div style="font-weight: 700; color: #818cf8; margin-bottom: 8px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">
                            🧠 Agent Reasoning (Live)
                        </div>
                        <div style="font-family: monospace; font-size: 11px; line-height: 1.8; color: #e5e7eb;">
                            ${data.reasoning.map((line, index) => `
                                <div style="padding: 4px 0; opacity: 0; animation: fadeInUp 0.4s ease-out ${index * 0.15}s forwards;">
                                    ${line}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }

            // Summary
            const summaryHTML = `
                <div style="padding: 10px; background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 100%); border-radius: 6px; color: #fff; font-weight: 600; font-size: 12px;">
                    ${data.output}
                </div>
            `;

            outputDiv.innerHTML = reasoningHTML + summaryHTML;
            document.getElementById('step-gemini').classList.add('active');
        } else {
            outputDiv.innerHTML = `
                <span class="placeholder">
                    Processing...
                </span>
            `;
        }
    } else {
        outputDiv.innerHTML = `
            <span class="placeholder">
                Skipped
            </span>
        `;
        document.getElementById('step-gemini').classList.remove('active');
    }
}

// Add fadeInUp animation
if (!document.getElementById('agent-animations')) {
    const style = document.createElement('style');
    style.id = 'agent-animations';
    style.textContent = `
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(style);
}

// Update Function Calls step UI - with animations and latest 5 only
function updateFunctionCallsStep(data) {
    updateStepStatus('functions', data.status);
    updateLogs('functions', data.logs);

    const outputDiv = document.getElementById('functions-output');

    if (data.calls && data.calls.length > 0) {
        // Show only latest 5 tool calls
        const latestCalls = data.calls.slice(-5);

        // Clear and animate tool calls appearing one by one
        outputDiv.innerHTML = '';
        document.getElementById('step-functions').classList.add('active');

        // Add each call with staggered animation
        latestCalls.forEach((call, index) => {
            setTimeout(() => {
                const callDiv = document.createElement('div');
                callDiv.className = 'tool-call-item';
                callDiv.style.opacity = '0';
                callDiv.style.transform = 'translateY(10px)';

                // Format the result object nicely
                let resultText = '';
                if (typeof call.result === 'object') {
                    resultText = Object.entries(call.result)
                        .map(([key, value]) => `${key}: ${value}`)
                        .join(', ');
                } else {
                    resultText = call.result;
                }

                callDiv.innerHTML = `
                    <div style="margin-bottom: 12px; padding: 10px; background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); border-radius: 8px; border-left: 3px solid #60a5fa; box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                            <span style="font-size: 16px;">⚡</span>
                            <div style="font-weight: 700; color: #fff; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">
                                ${call.tool || call.name}
                            </div>
                            <div style="margin-left: auto; background: #22c55e; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;">
                                EXECUTED
                            </div>
                        </div>
                        <div style="font-size: 11px; color: #e0e7ff; line-height: 1.6; font-family: monospace;">
                            ${resultText}
                        </div>
                    </div>
                `;

                outputDiv.appendChild(callDiv);

                // Animate in
                setTimeout(() => {
                    callDiv.style.transition = 'all 0.4s ease-out';
                    callDiv.style.opacity = '1';
                    callDiv.style.transform = 'translateY(0)';
                }, 10);
            }, index * 300); // Stagger by 300ms
        });
    } else {
        outputDiv.innerHTML = `
            <span class="placeholder">
                Waiting for agent actions...
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

// Auto-analysis loop - runs continuously
let autoAnalysisInterval;
function startAutoAnalysis() {
    console.log(`Starting auto-analysis loop (every ${ANALYSIS_INTERVAL}ms)`);
    autoAnalysisInterval = setInterval(() => {
        console.log('Auto-analysis tick, isProcessing:', isProcessing);
        if (!isProcessing) {
            processFrame(); // Analyze continuously, even if video is paused
        } else {
            console.log('Skipping analysis - already processing');
        }
    }, ANALYSIS_INTERVAL);
    console.log('Auto-analysis loop started');
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
        pauseBtn.textContent = 'Pause';
        if (autoAnalyze) startAutoAnalysis();
    } else {
        video.pause();
        pauseBtn.textContent = 'Play';
        stopAutoAnalysis();
    }
});

analyzeBtn.addEventListener('click', () => {
    processFrame();
});

// Video navigation event listeners
prevVideoBtn.addEventListener('click', previousVideo);
nextVideoBtn.addEventListener('click', nextVideo);

// Keyboard navigation (left/right arrows)
document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') {
        previousVideo();
    } else if (e.key === 'ArrowRight') {
        nextVideo();
    }
});

// Camera markers management
const cameraMarkersContainer = document.getElementById('cameraMarkers');
const storeMap = document.getElementById('storeMap');
let cameraMarkers = [];

// Generate camera positions on the map
function initializeCameraMarkers() {
    if (!storeMap || !cameraMarkersContainer || videoList.length === 0) return;

    // Clear existing markers
    cameraMarkersContainer.innerHTML = '';
    cameraMarkers = [];

    // Define camera positions (percentage-based for responsiveness)
    const cameraPositions = [
        { x: 20, y: 30 },
        { x: 45, y: 25 },
        { x: 70, y: 35 },
        { x: 30, y: 60 },
        { x: 55, y: 65 },
        { x: 80, y: 70 }
    ];

    // Create markers for each video
    videoList.forEach((video, index) => {
        const position = cameraPositions[index % cameraPositions.length];

        const marker = document.createElement('div');
        marker.className = 'camera-marker';
        marker.style.left = `${position.x}%`;
        marker.style.top = `${position.y}%`;
        marker.dataset.videoIndex = index;

        // Mark first marker as active
        if (index === currentVideoIndex) {
            marker.classList.add('active');
        }

        // Click handler
        marker.addEventListener('click', () => {
            switchVideo(index);
            updateActiveMarker(index);
        });

        cameraMarkersContainer.appendChild(marker);
        cameraMarkers.push(marker);
    });
}

// Update active marker when video changes
function updateActiveMarker(index) {
    cameraMarkers.forEach((marker, i) => {
        if (i === index) {
            marker.classList.add('active');
        } else {
            marker.classList.remove('active');
        }
    });
}

// Initialize on load
window.addEventListener('load', () => {
    console.log('Page loaded, initializing...');
    console.log(`Video list: ${videoList.length} video(s)`);

    // Initialize video navigation
    updateVideoNavigation();

    // Initialize camera markers on the map
    initializeCameraMarkers();

    // Ensure video loops and autoplays
    video.loop = true;
    video.muted = true;

    // Wait for video metadata to load
    video.addEventListener('loadedmetadata', () => {
        console.log('Video metadata loaded:', video.videoWidth, 'x', video.videoHeight);
        console.log('Video ready state:', video.readyState);
    });

    // Start checking model status
    console.log('Starting model status check...');
    checkModelStatus();
});
