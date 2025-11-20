import streamlit as st
import nest_asyncio
import asyncio
import edge_tts
import base64
import jieba
from io import BytesIO
from pypinyin import pinyin, Style
from gtts import gTTS



nest_asyncio.apply()
# Page Config
st.set_page_config(page_title="Mandarin Karaoke Pro", layout="wide")

# --- 1. Sidebar Controls ---
with st.sidebar:
    st.header("🎛️ Settings")

    # View Mode Selector
    view_mode = st.radio(
        "Display Mode", ["Pinyin Only", "Mandarin + Pinyin (Stacked)"], index=1
    )

    st.divider()
    st.subheader("Audio Config")

    voice_options = {
        "Xiaoxiao (Female - Warm)": "zh-CN-XiaoxiaoNeural",
        "Yunxi (Male - Deep)": "zh-CN-YunxiNeural",
        "Yunyang (Male - News)": "zh-CN-YunyangNeural",
    }
    selected_voice_name = st.selectbox("Voice", options=voice_options.keys())
    selected_voice_code = voice_options[selected_voice_name]

    speed_val = st.slider("Rate", -50, 50, 0, 10, format="%d%%")
    speed_str = f"{'+' if speed_val >= 0 else ''}{speed_val}%"

# --- 2. Backend Logic ---


def get_karaoke_data(text):
    """
    Uses jieba to segment text into words, then matches them with Pinyin.
    Returns a list of dicts: [{'text': '我们', 'pinyin': 'wǒ men'}, ...]
    """
    # 1. Cut text into semantic words (e.g., "我", "喜欢", "Python")
    words = list(jieba.cut(text))

    karaoke_data = []

    for word in words:
        # Skip pure whitespace to avoid empty highlights
        if not word.strip():
            continue

        # Convert this specific word chunk to pinyin
        # heteronym=False ensures we get the most likely sound
        py_result = pinyin(word, style=Style.TONE, heteronym=False)

        # Flatten the result (e.g., [['wǒ'], ['men']] -> "wǒ men")
        py_str = " ".join([item[0] for item in py_result])

        karaoke_data.append({"text": word, "pinyin": py_str})

    return karaoke_data


async def get_audio_base64(text, voice, rate):
    mp3_fp = BytesIO()

    try:
        # --- ATTEMPT 1: Edge TTS (High Quality) ---
        # Note: edge-tts doesn't like empty strings, check first
        if not text.strip():
            raise ValueError("Text is empty")

        communicate = edge_tts.Communicate(text, voice, rate=rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_fp.write(chunk["data"])

        # Check if we actually got data
        if mp3_fp.getbuffer().nbytes == 0:
            raise Exception("EdgeTTS returned 0 bytes (IP Blocked?)")

    except Exception as e:
        # --- ATTEMPT 2: Fallback to Google TTS (Standard Quality) ---
        # Log the error to your console so you know it happened
        print(f"⚠️ EdgeTTS failed: {e}. Switching to Google Backup.")

        # Reset buffer just in case
        mp3_fp = BytesIO()

        # gTTS doesn't support specific voices/speed the same way
        # We use 'zh-cn' for Mandarin
        tts = gTTS(text=text, lang="zh-cn")
        tts.write_to_fp(mp3_fp)

        # Notify user in UI (Optional)
        st.toast("Using Backup Voice (Microsoft Service Busy)", icon="⚠️")

    mp3_fp.seek(0)
    b64 = base64.b64encode(mp3_fp.read()).decode()
    return f"data:audio/mp3;base64,{b64}"


# --- 3. The Component ---
def render_karaoke(data_list, audio_data_url, mode):
    # Generate HTML based on mode
    html_items = ""

    for i, item in enumerate(data_list):
        hanzi = item["text"]
        py = item["pinyin"]

        if mode == "Mandarin + Pinyin (Stacked)":
            # Stacked Layout (Flexbox Column)
            html_items += f"""
            <div id="word-{i}" class="word-unit">
                <div class="hanzi">{hanzi}</div>
                <div class="pinyin">{py}</div>
            </div>
            """
        else:
            # Simple Layout (Just Pinyin)
            html_items += f'<span id="word-{i}" class="word-unit-simple">{py}</span> '

    # CSS Styling
    css = """
    <style>
        .container {
            height: 350px;
            overflow-y: auto;
            padding: 20px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 10px;
            display: flex;
            flex-wrap: wrap;
            align-content: flex-start; /* Pack lines to top */
            gap: 10px; /* Space between words */
        }

        /* --- Stacked Mode Styles --- */
        .word-unit {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 5px 8px;
            border-radius: 6px;
            transition: all 0.2s ease;
            cursor: default;
        }
        .hanzi {
            font-size: 28px;
            font-weight: bold;
            color: #333;
            line-height: 1.2;
        }
        .pinyin {
            font-size: 14px;
            color: #666;
        }

        /* --- Simple Mode Styles --- */
        .word-unit-simple {
            font-size: 22px;
            padding: 2px 5px;
            border-radius: 4px;
            transition: all 0.2s ease;
            margin-right: 5px;
            line-height: 2.0;
        }

        /* --- Active State (The "Karaoke" Effect) --- */
        .active {
            background-color: #ff4b4b; /* Background highlight */
            transform: scale(1.1);
        }
        
        /* Change text color inside active unit */
        .active .hanzi { color: white; }
        .active .pinyin { color: white; }
        .active.word-unit-simple { 
            color: white; 
            background-color: #ff4b4b;
        }
    </style>
    """

    # JS Logic (Same logic, just targets .word-unit)
    js = f"""
    <script>
        const player = document.getElementById('player');
        const totalItems = {len(data_list)};
        let lastIndex = -1;
        
        player.ontimeupdate = function() {{
            if (player.duration > 0) {{
                const pct = player.currentTime / player.duration;
                let idx = Math.floor(pct * totalItems);
                if (idx >= totalItems) idx = totalItems - 1;
                
                if (idx !== lastIndex) {{
                    // Remove old
                    if (lastIndex !== -1) {{
                        const oldEl = document.getElementById('word-' + lastIndex);
                        if (oldEl) oldEl.classList.remove('active');
                    }}
                    // Add new
                    const newEl = document.getElementById('word-' + idx);
                    if (newEl) {{
                        newEl.classList.add('active');
                        newEl.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                    }}
                    lastIndex = idx;
                }}
            }}
        }};
    </script>
    """

    full_html = f"""
    {css}
    <div class="container" id="scroll-box">
        {html_items}
    </div>
    <audio id="player" controls autoplay style="width:100%; margin-top:15px;">
        <source src="{audio_data_url}" type="audio/mp3">
    </audio>
    {js}
    """

    st.components.v1.html(full_html, height=450)


# --- 4. Main UI ---
st.title("🎤 Mandarin Mastery")

default_text = "我喜欢用Python写代码。这是一个非常有用的工具。"
text_input = st.text_area("Paste Mandarin Text:", default_text, height=100)

if st.button("🚀 Start Learning", type="primary"):
    if text_input:
        with st.spinner("Processing text and audio..."):
            # 1. Get structured data (Word + Pinyin)
            data = get_karaoke_data(text_input)

            # 2. Generate Audio
            audio_b64 = asyncio.run(
                get_audio_base64(text_input, selected_voice_code, speed_str)
            )

            # 3. Render
            render_karaoke(data, audio_b64, view_mode)
