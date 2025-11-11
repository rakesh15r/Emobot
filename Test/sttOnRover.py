import sounddevice as sd
import soundfile as sf
import numpy as np
import io
import speech_recognition as sr
import datetime

# ====== Configuration ======
SAMPLE_RATE = 16000        # Matches your arecord rate
CHANNELS = 1               # Mono
DEVICE = 'hw:1,0'          # I2S microphone device
DTYPE = 'int32'            # Match S32_LE
CHUNK_DURATION = 3         # seconds per recognition chunk

# ====== Initialize recognizer ======
recognizer = sr.Recognizer()

def record_chunk(duration=CHUNK_DURATION):
    """Record one chunk of audio from the I2S mic"""
    print(f"🎙 Recording {duration}s chunk...")
    audio_data = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=DEVICE
    )
    sd.wait()
    # Normalize 32-bit data to float32 for recognizer
    audio_float = audio_data.astype(np.float32) / np.iinfo(np.int32).max
    return audio_float

def stt():
    """Convert NumPy audio array to text using SpeechRecognition"""
    # Save to in-memory WAV buffer
    audio_float = record_chunk()
    buf = io.BytesIO()
    sf.write(buf, audio_float, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    # sf.write()
    buf.seek(0)

    # Recognize speech from buffer
    with sr.AudioFile(buf) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio)

        print(f"🗣  {text}")
        return text
    except sr.UnknownValueError:
        print("🤔 Could not understand audio.")
    except sr.RequestError as e:
        print(f"⚠ API request failed: {e}")

def audio_to_text(audio_float):
    """Convert NumPy audio array to text using SpeechRecognition"""
    # Save to in-memory WAV buffer
    audio_float = record_chunk()
    buf = io.BytesIO()
    sf.write(buf, audio_float, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    # sf.write()
    buf.seek(0)

    # Recognize speech from buffer
    with sr.AudioFile(buf) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio)

        print(f"🗣  {text}")
        return text
    except sr.UnknownValueError:
        print("🤔 Could not understand audio.")
    except sr.RequestError as e:
        print(f"⚠ API request failed: {e}")

if __name__ == "__main__":
    print("🧠 Continuous Speech-to-Text started (Ctrl+C to stop)")
    try:
        while True:
            chunk = record_chunk()
            audio_to_text(chunk)
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")