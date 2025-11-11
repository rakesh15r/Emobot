#!/usr/bin/env python3
# emobot_xavier.py
# Records audio, runs STT, emotion classification and LLM response on the Xavier (or Jetson).
# Put this file in the same folder as emotionResponse.py which must provide:
#   - stt(audio_path) -> str
#   - emotion_classification(audio_path, transcript) -> str
#   - response_llama(transcript, emotion) -> str

import time
import os
import sys
import pyttsx3
import sounddevice as sd
import soundfile as sf
import numpy as np

# Import your pipeline functions from emotionResponse.py
from emotionResponse import stt, emotion_classification, response_llama

# -------- CONFIG --------
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = None        # None uses default audio device; set to 'hw:1,0' or an index if needed
DTYPE = 'int16'     # common device dtype; change to 'float32' if your device requires it

RECORD_DURATION = 4        # seconds to record user reply
AUDIO_FILENAME = "user_voice.wav"

# -------------------------

def speak_text(text):
    """Simple TTS using pyttsx3."""
    print(f"[TTS] {text}")
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print("[TTS] Error:", e)

def record_audio(filename, duration=3):
    """Record audio to `filename` with configured SAMPLE_RATE and CHANNELS."""
    print(f"[Audio] Recording {duration}s -> {filename}")
    try:
        # record
        frames = int(duration * SAMPLE_RATE)
        audio_data = sd.rec(frames, samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype=DTYPE, device=DEVICE)
        sd.wait()

        # convert integer to float32 normalized if needed (soundfile can write int16 too,
        # but many downstream STT / feature extractors expect float32 PCM -1..1)
        if np.issubdtype(audio_data.dtype, np.integer):
            # integer dtype (e.g., int16) -> normalize to float32
            maxval = np.iinfo(audio_data.dtype).max
            audio_float = audio_data.astype(np.float32) / float(maxval)
        else:
            audio_float = audio_data.astype(np.float32)

        # ensure shape is (N, channels) for soundfile
        sf.write(filename, audio_float, SAMPLE_RATE, format='WAV')
        print("[Audio] Saved:", filename)
    except Exception as e:
        print("[Audio] Recording failed:", e)
        raise

def main_loop():
    print("[Main] Starting audio -> STT -> emotion -> LLM loop. Ctrl+C to stop.")
    try:
        while True:
            # 1) Speak prompt
            prompt_text = "Hi, how are you doing?"
            speak_text(prompt_text)

            # 2) Record reply
            try:
                record_audio(AUDIO_FILENAME, duration=RECORD_DURATION)
            except Exception:
                speak_text("Sorry, I couldn't record. Let's try again.")
                time.sleep(0.5)
                continue

            # 3) STT
            print("[Main] Running STT...")
            try:
                transcript = stt(AUDIO_FILENAME)
            except Exception as e:
                print("[Main] stt() raised:", e)
                transcript = ""

            if not transcript:
                speak_text("Sorry, I could not understand your voice.")
                time.sleep(0.5)
                continue
            print("[Main] Transcript:", transcript)

            # 4) Emotion classification
            try:
                emotion = emotion_classification(AUDIO_FILENAME, transcript)
            except Exception as e:
                print("[Main] emotion_classification() failed:", e)
                emotion = "unknown"
            print("[Main] Emotion:", emotion)

            # 5) LLM response
            try:
                reply = response_llama(transcript, emotion)
            except Exception as e:
                print("[Main] response_llama() failed:", e)
                reply = "Sorry, I'm having trouble thinking right now."
            print("[Main] Reply:", reply)

            # 6) Speak reply
            speak_text(reply)

            # 7) Stop condition
            if "stop" in reply.lower():
                speak_text("Okay, stopping. Goodbye.")
                break

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[Main] Interrupted by user. Exiting.")

if __name__ == "__main__":
    main_loop()
