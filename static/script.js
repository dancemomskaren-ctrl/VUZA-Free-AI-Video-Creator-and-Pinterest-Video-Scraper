console.log("🚀 VUZA v5 — Free AI Video Creator (English)");

document.addEventListener('DOMContentLoaded', () => {
    // ── Elements ──
    const scrapeBtn = document.getElementById('scrape-btn');
    const queryInput = document.getElementById('query');
    const scriptInput = document.getElementById('script');
    const countInput = document.getElementById('count');
    const statusCard = document.getElementById('status-card');
    const statusMsg = document.getElementById('status-msg');
    const statusPercent = document.getElementById('status-percent');
    const progressFill = document.getElementById('progress-fill');
    const galleryContainer = document.getElementById('gallery-container');
    const clearBtn = document.getElementById('clear-gallery');
    const analyzeBtn = document.getElementById('analyze-btn');
    const generateScriptBtn = document.getElementById('generate-script-btn');
    const topicInput = document.getElementById('topic-input');
    const analysisPanel = document.getElementById('analysis-panel');
    const aiTitle = document.getElementById('ai-title');
    const aiDesc = document.getElementById('ai-desc');
    const aiHashtags = document.getElementById('ai-hashtags');
    const aiThumbPrompt = document.getElementById('ai-thumb-prompt');

    const tabSingle = document.getElementById('tab-single');
    const tabScript = document.getElementById('tab-script');
    const singleArea = document.getElementById('single-input-area');
    const scriptArea = document.getElementById('script-input-area');
    const scriptsContainer = document.getElementById('scripts-container');
    const addScriptBtn = document.getElementById('add-script-btn');
    const templateSelect = document.getElementById('template-select');
    const scrapeUrlBtn = document.getElementById('scrape-url-btn');
    const urlInput = document.getElementById('url-input');

    let currentMode = 'single';
    let statusInterval = null;
    let finalVideoUrl = '';
    let pollConnectionErrorShown = false;

    // ═══ SETTINGS PANEL TOGGLE ═══
    const settingsToggle = document.getElementById('settings-toggle');
    const settingsBody = document.getElementById('settings-body');
    const settingsPanel = document.getElementById('settings-panel');

    if (settingsToggle) {
        settingsToggle.addEventListener('click', () => {
            settingsBody.classList.toggle('hidden');
            settingsPanel.classList.toggle('open');
        });
    }

    // ═══ LOAD SAVED KEYS FROM localStorage ═══
    function loadKeys() {
        const keys = JSON.parse(localStorage.getItem('vuza_api_keys') || '{}');
        if (keys.llm_key) document.getElementById('llm-key').value = keys.llm_key;
        if (keys.llm_url) document.getElementById('llm-url').value = keys.llm_url;
        if (keys.llm_model) document.getElementById('llm-model').value = keys.llm_model;
        if (keys.seedream_key) document.getElementById('seedream-key').value = keys.seedream_key;
        if (keys.seedream_url) document.getElementById('seedream-url').value = keys.seedream_url;
        if (keys.seedream_model) document.getElementById('seedream-model').value = keys.seedream_model;
        if (keys.pexels_key) document.getElementById('pexels-key').value = keys.pexels_key;
        if (keys.pixabay_key) document.getElementById('pixabay-key').value = keys.pixabay_key;
        if (keys.yt_client_id) document.getElementById('yt-client-id').value = keys.yt_client_id;
        if (keys.yt_client_secret) document.getElementById('yt-client-secret').value = keys.yt_client_secret;
        if (keys.eleven_key) document.getElementById('eleven-key').value = keys.eleven_key;
    }

    function saveKeys() {
        const keys = {
            llm_key: document.getElementById('llm-key').value.trim(),
            llm_url: document.getElementById('llm-url').value.trim(),
            llm_model: document.getElementById('llm-model').value.trim(),
            seedream_key: document.getElementById('seedream-key').value.trim(),
            seedream_url: document.getElementById('seedream-url').value.trim(),
            seedream_model: document.getElementById('seedream-model').value.trim(),
            pexels_key: document.getElementById('pexels-key').value.trim(),
            pixabay_key: document.getElementById('pixabay-key').value.trim(),
            yt_client_id: document.getElementById('yt-client-id').value.trim(),
            yt_client_secret: document.getElementById('yt-client-secret').value.trim(),
            eleven_key: document.getElementById('eleven-key').value.trim()
        };
        localStorage.setItem('vuza_api_keys', JSON.stringify(keys));
        showToast('✅ Settings saved', 'success');
    }

    function getKeys() {
        const saved = JSON.parse(localStorage.getItem('vuza_api_keys') || '{}');
        const valueOf = (id) => {
            const el = document.getElementById(id);
            return el ? el.value.trim() : '';
        };
        const current = {
            llm_key: valueOf('llm-key'),
            llm_url: valueOf('llm-url'),
            llm_model: valueOf('llm-model'),
            seedream_key: valueOf('seedream-key'),
            seedream_url: valueOf('seedream-url'),
            seedream_model: valueOf('seedream-model'),
            pexels_key: valueOf('pexels-key'),
            pixabay_key: valueOf('pixabay-key'),
            yt_client_id: valueOf('yt-client-id'),
            yt_client_secret: valueOf('yt-client-secret'),
            eleven_key: valueOf('eleven-key')
        };
        const merged = { ...saved };
        Object.entries(current).forEach(([key, value]) => {
            if (value) merged[key] = value;
        });
        return merged;
    }

    function persistKeys(keys) {
        localStorage.setItem('vuza_api_keys', JSON.stringify(keys));
    }

    async function readErrorMessage(response, fallback) {
        try {
            const err = await response.json();
            const message = err.detail || err.message;
            if (typeof message === 'string') return message;
            if (message) return JSON.stringify(message);
            return fallback;
        } catch (error) {
            return fallback;
        }
    }

    function showApiSettings() {
        if (settingsBody && settingsBody.classList.contains('hidden')) {
            settingsBody.classList.remove('hidden');
            settingsPanel.classList.add('open');
        }
    }

    // Load on start
    loadKeys();

    // Save button
    const saveBtn = document.getElementById('save-keys-btn');
    if (saveBtn) saveBtn.addEventListener('click', saveKeys);

    // ═══ MODE TABS ═══
    if (!tabSingle || !tabScript) return;

    function switchMode(mode) {
        currentMode = mode;
        if (mode === 'single') {
            tabSingle.classList.add('active');
            tabScript.classList.remove('active');
            singleArea.classList.remove('hidden');
            scriptArea.classList.add('hidden');
        } else {
            tabSingle.classList.remove('active');
            tabScript.classList.add('active');
            singleArea.classList.add('hidden');
            scriptArea.classList.remove('hidden');
        }
        updatePrimaryButtonText();
    }

    tabSingle.addEventListener('click', () => switchMode('single'));
    tabScript.addEventListener('click', () => switchMode('script'));

    // ═══ BATCH SCRIPTS ═══
    if (addScriptBtn) {
        addScriptBtn.addEventListener('click', () => {
            const div = document.createElement('div');
            div.className = 'script-item';
            div.innerHTML = `<textarea class="script-input" placeholder="Paste another script for batch generation"></textarea><button type="button" class="remove-script-btn">×</button>`;
            scriptsContainer.appendChild(div);
            div.querySelector('.remove-script-btn').addEventListener('click', () => div.remove());
        });
    }

    // ═══ TEMPLATES ═══
    if (templateSelect) {
        templateSelect.addEventListener('change', () => {
            const template = templateSelect.value;
            const firstScript = scriptsContainer.querySelector('.script-input');
            if (!firstScript) return;

            if (template === 'suspense') {
                firstScript.value = "At 2 AM, my phone buzzed with a text from an unknown number.\nIt said only four words: \"Don't turn around.\"\nBut I live alone.\nThe rain outside suddenly stopped.\nUnder my door, an old photograph slid slowly across the floor.\nIn the photo, I'm standing in this exact room — ten years ago.\nAnd behind me, a blurred figure I've never been able to explain.\nThen my phone lit up again: \"He's already inside.\"";
                document.getElementById('vibe-suspense').checked = true;
                applySuspenseDefaults();
            } else if (template === 'motivational') {
                firstScript.value = "What separates people isn't one big moment of effort.\nIt's what you do when nobody's watching.\nMoving slowly today is fine — just don't stop.\nYou think you barely survived the day, but you're actually getting stronger.";
                document.getElementById('vibe-aesthetic').checked = true;
                document.getElementById('ratio-9-16').checked = true;
            } else if (template === 'educational') {
                firstScript.value = "Did you know honey almost never spoils?\nArchaeologists found 3,000-year-old honey in Egyptian tombs.\nAnd it was still perfectly edible.\nThe reason: honey has low moisture and high acidity, so bacteria can't grow in it.";
                document.getElementById('vibe-general').checked = true;
                document.getElementById('ratio-16-9').checked = true;
            } else if (template === 'storytelling') {
                firstScript.value = "The old bookstore only opened on rainy nights.\nOn the deepest shelf, a girl found an atlas with no title.\nThe moment she opened it, the clock behind the counter stopped.\nAnd in the center of the map, her home address slowly appeared.";
                document.getElementById('vibe-aesthetic').checked = true;
                document.getElementById('ratio-9-16').checked = true;
            } else if (template === 'lofi_vibes') {
                firstScript.value = "Midnight rain tapping on the window.\nA warm cup of coffee still steaming on the desk.\nCity lights blurring into the distance.\nFor once, the world feels quiet.";
                document.getElementById('vibe-lofi').checked = true;
                document.getElementById('ratio-9-16').checked = true;
            } else if (template === 'news') {
                firstScript.value = "Breaking: scientists have identified an exoplanet that could support life.\nIt sits about twenty light-years away, orbiting a red dwarf star.\nThe team is now checking for water and atmosphere.\nThis discovery could reshape how we think about habitable worlds.";
                document.getElementById('vibe-general').checked = true;
                document.getElementById('ratio-16-9').checked = true;
                document.getElementById('subtitle-style').value = 'yellow_box';
            } else if (template === 'tutorial') {
                firstScript.value = "Three steps to a better pour-over coffee.\nStep one: grind your beans to a medium-fine consistency.\nStep two: keep the water between 92 and 95 degrees Celsius.\nStep three: pour in slow circles and let the flavor bloom.";
                document.getElementById('vibe-general').checked = true;
                document.getElementById('ratio-9-16').checked = true;
                document.getElementById('subtitle-style').value = 'bold_outline';
            }
            if (template) showToast('✅ Template loaded', 'success');
        });
    }

    // ═══ DYNAMIC VOICES ═══
    const languageSelect = document.getElementById('language-select');
    const voiceSelect = document.getElementById('voice-select');

    const voiceMap = {
        'en-US': [
            { name: '🇺🇸 Christopher (male)', value: 'en-US-ChristopherNeural' },
            { name: '🇺🇸 Jenny (female)', value: 'en-US-JennyNeural' },
            { name: '🇺🇸 Guy (male)', value: 'en-US-GuyNeural' },
            { name: '🇺🇸 Aria (female)', value: 'en-US-AriaNeural' },
            { name: '🌟 Adam (ElevenLabs)', value: 'eleven_pNInz6obpg8ndclQU7Nc' },
            { name: '🌟 Antoni (ElevenLabs)', value: 'eleven_ErXwBPLxhSj618Y4yxKI' },
            { name: '🌟 Bella (ElevenLabs)', value: 'eleven_EXAVITQu4vr4xnSDxMaL' }
        ],
        'en-GB': [
            { name: '🇬🇧 Ryan', value: 'en-GB-RyanNeural' },
            { name: '🇬🇧 Sonia', value: 'en-GB-SoniaNeural' },
            { name: '🇬🇧 Libby', value: 'en-GB-LibbyNeural' },
            { name: '🇬🇧 Thomas', value: 'en-GB-ThomasNeural' }
        ],
        'es-ES': [
            { name: '🇪🇸 Alvaro', value: 'es-ES-AlvaroNeural' },
            { name: '🇪🇸 Elvira', value: 'es-ES-ElviraNeural' }
        ],
        'fr-FR': [
            { name: '🇫🇷 Henri', value: 'fr-FR-HenriNeural' },
            { name: '🇫🇷 Denise', value: 'fr-FR-DeniseNeural' }
        ],
        'de-DE': [
            { name: '🇩🇪 Conrad', value: 'de-DE-ConradNeural' },
            { name: '🇩🇪 Katja', value: 'de-DE-KatjaNeural' }
        ],
        'it-IT': [
            { name: '🇮🇹 Diego', value: 'it-IT-DiegoNeural' },
            { name: '🇮🇹 Elsa', value: 'it-IT-ElsaNeural' }
        ],
        'hi-IN': [
            { name: '🇮🇳 Madhur', value: 'hi-IN-MadhurNeural' },
            { name: '🇮🇳 Swara', value: 'hi-IN-SwaraNeural' }
        ],
        'ur-PK': [
            { name: '🇵🇰 Asad', value: 'ur-PK-AsadNeural' },
            { name: '🇵🇰 Uzma', value: 'ur-PK-UzmaNeural' }
        ],
        'zh-CN': [
            { name: '🇨🇳 Yunyang (male)', value: 'zh-CN-YunyangNeural' },
            { name: '🇨🇳 Xiaoxiao (female)', value: 'zh-CN-XiaoxiaoNeural' }
        ],
        'ja-JP': [
            { name: '🇯🇵 Keita', value: 'ja-JP-KeitaNeural' },
            { name: '🇯🇵 Nanami', value: 'ja-JP-NanamiNeural' }
        ]
    };

    function updateVoices() {
        const lang = languageSelect.value;
        const voices = voiceMap[lang] || [];
        voiceSelect.innerHTML = voices.map(v => `<option value="${v.value}">${v.name}</option>`).join('') + '<option value="none">🔇 No voiceover (stock media only)</option>';
    }

    function applySuspenseDefaults() {
        const setChecked = (id) => {
            const el = document.getElementById(id);
            if (el) el.checked = true;
        };

        setChecked('src-ai');
        setChecked('type-photo');
        setChecked('ratio-9-16');
        setChecked('emoji-subs-off');

        const suspenseVibe = document.getElementById('vibe-suspense');
        if (suspenseVibe) suspenseVibe.checked = true;

        if (languageSelect) {
            languageSelect.value = 'en-US';
            updateVoices();
        }
        if (voiceSelect) voiceSelect.value = 'en-US-ChristopherNeural';

        const musicSelect = document.getElementById('music-select');
        if (musicSelect) musicSelect.value = 'none';

        const subtitleStyle = document.getElementById('subtitle-style');
        if (subtitleStyle) subtitleStyle.value = 'high_retention';

        if (topicInput) topicInput.placeholder = 'Short topic: a text from a roommate who moved out a year ago. You can also paste a long story and it will be adapted into a full narration script.';
    }

    if (languageSelect) {
        languageSelect.addEventListener('change', updateVoices);
        updateVoices(); // Initial load
    }

    const suspenseVibe = document.getElementById('vibe-suspense');
    if (suspenseVibe) {
        suspenseVibe.addEventListener('change', () => {
            if (suspenseVibe.checked) applySuspenseDefaults();
        });
    }

    applySuspenseDefaults();
    switchMode('script');
    resumeCurrentJob();

    document.querySelectorAll('input[name="source"], input[name="auto_video"]').forEach(input => {
        input.addEventListener('change', updatePrimaryButtonText);
    });

    // ═══ URL SCRAPER ACTION ═══
    if (scrapeUrlBtn) {
        scrapeUrlBtn.addEventListener('click', async () => {
            const url = urlInput.value.trim();
            if (!url) { showToast('Paste an article link first', 'error'); return; }

            const keys = getKeys();
            scrapeUrlBtn.disabled = true;
            scrapeUrlBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Extracting...';

            try {
                const response = await fetch('/api/scrape_url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: url,
                        api_keys: keys
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    const firstScript = scriptsContainer.querySelector('.script-input');
                    if (firstScript) {
                        firstScript.value = data.script;
                        showToast('✅ Extracted and summarized into a script', 'success');
                    }
                } else {
                    showToast(await readErrorMessage(response, 'Extraction failed'), 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            } finally {
                scrapeUrlBtn.disabled = false;
                scrapeUrlBtn.innerHTML = '<i class="fas fa-file-download"></i> Extract script';
            }
        });
    }

    // ═══ AI SCRIPT GENERATOR ACTION ═══
    if (generateScriptBtn) {
        generateScriptBtn.addEventListener('click', async () => {
            const topic = topicInput.value.trim();
            if (!topic) { showToast('Enter a topic or paste long-form source text first', 'error'); return; }

            const keys = getKeys();
            const vibe = document.querySelector('input[name="vibe"]:checked').value;

            if (!keys.llm_key) {
                showApiSettings();
                showToast('Add your AI API key in API Settings first', 'error');
                return;
            }
            persistKeys(keys);

            generateScriptBtn.disabled = true;
            generateScriptBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';

            try {
                const response = await fetch('/api/generate_script', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        topic: topic,
                        vibe: vibe,
                        api_keys: {
                            llm_key: keys.llm_key || '',
                            llm_url: keys.llm_url || 'https://openrouter.ai/api/v1/chat/completions',
                            llm_model: keys.llm_model || ''
                        }
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    const firstScript = scriptsContainer.querySelector('.script-input');
                    if (firstScript) {
                        firstScript.value = data.script;
                        showToast('✅ Script generated', 'success');
                    }
                } else {
                    showToast(await readErrorMessage(response, 'Script generation failed'), 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            } finally {
                generateScriptBtn.disabled = false;
                generateScriptBtn.innerHTML = '<i class="fas fa-magic"></i> Generate script';
            }
        });
    }

    // ═══ AI ANALYSIS ACTION ═══
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', async () => {
            const scripts = Array.from(document.querySelectorAll('.script-input'))
                                .map(s => s.value.trim())
                                .filter(s => s !== "");

            if (scripts.length === 0) { showToast('Enter or generate a script first', 'error'); return; }

            const keys = getKeys();
            if (!keys.llm_key) {
                showApiSettings();
                showToast('Add your AI API key in API Settings first', 'error');
                return;
            }
            persistKeys(keys);
            analyzeBtn.disabled = true;
            analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';

            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        script: scripts[0],
                        api_keys: {
                            llm_key: keys.llm_key || '',
                            llm_url: keys.llm_url || 'https://openrouter.ai/api/v1/chat/completions',
                            llm_model: keys.llm_model || ''
                        }
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    aiTitle.value = data.title;
                    aiDesc.value = data.description;
                    aiHashtags.value = data.hashtags;
                    if (aiThumbPrompt) aiThumbPrompt.value = data.thumbnail_prompt || "";
                    analysisPanel.classList.remove('hidden');
                    showToast('✅ Analysis complete', 'success');
                } else {
                    showToast(await readErrorMessage(response, 'Analysis failed'), 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            } finally {
                analyzeBtn.disabled = false;
                analyzeBtn.innerHTML = '<i class="fas fa-brain"></i> AI Title Analyzer';
            }
        });
    }

    // ═══ MAIN ACTION ═══
    scrapeBtn.addEventListener('click', async () => {
        const query = queryInput ? queryInput.value.trim() : "";

        const scripts = Array.from(document.querySelectorAll('.script-input'))
                            .map(s => s.value.trim())
                            .filter(s => s !== "");

        if (currentMode === 'single' && !query) { showToast('Enter a stock search term first', 'error'); return; }
        if (currentMode === 'script' && scripts.length === 0) { showToast('Enter at least one script', 'error'); return; }

        const source = document.querySelector('input[name="source"]:checked').value;
        const mediaType = document.querySelector('input[name="media_type"]:checked').value;
        const vibe = document.querySelector('input[name="vibe"]:checked').value;
        const count = parseInt(countInput.value);

        const ratio = document.querySelector('input[name="ratio"]:checked').value;
        const language = document.getElementById('language-select').value;
        const voice = document.getElementById('voice-select').value;
        const music = document.getElementById('music-select').value;
        const filter = document.getElementById('filter-select').value;
        const subtitleStyle = document.getElementById('subtitle-style').value;
        const subtitles = document.querySelector('input[name="subtitles"]:checked').value === 'true';
        const autoVideo = document.querySelector('input[name="auto_video"]:checked').value === 'true';
        const ytUpload = document.querySelector('input[name="yt_upload"]:checked').value === 'true';
        const emojiSubtitles = document.querySelector('input[name="emoji_subtitles"]:checked').value === 'true';
        const watermark = document.querySelector('input[name="watermark"]:checked').value === 'true';

        // Get saved API keys
        const keys = getKeys();

        const allowedMusic = new Set(['none', 'cinematic.mp3']);
        if (!allowedMusic.has(music)) {
            showToast('Invalid background music option — pick again', 'error');
            return;
        }

        if (source === 'ai' && mediaType !== 'photo') {
            showToast('AI image mode only supports photos; switch media source for videos', 'error');
            return;
        }

        if (autoVideo && voice === 'none') {
            showToast('Auto video needs an AI voiceover; turn auto-assemble off for a silent render', 'error');
            return;
        }

        if (autoVideo && currentMode === 'single' && source !== 'ai') {
            showToast('A single stock search won\'t auto-assemble a video; switch to script mode or turn auto-assemble off', 'error');
            return;
        }

        if (source === 'ai' && (!keys.llm_key || !keys.seedream_key)) {
            showApiSettings();
            const missing = [];
            if (!keys.llm_key) missing.push('AI text key');
            if (!keys.seedream_key) missing.push('Seedream image key');
            showToast(`Add ${missing.join(' and ')} to use Seedream AI images`, 'error');
            return;
        }

        if (currentMode === 'script' && source !== 'ai' && !keys.llm_key) {
            showApiSettings();
            showToast('Script mode with stock sources needs your AI text key for scene keyword analysis', 'error');
            return;
        }

        setLoading(true);
        finalVideoUrl = '';
        pollConnectionErrorShown = false;
        galleryContainer.innerHTML = '<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>VUZA is working — hang tight...</p></div>';

        try {
            const response = await fetch('/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    script: scripts[0],
                    scripts: scripts, // Send all for batch mode
                    source,
                    media_type: mediaType, count,
                    mode: currentMode, vibe,
                    video_settings: {
                        ratio, voice, subtitles, language,
                        subtitle_style: subtitleStyle, music, filter,
                        emoji_subtitles: emojiSubtitles,
                        watermark: watermark
                    },
                    auto_video: autoVideo,
                    yt_upload: ytUpload,
                    api_keys: {
                        llm_key: keys.llm_key || '',
                        llm_url: keys.llm_url || 'https://openrouter.ai/api/v1/chat/completions',
                        llm_model: keys.llm_model || '',
                        seedream_key: keys.seedream_key || '',
                        seedream_url: keys.seedream_url || 'https://ark.cn-beijing.volces.com/api/v3/images/generations',
                        seedream_model: keys.seedream_model || 'doubao-seedream-4-5-251128',
                        pexels_key: keys.pexels_key || '',
                        pixabay_key: keys.pixabay_key || '',
                        yt_client_id: keys.yt_client_id || '',
                yt_client_secret: keys.yt_client_secret || '',
                eleven_key: keys.eleven_key || ''
                    }
                })
            });

            if (response.ok) {
                showToast('🚀 Generation started', 'success');
                startPollingStatus();
            } else {
                showToast(await readErrorMessage(response, 'Failed to start'), 'error');
                setLoading(false);
            }
        } catch (error) {
            showToast('Network error', 'error');
            setLoading(false);
        }
    });

    function startPollingStatus() {
        statusCard.classList.remove('hidden');
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/status');
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const status = await response.json();
                renderStatus(status);
                if (status.final_video) {
                    finalVideoUrl = status.final_video;
                }
                if ((status.results && status.results.length > 0) || finalVideoUrl) updateGallery(status.results || []);
                if (!status.is_running) {
                    clearInterval(statusInterval);
                    statusInterval = null;
                    setLoading(false);
                    if (isFailureStatus(status)) {
                        showToast(status.error || status.message || 'Generation failed', 'error');
                    } else {
                        showToast('✅ Done', 'success');
                    }
                }
            } catch (err) {
                clearInterval(statusInterval);
                statusInterval = null;
                setLoading(false);
                showServiceConnectionError();
            }
        }, 2000);
    }

    async function resumeCurrentJob() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const status = await response.json();

            if (status.final_video) {
                finalVideoUrl = status.final_video;
            }

            if (status.results && status.results.length > 0) {
                updateGallery(status.results);
            } else if (finalVideoUrl) {
                updateGallery([]);
            }

            if (status.is_running || normalizeProgress(status.progress) > 0 || (status.results && status.results.length > 0)) {
                statusCard.classList.remove('hidden');
                renderStatus(status);
            }

            if (status.is_running) {
                setLoading(true);
                startPollingStatus();
            } else {
                setLoading(false);
            }
        } catch (err) {
            showServiceConnectionError();
        }
    }

    function updateGallery(results) {
        galleryContainer.innerHTML = '';
        renderFinalVideoCard();
        results.forEach(res => {
            const block = document.createElement('div');
            block.className = 'keyword-block';
            let html = `<h3>🔑 ${res.keyword}</h3>`;
            if (res.sentence) html += `<span class="sentence-text">"${res.sentence}"</span>`;
            html += `<div class="gallery-grid">`;
            (res.files || []).forEach(file => {
                const isVideo = /\.(mp4|mov|webm)$/i.test(file);
                if (isVideo) {
                    html += `<div class="media-card"><video src="${file}" preload="metadata" loop muted onmouseover="this.play()" onmouseout="this.pause()"></video><div class="media-actions"><a href="${file}" download class="icon-btn"><i class="fas fa-download"></i></a><span class="badge">Video</span></div></div>`;
                } else {
                    html += `<div class="media-card"><img src="${file}" loading="lazy"><div class="media-actions"><a href="${file}" download class="icon-btn"><i class="fas fa-download"></i></a><span class="badge">HD</span></div></div>`;
                }
            });
            html += `</div>`;
            block.innerHTML = html;
            galleryContainer.appendChild(block);
        });
    }

    function renderFinalVideoCard() {
        if (!finalVideoUrl) return;
        const card = document.createElement('div');
        card.className = 'final-video-card';
        card.innerHTML = `
            <div class="final-video-copy">
                <span class="final-video-kicker"><i class="fas fa-check-circle"></i> Final video ready</span>
                <strong>Download your video</strong>
            </div>
            <a class="final-video-btn" href="${finalVideoUrl}" download>
                <i class="fas fa-download"></i> Download final video
            </a>
        `;
        galleryContainer.appendChild(card);
    }

    clearBtn.addEventListener('click', () => {
        finalVideoUrl = '';
        galleryContainer.innerHTML = '<div class="empty-state"><i class="fas fa-cloud-download-alt"></i><p>Cleared.</p></div>';
        statusCard.classList.add('hidden');
    });

    function updatePrimaryButtonText() {
        const btnText = scrapeBtn.querySelector('.btn-text');
        if (!btnText) return;

        const source = document.querySelector('input[name="source"]:checked')?.value;
        const autoVideo = document.querySelector('input[name="auto_video"]:checked')?.value === 'true';

        if (currentMode === 'script') {
            btnText.textContent = autoVideo ? 'Script → Video' : 'Generate media from script';
        } else if (source === 'ai' && autoVideo) {
            btnText.textContent = 'Topic → Video';
        } else if (source === 'ai') {
            btnText.textContent = 'Generate AI media';
        } else {
            btnText.textContent = 'Search stock media';
        }
    }

    function isFailureStatus(status) {
        const message = status?.message || '';
        return status?.status === 'error' || Boolean(status?.error) || message.trim().startsWith('❌');
    }

    function normalizeProgress(value) {
        const progress = Number(value);
        if (!Number.isFinite(progress)) return 0;
        return Math.min(100, Math.max(0, Math.round(progress)));
    }

    function renderStatus(status) {
        const progress = normalizeProgress(status.progress);
        const failed = isFailureStatus(status);
        statusMsg.textContent = status.error || status.message || (failed ? 'Generation failed' : 'Processing...');
        statusCard.classList.toggle('status-error', failed);
        statusPercent.textContent = `${progress}%`;
        progressFill.style.width = `${progress}%`;
    }

    function showServiceConnectionError() {
        statusCard.classList.remove('hidden');
        statusCard.classList.add('status-error');
        statusMsg.textContent = 'Can\'t reach the backend — make sure the server is still running';
        statusPercent.textContent = '0%';
        progressFill.style.width = '0%';
        if (!pollConnectionErrorShown) {
            showToast('Server connection error — try again shortly', 'error');
            pollConnectionErrorShown = true;
        }
    }

    function setLoading(loading) {
        scrapeBtn.disabled = loading;
        const btnText = scrapeBtn.querySelector('.btn-text');
        const btnLoader = scrapeBtn.querySelector('.btn-loader');
        const btnIcon = scrapeBtn.querySelector('.fa-rocket');
        if (loading) {
            btnText.textContent = 'Processing...';
            if (btnLoader) btnLoader.classList.remove('hidden');
            if (btnIcon) btnIcon.classList.add('hidden');
        } else {
            updatePrimaryButtonText();
            if (btnLoader) btnLoader.classList.add('hidden');
            if (btnIcon) btnIcon.classList.remove('hidden');
        }
    }

    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        if (!toast) return;
        toast.textContent = message;
        toast.className = `toast ${type}`;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3500);
    }
});
