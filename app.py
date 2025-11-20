import streamlit as st
import asyncio
import edge_tts
import base64
import jieba
import nest_asyncio
from io import BytesIO
from pypinyin import pinyin, Style
from gtts import gTTS

# --- CLOUD FIX: Patch Asyncio Loop ---
# This prevents "RuntimeError: This event loop is already running" on Streamlit Cloud
nest_asyncio.apply()

# --- PAGE CONFIG ---
st.set_page_config(page_title="Mandarin Karaoke Pro", layout="wide")

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("🎛️ Settings")

    # 1. View Mode
    view_mode = st.radio(
        "Display Mode", ["Pinyin Only", "Mandarin + Pinyin (Stacked)"], index=1
    )

    st.divider()

    # 2. Voice Selection
    st.subheader("Audio Config")
    voice_options = {
        "Xiaoxiao (Female - Warm)": "zh-CN-XiaoxiaoNeural",
        "Yunxi (Male - Deep)": "zh-CN-YunxiNeural",
        "Yunyang (Male - News)": "zh-CN-YunyangNeural",
        "Xiaoyi (Female - Digital)": "zh-CN-XiaoyiNeural",
    }
    selected_voice_name = st.selectbox("Voice (Edge-TTS)", options=voice_options.keys())
    selected_voice_code = voice_options[selected_voice_name]

    # 3. Speed Control
    # We use this integer (-50 to 50) for both engines
    speed_val = st.slider("Speaking Rate", -50, 50, 0, 10, format="%d%%")

    # Prepare string for Edge-TTS (e.g., "+10%")
    speed_str_edge = f"{'+' if speed_val >= 0 else ''}{speed_val}%"

    st.info(
        "Note: If Edge-TTS fails (due to cloud blocking), Google Voice will be used automatically."
    )

# --- BACKEND LOGIC ---


def get_karaoke_data(text):
    """
    Segments text using jieba (words) and generates pinyin.
    """
    words = list(jieba.cut(text))
    karaoke_data = []

    for word in words:
        if not word.strip():
            continue

        # Get pinyin for this specific word chunk
        py_result = pinyin(word, style=Style.TONE, heteronym=False)
        py_str = " ".join([item[0] for item in py_result])

        karaoke_data.append({"text": word, "pinyin": py_str})
    return karaoke_data


async def get_audio_base64(text, voice, rate_str):
    """
    Tries Edge-TTS first. If it fails (IP Block/No Audio), falls back to gTTS.
    Returns: (base64_audio_string, engine_name)
    """
    mp3_fp = BytesIO()
    engine_used = "edge"

    # 1. Attempt Edge TTS
    try:
        if not text.strip():
            raise ValueError("Empty Text")

        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_fp.write(chunk["data"])

        # Validate we actually got data
        if mp3_fp.getbuffer().nbytes == 0:
            raise Exception("EdgeTTS returned 0 bytes (likely IP blocked)")

    except Exception as e:
        # 2. Fallback to Google TTS
        print(f"⚠️ EdgeTTS Failed ({e}). Switching to gTTS.")
        st.toast(f"Edge-TTS unavailable ({e}). Using Google Backup.", icon="⚠️")

        engine_used = "google"
        mp3_fp = BytesIO()  # Reset buffer

        # gTTS doesn't support fine-grained server-side speed (we fix this in JS)
        tts = gTTS(text=text, lang="zh-cn", slow=False)
        tts.write_to_fp(mp3_fp)

    mp3_fp.seek(0)
    b64 = base64.b64encode(mp3_fp.read()).decode()
    return f"data:audio/mp3;base64,{b64}", engine_used


# --- FRONTEND COMPONENT ---


