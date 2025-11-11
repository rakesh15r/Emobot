import pvporcupine
import sounddevice as sd
import soundfile as sf
import numpy as np
import io
import speech_recognition as sr
import webrtcvad
import time
import os

# ====== CONFIGURATION ======
WAKE_WORD = "jarvis"
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'         # Check with `python3 -m sounddevice`
DTYPE = 'float32'         # Jetson I²S mics usually output float32
FRAME_DURATION = 30       # 10, 20, or 30 ms
VAD_SENSITIVITY = 2       # 0–3 (3 = most sensitive)
SILENCE_LIMIT = 1.0       # seconds of silence before stop
SAVE_PATH = "command.wav" # File to overwrite for every command

# ====== INITIALIZE ======
recognizer = sr.Recognizer()
porcupine = pvporcupine.create(
    access_key="6ZxVPO4M7eURSKhjbfUVBKzCYQHEPEUAvh+zkaFQsUr5mSfkMcrF1w==",
    keywords=["jarvis"]
)
FRAME_LENGTH = porcupine.frame_length
vad = webrtcvad.Vad(VAD_SENSITIVITY)

print(f"🎧 Listening for wake word: '{WAKE_WORD}'... (Frame length: {FRAME_LENGTH})")

# ====== FUNCTION: AUTO GAIN CONTROL ======
def auto_gain(audio_float):
    rms = np.sqrt(np.mean(audio_float ** 2))
    target_rms = 0.1  # target loudness level
    if rms > 0:
        gain = target_rms / rms
        gain = np.clip(gain, 1.0, 4.0)  # prevent overboost
        audio_float *= gain
    return np.clip(audio_float, -1.0, 1.0)

# ====== FUNCTION: RECORD UNTIL SILENCE ======
def record_until_silence():
    print("🎙 Wake word detected! Listening to your speech...")

    frame_size = int(SAMPLE_RATE * FRAME_DURATION / 1000)
    voiced_frames = []
    recording = False
    silence_counter = 0

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=DEVICE,
        blocksize=frame_size
    ) as stream:
        while True:
            frame, _ = stream.read(frame_size)

            # Convert safely to int16
            if frame.dtype != np.int16:
                pcm16 = np.int16(np.clip(frame.flatten() * 32767, -32768, 32767))
            else:
                pcm16 = frame.flatten()

            raw_bytes = pcm16.tobytes()
            is_speech = vad.is_speech(raw_bytes, SAMPLE_RATE)

            if is_speech:
                if not recording:
                    recording = True
                voiced_frames.append(raw_bytes)
                silence_counter = 0
            elif recording:
                silence_counter += FRAME_DURATION / 1000
                if silence_counter > SILENCE_LIMIT:
                    break

    pcm_concat = b''.join(voiced_frames)
    if not pcm_concat:
        print("⚠️ No speech detected.")
        return None

    # --- Convert and apply soft gain boost ---
    audio_np_int16 = np.frombuffer(pcm_concat, dtype=np.int16)
    audio_np_float = audio_np_int16.astype(np.float32) / 32767.0
    audio_np_float = auto_gain(audio_np_float)
    audio_np_int16 = np.int16(audio_np_float * 32767)

    # --- Normalize volume before saving ---
    max_val = np.max(np.abs(audio_np_int16))
    if max_val > 0:
        audio_np_int16 = np.int16(audio_np_int16 / max_val * 30000)

    sf.write(SAVE_PATH, audio_np_int16, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    print(f"✅ Saved command to '{SAVE_PATH}' (normalized and gain-adjusted)")

    return audio_np_float

# ====== FUNCTION: SPEECH TO TEXT ======
def audio_to_text(audio_float):
    # Normalize amplitude before STT
    max_val = np.max(np.abs(audio_float))
    if max_val > 0:
        audio_float = audio_float / max_val

    buf = io.BytesIO()
    sf.write(buf, audio_float, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    buf.seek(0)
    with sr.AudioFile(buf) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio)
        print(f"💬 You said: {text}")
        return text
    except sr.UnknownValueError:
        print("🤔 Could not understand your speech.")
    except sr.RequestError as e:
        print(f"⚠️ STT request failed: {e}")

# ====== MAIN LOOP ======
stream = None
try:
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=FRAME_LENGTH,
        dtype=DTYPE,
        channels=CHANNELS,
        device=DEVICE
    )
    stream.start()

    while True:
        pcm, _ = stream.read(FRAME_LENGTH)

        # Convert float → int16 for Porcupine
        if pcm.dtype != np.int16:
            pcm16 = np.int16(np.clip(pcm.flatten() * 32767, -32768, 32767))
        else:
            pcm16 = pcm.flatten()

        # Normalize quiet audio for better detection
        if np.mean(np.abs(pcm16)) < 1000:
            pcm16 = np.int16(pcm16 * 5)

        keyword_index = porcupine.process(pcm16)

        if keyword_index >= 0:
            print("💡 Wake word detected!")

            # --- Close wakeword stream ---
            stream.close()

            # --- Record user speech ---
            audio_data = record_until_silence()

            # --- Convert to text ---
            if audio_data is not None and len(audio_data) > 0:
                audio_to_text(audio_data)

            # --- Reopen wakeword stream ---
            print(f"\n🎧 Listening again for wake word: '{WAKE_WORD}'...\n")
            time.sleep(0.2)
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                blocksize=FRAME_LENGTH,
                dtype=DTYPE,
                channels=CHANNELS,
                device=DEVICE
            )
            stream.start()

except KeyboardInterrupt:
    print("\n🛑 Keyboard Interrupt received — releasing microphone...")
finally:
    if stream is not None:
        try:
            stream.stop()
            stream.close()
            print("🎤 Microphone released successfully.")
        except Exception as e:
            print(f"⚠️ Error while closing stream: {e}")
    porcupine.delete()
    print("✅ Porcupine deleted. Exiting gracefully.")
