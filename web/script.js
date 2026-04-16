// Selectors
const draftInput = document.getElementById('draft-input');
const toneSelect = document.getElementById('tone-select');
const improveBtn = document.getElementById('improve-btn');

const originalTextDisplay = document.getElementById('original-text');
const improvedTextDisplay = document.getElementById('improved-text');
const outputSubject = document.getElementById('output-subject');
const outputBody = document.getElementById('output-body');
const feedbackList = document.getElementById('feedback-list');
const loadingOverlay = document.getElementById('comparison-loading');

const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const apiUrlInput = document.getElementById('api-url-input');
const modelNameInput = document.getElementById('model-name-input');
const saveSettingsBtn = document.getElementById('save-settings');
const closeModalBtn = document.getElementById('close-modal');

// AI Config
let apiUrl = localStorage.getItem('ollama_api_url') || 'http://localhost:11434';
let modelName = localStorage.getItem('ollama_model_name') || 'llama3';

const getSystemPrompt = (tone) => `
You are "Whetstone AI", a Professional Writing Coach.
Your goal is to improve the user's draft text using a ${tone} tone.

CRITICAL INSTRUCTION:
You MUST respond ONLY with a valid JSON object. Do not include markdown code blocks, conversational filler, or anything outside the JSON structure.

The JSON object must have exactly these keys:
{
  "subject": "A brief, clear subject line for the text (if applicable, else a title)",
  "improved_version": "The fully rewritten text in the ${tone} tone",
  "feedback": [
    "Explanation of change 1",
    "Explanation of change 2"
  ]
}
`;

// Initialization
function initAI() {
    if (!localStorage.getItem('ollama_api_url')) {
        showModal();
    }
}

// Extract JSON from response (in case the LLM wraps it in markdown)
function extractJSON(text) {
    try {
        // Try parsing directly first
        return JSON.parse(text);
    } catch (e) {
        // If it fails, try to extract from markdown code blocks
        const match = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
        if (match && match[1]) {
            return JSON.parse(match[1]);
        }
        throw new Error("Could not parse JSON from response");
    }
}

// API Call
async function improveDraft() {
    const text = draftInput.value.trim();
    if (!text) {
        alert("Please enter a draft to improve.");
        return;
    }

    const tone = toneSelect.value;
    
    // Update UI Loading State
    improveBtn.disabled = true;
    loadingOverlay.style.display = 'flex';
    
    // Clear previous results
    originalTextDisplay.textContent = text;
    improvedTextDisplay.textContent = "";
    outputSubject.textContent = "";
    outputBody.textContent = "";
    feedbackList.innerHTML = "";

    const userMessage = { role: 'user', content: text };
    const systemPromptMessage = { role: 'system', content: getSystemPrompt(tone) };

    try {
        const response = await fetch(apiUrl + '/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: modelName,
                messages: [systemPromptMessage, userMessage],
                stream: false,
                format: "json" // Tell Ollama to expect/enforce JSON if supported
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        const aiText = result.message.content;
        
        try {
            const parsedData = extractJSON(aiText);
            
            // Populate UI
            improvedTextDisplay.textContent = parsedData.improved_version;
            outputSubject.textContent = parsedData.subject;
            outputBody.textContent = parsedData.improved_version;
            
            if (parsedData.feedback && Array.isArray(parsedData.feedback)) {
                parsedData.feedback.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = item;
                    feedbackList.appendChild(li);
                });
            } else {
                feedbackList.innerHTML = "<li>No specific feedback provided.</li>";
            }
            
        } catch (parseError) {
            console.error("JSON Parse Error:", parseError, "Raw output:", aiText);
            alert("The AI generated an invalid format. Please try again.");
            improvedTextDisplay.textContent = aiText; // dump raw text as fallback
        }

    } catch (error) {
        console.error("Ollama API Error:", error);
        alert("Could not connect to the AI server. Please check your Ollama settings.");
    } finally {
        improveBtn.disabled = false;
        loadingOverlay.style.display = 'none';
    }
}

// Modal logic
function showModal() { settingsModal.classList.add('active'); }
function hideModal() { settingsModal.classList.remove('active'); }

// Event Listeners
improveBtn.addEventListener('click', improveDraft);

settingsBtn.addEventListener('click', showModal);
closeModalBtn.addEventListener('click', hideModal);

saveSettingsBtn.addEventListener('click', () => {
    const newUrl = apiUrlInput.value.trim();
    const newModel = modelNameInput.value.trim();
    if (newUrl && newModel) {
        localStorage.setItem('ollama_api_url', newUrl);
        localStorage.setItem('ollama_model_name', newModel);
        apiUrl = newUrl;
        modelName = newModel;
        hideModal();
    }
});

// Start
if (localStorage.getItem('ollama_api_url')) {
    apiUrlInput.value = localStorage.getItem('ollama_api_url');
}
if (localStorage.getItem('ollama_model_name')) {
    modelNameInput.value = localStorage.getItem('ollama_model_name');
}
initAI();