def render_karaoke(data_list, audio_data_url, mode, engine, speed_val):
    """
    Renders the HTML/JS component.
    - data_list: Word/Pinyin data
    - engine: 'edge' or 'google'
    - speed_val: The slider value (-50 to 50)
    """

    # --- 1. Calculate Playback Rate for JS ---
    # If Edge: Audio is already physically faster/slower. Browser plays at 1.0.
    # If Google: Audio is normal. Browser must speed it up via .playbackRate.
    if engine == "edge":
        js_rate = 1.0
    else:
        # Convert slider percentage to multiplier (e.g., 20 -> 1.2, -20 -> 0.8)
        js_rate = 1.0 + (speed_val / 100.0)

    # --- 2. Build HTML Structure ---
    html_items = ""
    for i, item in enumerate(data_list):
        hanzi = item["text"]
        py = item["pinyin"]

        if mode == "Mandarin + Pinyin (Stacked)":
            html_items += f"""
            <div id="word-{i}" class="word-unit">
                <div class="hanzi">{hanzi}</div>
                <div class="pinyin">{py}</div>
            </div>
            """
        else:
            html_items += f'<span id="word-{i}" class="word-unit-simple">{py}</span> '

    # --- 3. Build CSS & JS ---
    html_code = f"""
    <style>
        .container {{
            height: 350px;
            overflow-y: auto; /* Enable Vertical Scroll */
            padding: 20px;
            background: #ffffff;
            border: 1px solid #ddd;
            border-radius: 12px;
            display: flex;
            flex-wrap: wrap;
            align-content: flex-start;
            gap: 12px;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);
        }}

        /* Stacked Mode */
        .word-unit {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 6px 10px;
            border-radius: 8px;
            transition: background-color 0.2s ease, transform 0.2s ease;
            cursor: default;
        }}
        .hanzi {{ font-size: 28px; font-weight: bold; color: #2c3e50; line-height: 1.2; }}
        .pinyin {{ font-size: 14px; color: #7f8c8d; }}

        /* Simple Mode */
        .word-unit-simple {{
            font-size: 22px;
            padding: 4px 8px;
            border-radius: 6px;
            transition: all 0.2s ease;
            margin-right: 4px;
            line-height: 2.2;
            display: inline-block;
        }}

        /* Active State (Highlighter) */
        .active {{
            background-color: #FF4B4B;
            transform: scale(1.05);
            box-shadow: 0 4px 10px rgba(255, 75, 75, 0.3);
        }}
        .active .hanzi {{ color: white; }}
        .active .pinyin {{ color: white; }}
        .active.word-unit-simple {{ color: white; background-color: #FF4B4B; }}

        audio {{ width: 100%; margin-top: 15px; }}
    </style>

    <div class="container" id="scroll-box">
        {html_items}
    </div>
    
    <audio id="player" controls autoplay>
        <source src="{audio_data_url}" type="audio/mp3">
    </audio>

    <script>
        const player = document.getElementById('player');
        const totalItems = {len(data_list)};
        let lastIndex = -1;
        
        // --- SPEED HACK ---
        // Enforce playback rate (needed for Google Fallback)
        player.playbackRate = {js_rate};
        player.onplay = () => {{ player.playbackRate = {js_rate}; }};

        player.ontimeupdate = function() {{
            if (player.duration > 0) {{
                // Linear interpolation
                const pct = player.currentTime / player.duration;
                let idx = Math.floor(pct * totalItems);
                if (idx >= totalItems) idx = totalItems - 1;
                
                if (idx !== lastIndex) {{
                    // Remove old highlight
                    if (lastIndex !== -1) {{
                        const oldEl = document.getElementById('word-' + lastIndex);
                        if (oldEl) oldEl.classList.remove('active');
                    }}
                    
                    // Add new highlight
                    const newEl = document.getElementById('word-' + idx);
                    if (newEl) {{
                        newEl.classList.add('active');
                        
                        // --- AUTO SCROLL LOGIC ---
                        newEl.scrollIntoView({{
                            behavior: 'smooth', 
                            block: 'center',
                            inline: 'nearest'
                        }});
                    }}
                    lastIndex = idx;
                }}
            }}
        }};
    </script>
    """

    st.components.v1.html(html_code, height=450)


# --- MAIN UI ---
st.title("🎤 Mandarin Karaoke Trainer")
st.caption("Type Chinese, listen to AI voices, and follow along as the words light up.")

default_text = (
    "我是一个喜欢探索的技术人员。"
    "我喜欢用Python写代码。"
    "这是一个非常有用的工具。"
    "即使网络不好，我们也有备份方案。"
)

text_input = st.text_area("Paste Mandarin Text:", value=default_text, height=120)

if st.button("🚀 Generate & Speak", type="primary", use_container_width=True):
    if text_input:
        with st.spinner("Analyzing text and synthesizing audio..."):
            # 1. Prepare Data (Word Segmentation)
            data = get_karaoke_data(text_input)

            # 2. Generate Audio (Async)
            audio_b64, engine_used = asyncio.run(
                get_audio_base64(text_input, selected_voice_code, speed_str_edge)
            )

            # 3. Render Component
            render_karaoke(data, audio_b64, view_mode, engine_used, speed_val)
