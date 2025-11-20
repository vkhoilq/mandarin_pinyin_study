import streamlit as st
import asyncio
import edge_tts
from io import BytesIO
from pypinyin import pinyin, Style

# Page Config
st.set_page_config(page_title="Mandarin Voice Trainer", layout="centered")
st.title("🇨🇳 Mandarin Paragraph to Speech")
st.markdown("Convert text to Pinyin and listen to **Neural AI Voices**.")

# --- 1. Sidebar Settings ---
with st.sidebar:
    st.header("Audio Settings")

    # Voice Selection
    voice_options = {
        "Xiaoxiao (Female - Warm)": "zh-CN-XiaoxiaoNeural",
        "Yunxi (Male - Deep)": "zh-CN-YunxiNeural",
        "Xiaoyi (Female - Digital)": "zh-CN-XiaoyiNeural",
        "Yunjian (Male - Sports/Loud)": "zh-CN-YunjianNeural",
        "Yunyang (Male - News)": "zh-CN-YunyangNeural",
    }
    selected_voice_name = st.selectbox("Select Voice", options=voice_options.keys())
    selected_voice_code = voice_options[selected_voice_name]

    # Speed Control
    # edge-tts accepts strings like "+50%", "-10%"
    speed_val = st.slider(
        "Speaking Rate", min_value=-50, max_value=50, value=0, step=10, format="%d%%"
    )
    speed_str = f"{'+' if speed_val >= 0 else ''}{speed_val}%"

    st.divider()
    st.header("Text Settings")
    pinyin_mode = st.radio("Pinyin Format", ["Marks (nǐ hǎo)", "Numbers (ni3 hao3)"])


# --- 2. Async Logic ---
async def generate_audio_stream(text, voice, rate):
    """
    Generates audio using edge-tts and writes it to an in-memory buffer.
    """
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    audio_buffer = BytesIO()

    # Iterate over the async stream
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])

    # Reset pointer to start of buffer so Streamlit can read it
    audio_buffer.seek(0)
    return audio_buffer


# --- 3. Main Interface ---
text_input = st.text_area(
    "Enter Mandarin Text:",
    height=150,
    placeholder="Paste Chinese text here... (e.g. 今天的代码写得很开心)",
)

if text_input:
    # A. Pinyin Conversion
    # Determine style based on sidebar selection
    style = Style.TONE if "Marks" in pinyin_mode else Style.TONE3

    # Convert
    pinyin_list = pinyin(text_input, style=style, heteronym=False)
    pinyin_text = " ".join([item[0] for item in pinyin_list])

    st.subheader("📖 Pinyin Reading")
    st.info(pinyin_text)

    # B. Audio Generation
    st.subheader("🎧 Neural Audio")

    # We use a button to prevent API calls on every keystroke
    if st.button("Generate Audio", type="primary", use_container_width=True):
        with st.spinner(
            f"Synthesizing voice ({selected_voice_name} at {speed_str})..."
        ):
            try:
                # Bridge Async to Sync
                audio_data = asyncio.run(
                    generate_audio_stream(text_input, selected_voice_code, speed_str)
                )

                # Display Player
                st.audio(audio_data, format="audio/mp3")
                st.success("Audio generated successfully!")

            except Exception as e:
                st.error(f"Failed to generate audio. Error: {e}")
