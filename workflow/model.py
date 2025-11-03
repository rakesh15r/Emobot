# # -*- coding: utf-8 -*-
# """
# Multimodal Rover Assistant:
# - Records mic audio
# - STT via SeamlessM4T
# - Detects rover commands (forward/back/left/right/stop) with many phrasings
# - If command: acknowledges ("Going back") and optionally sends serial command
# - Else: detects emotion from speech (+ option: face) and responds supportively
# - TTS back to the user
# - Logs interactions to JSONL
# """

# import os
# import json
# import time
# from datetime import datetime
# from typing import Optional, Tuple

# import numpy as np
# import torch

# # Audio / CV
# import pyaudio
# import cv2

# # Serial is optional
# try:
#     import serial  # optional
# except Exception:
#     serial = None

# # HF Transformers
# from transformers import (
#     AutoProcessor,
#     SeamlessM4TModel,
#     AutoFeatureExtractor,
#     AutoModelForAudioClassification,
#     AutoImageProcessor,
#     AutoModelForImageClassification,
# )

# # ----------------------------- Settings -----------------------------

# # Core speech model (STT + TTS in one)
# MODEL_ID = "facebook/hf-seamless-m4t-medium"

# # Audio capture
# SAMPLE_RATE = 16000
# CHANNELS = 1
# RECORD_SECONDS = 5  # change to taste

# # Language codes (ISO-ish for SeamlessM4T)
# SRC_LANG = "eng"  # input text language tag for TTS prompting
# TGT_LANG = "eng"  # output language for STT text & TTS voice

# # Emotion models
# SER_MODEL_ID = "superb/hubert-large-superb-er"   # Speech Emotion Recognition
# FACE_MODEL_ID = "trpakov/vit-face-expression"    # Facial Emotion Recognition (optional)

# # Face / camera
# ENABLE_FACE = True
# WEBCAM_INDEX = 0

# # Optional serial control: set to something like "COM3" or "/dev/ttyUSB0"
# SERIAL_PORT: Optional[str] = None
# SERIAL_BAUDRATE = 115200
# SERIAL_CMD_PREFIX = "C:"  # e.g., "C:FORWARD\n"
# SERIAL_EMO_PREFIX = "E:"  # e.g., "E:happy\n"

# # Logging & privacy
# LOG_DIR = os.path.join(os.getcwd(), "logs")
# LOG_FILE = os.path.join(LOG_DIR, "interactions.jsonl")
# os.makedirs(LOG_DIR, exist_ok=True)
# PRIVACY_SAVE_AUDIO = False   # save raw mic capture
# PRIVACY_SAVE_FRAMES = True   # save face/full frames for debugging

# # Rover command dictionary and variants
# ROVER_CANONICAL = {
#     "FORWARD": {"forward", "go forward", "move forward", "ahead", "advance", "go ahead"},
#     "BACKWARD": {"back", "go back", "move back", "reverse", "back up"},
#     "LEFT": {"left", "turn left", "go left", "veer left"},
#     "RIGHT": {"right", "turn right", "go right", "veer right"},
#     "STOP": {"stop", "halt", "hold", "freeze"},
# }

# # Nice acknowledgements for TTS
# ACK_TEMPLATES = {
#     "FORWARD": "Going forward.",
#     "BACKWARD": "Going back.",
#     "LEFT": "Turning left.",
#     "RIGHT": "Turning right.",
#     "STOP": "Stopping.",
# }

# # ----------------------------- Utilities -----------------------------

# def _open_serial() -> Optional["serial.Serial"]:
#     if SERIAL_PORT and serial is not None:
#         try:
#             return serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=1)
#         except Exception as e:
#             print(f"[WARN] Could not open serial {SERIAL_PORT}: {e}")
#     return None


# def log_interaction(payload: dict):
#     try:
#         with open(LOG_FILE, "a", encoding="utf-8") as f:
#             f.write(json.dumps(payload, ensure_ascii=False) + "\n")
#     except Exception as e:
#         print(f"[WARN] Logging failed: {e}")


# # ----------------------------- Audio I/O -----------------------------

# def record_audio(duration_sec: int, rate: int, nchannels: int) -> np.ndarray:
#     """Record mono audio from default mic and return float32 waveform in [-1,1]."""
#     pa = pyaudio.PyAudio()
#     frames = []
#     stream = None
#     try:
#         stream = pa.open(format=pyaudio.paInt16, channels=nchannels, rate=rate,
#                          input=True, frames_per_buffer=1024)
#         print(f"🎙 Speak now ({duration_sec}s)...")
#         for _ in range(int(rate / 1024 * duration_sec)):
#             data = stream.read(1024, exception_on_overflow=False)
#             frames.append(data)
#     finally:
#         if stream is not None:
#             stream.stop_stream()
#             stream.close()
#         pa.terminate()

#     # Convert to float32 mono waveform
#     audio_bytes = b"".join(frames)
#     if PRIVACY_SAVE_AUDIO:
#         ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
#         try:
#             with open(os.path.join(LOG_DIR, f"raw_{ts}.pcm"), "wb") as f:
#                 f.write(audio_bytes)
#         except Exception:
#             pass
#     audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
#     if len(audio_int16) == 0:
#         return np.zeros(1, dtype=np.float32)
#     audio_float = (audio_int16.astype(np.float32) / 32768.0)  # normalize [-1, 1]
#     return audio_float


# def play_audio(wave: np.ndarray, rate: int):
#     pa = pyaudio.PyAudio()
#     stream = None
#     try:
#         stream = pa.open(format=pyaudio.paFloat32, channels=1, rate=rate, output=True)
#         stream.write(wave.tobytes())
#     finally:
#         if stream is not None:
#             stream.stop_stream()
#             stream.close()
#         pa.terminate()


# # ----------------------------- Vision -----------------------------

# def capture_face_frame(timeout_sec: float = 4.0) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
#     """Capture a single frame with a detected face; returns (face_rgb, frame_rgb)."""
#     cap = cv2.VideoCapture(WEBCAM_INDEX)
#     if not cap.isOpened():
#         print("[WARN] Webcam not available.")
#         return None, None
#     face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
#     start = time.time()
#     face_rgb = None
#     frame_rgb = None
#     try:
#         while time.time() - start < timeout_sec:
#             ret, frame = cap.read()
#             if not ret:
#                 continue
#             frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#             faces = face_cascade.detectMultiScale(gray, 1.3, 5)
#             if len(faces) > 0:
#                 x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
#                 face = frame[y:y+h, x:x+w]
#                 face_rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
#                 break
#     finally:
#         cap.release()

#     # Save debugging frames if enabled
#     if PRIVACY_SAVE_FRAMES:
#         ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
#         try:
#             if face_rgb is not None:
#                 cv2.imwrite(os.path.join(LOG_DIR, f"face_{ts}.jpg"), cv2.cvtColor(face_rgb, cv2.COLOR_RGB2BGR))
#             elif frame_rgb is not None:
#                 cv2.imwrite(os.path.join(LOG_DIR, f"frame_{ts}.jpg"), cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
#         except Exception:
#             pass
#     return face_rgb, frame_rgb


# # ----------------------------- Models: STT / TTS -----------------------------

# def load_seamless():
#     print("🔧 Loading SeamlessM4T...")
#     processor = AutoProcessor.from_pretrained(MODEL_ID, use_fast=False)
#     use_cuda = torch.cuda.is_available()
#     dtype = torch.float16 if use_cuda else torch.float32
#     if use_cuda:
#         model = SeamlessM4TModel.from_pretrained(MODEL_ID, torch_dtype=dtype, device_map="auto")
#     else:
#         model = SeamlessM4TModel.from_pretrained(MODEL_ID)
#         model.to("cpu")
#     return processor, model


# def transcribe(processor: AutoProcessor, model: SeamlessM4TModel, audio_np: np.ndarray) -> str:
#     """Speech -> Text using SeamlessM4TModel (generate_speech=False)."""
#     try:
#         inputs = processor(audios=audio_np, sampling_rate=SAMPLE_RATE, return_tensors="pt")
#         with torch.no_grad():
#             out_tokens = model.generate(**inputs, tgt_lang=TGT_LANG, generate_speech=False)
#         # decode first sample
#         text_out = processor.decode(out_tokens[0].tolist()[0], skip_special_tokens=True)
#         return text_out.strip()
#     except Exception as e:
#         print(f"[WARN] Transcription failed: {e}")
#         return ""


# def tts(processor: AutoProcessor, model: SeamlessM4TModel, text: str) -> np.ndarray:
#     """Text -> Speech waveform using SeamlessM4TModel (returns waveform as float32)."""
#     try:
#         inputs = processor(text=text, src_lang=SRC_LANG, return_tensors="pt")
#         with torch.no_grad():
#             gen = model.generate(**inputs, tgt_lang=TGT_LANG)
#         waveforms = gen[0] if isinstance(gen, (list, tuple)) else gen
#         audio = waveforms[0].cpu().numpy().squeeze().astype(np.float32)
#         return audio
#     except Exception as e:
#         print(f"[WARN] TTS failed: {e}")
#         return np.zeros(int(SAMPLE_RATE * 0.2), dtype=np.float32)  # short silence fallback


# # ----------------------------- Emotion Models -----------------------------

# def load_emotion_models(enable_face: bool):
#     print("🔧 Loading emotion models...")
#     device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
#     # SER (speech)
#     ser_processor = AutoFeatureExtractor.from_pretrained(SER_MODEL_ID)
#     ser_model = AutoModelForAudioClassification.from_pretrained(SER_MODEL_ID).to(device)

#     # Facial emotion (optional)
#     face_processor = None
#     face_model = None
#     face_ok = enable_face
#     if enable_face:
#         try:
#             face_processor = AutoImageProcessor.from_pretrained(FACE_MODEL_ID)
#             face_model = AutoModelForImageClassification.from_pretrained(FACE_MODEL_ID).to(device)
#         except Exception as e:
#             print(f"[WARN] Face model disabled: {e}")
#             face_ok = False

#     return device, ser_processor, ser_model, face_processor, face_model, face_ok


# def detect_emotion_speech(
#     ser_processor: AutoFeatureExtractor,
#     ser_model: AutoModelForAudioClassification,
#     device: torch.device,
#     audio_np: np.ndarray,
# ) -> Tuple[str, float]:
#     try:
#         inputs = ser_processor(audio_np, sampling_rate=SAMPLE_RATE, return_tensors="pt")
#         inputs = {k: v.to(device) for k, v in inputs.items()}
#         with torch.no_grad():
#             logits = ser_model(**inputs).logits
#             probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()
#             pred_id = int(np.argmax(probs))
#             label = ser_model.config.id2label.get(pred_id, str(pred_id))
#             conf = float(probs[pred_id])
#         return label, conf
#     except Exception as e:
#         print(f"[WARN] Speech emotion failed: {e}")
#         return "neutral", 0.0


# def detect_emotion_face(
#     face_processor: Optional[AutoImageProcessor],
#     face_model: Optional[AutoModelForImageClassification],
#     device: torch.device,
#     face_rgb: Optional[np.ndarray],
# ) -> Optional[Tuple[str, float]]:
#     if face_processor is None or face_model is None or face_rgb is None:
#         return None
#     try:
#         inputs = face_processor(images=face_rgb, return_tensors="pt").to(device)
#         with torch.no_grad():
#             logits = face_model(**inputs).logits
#             probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()
#             pred_id = int(np.argmax(probs))
#             label = face_model.config.id2label.get(pred_id, str(pred_id))
#             conf = float(probs[pred_id])
#         return label, conf
#     except Exception as e:
#         print(f"[WARN] Face emotion failed: {e}")
#         return None


# def fuse_emotions(
#     audio_emo: Optional[Tuple[str, float]],
#     face_emo: Optional[Tuple[str, float]],
# ) -> Tuple[str, float]:
#     """Pick most salient emotion between audio and face (by confidence; prefer non-neutral)."""
#     candidates = []
#     if audio_emo:
#         candidates.append(("audio",) + audio_emo)
#     if face_emo:
#         candidates.append(("face",) + face_emo)
#     if not candidates:
#         return ("neutral", 0.0)
#     non_neutral = [c for c in candidates if c[1].lower() not in ("neutral", "neu")]
#     pool = non_neutral if non_neutral else candidates
#     _src, label, conf = max(pool, key=lambda c: c[2])
#     return label, conf


# # ----------------------------- Dialogue & Commands -----------------------------

# def detect_rover_command(text: str) -> Optional[str]:
#     """
#     Return canonical command in {"FORWARD","BACKWARD","LEFT","RIGHT","STOP"} if detected, else None.
#     Uses simple phrase containment over a set of common variants.
#     """
#     t = (text or "").lower().strip()
#     if not t:
#         return None

#     # Exact phrase containment over synonym sets (longer phrases first)
#     # Flatten variants with length sort to prefer multi-word matches
#     variants = []
#     for canon, phrases in ROVER_CANONICAL.items():
#         for p in phrases:
#             variants.append((canon, p))
#     variants.sort(key=lambda x: -len(x[1]))

#     for canon, phrase in variants:
#         if phrase in t:
#             return canon

#     # Additional light rules
#     if t in {"go", "move"}:
#         return "FORWARD"
#     return None


# def ack_for_command(canon: str) -> str:
#     return ACK_TEMPLATES.get(canon, f"Executing {canon.lower()}.")


# def send_rover_command(canon: str):
#     """Send a simple rover command over serial if available."""
#     ser = _open_serial()
#     if ser is None:
#         return
#     try:
#         cmd = f"{SERIAL_CMD_PREFIX}{canon}\n".encode()
#         ser.write(cmd)
#     except Exception as e:
#         print(f"[WARN] Serial send failed: {e}")
#     finally:
#         try:
#             ser.close()
#         except Exception:
#             pass


# def send_emotion_gesture(emotion_label: str):
#     """Optionally map emotion to a gesture/motion over serial."""
#     ser = _open_serial()
#     if ser is None:
#         return
#     try:
#         cmd = f"{SERIAL_EMO_PREFIX}{emotion_label}\n".encode()
#         ser.write(cmd)
#     except Exception as e:
#         print(f"[WARN] Serial send failed: {e}")
#     finally:
#         try:
#             ser.close()
#         except Exception:
#             pass


# def compose_supportive_message(emotion_label: str, transcript: Optional[str]) -> str:
#     """Simple supportive templates based on fused emotion + echo transcript lightly."""
#     e = (emotion_label or "").lower()
#     if "sad" in e:
#         base = ("I'm sorry you're feeling down. You're not alone, and it's okay to take things one step at a time. "
#                 "Try a deep breath with me: in for four, hold for four, and out for six.")
#     elif "angry" in e or "frustrat" in e:
#         base = ("I can hear the frustration. It's valid to feel this way. "
#                 "Let's pause for a moment and release some tension with a slow breath.")
#     elif "fear" in e or "anx" in e or "worr" in e:
#         base = ("It sounds like you're feeling anxious. You're safe right now. "
#                 "Let's ground together—notice three things you can see, two you can touch, and one you can hear.")
#     elif "happy" in e or "joy" in e:
#         base = "You sound happy—that's wonderful. I’m glad to share this moment with you."
#     elif "surprise" in e or "surprised" in e:
#         base = "That sounded surprising. Take a moment to notice how your body feels and let it settle."
#     else:
#         base = "Thanks for sharing. I'm here with you if you'd like to talk more."

#     if transcript:
#         # keep echo brief to avoid reading long texts
#         t = transcript.strip()
#         if len(t) > 160:
#             t = t[:157] + "..."
#         return f"You said: {t}. {base}"
#     return base


# # ----------------------------- Main Pipeline -----------------------------

# def main_once():
#     # Load models (heavy — keep outside loops if you add continuous listening)
#     processor, s2x_model = load_seamless()
#     device, ser_processor, ser_model, face_processor, face_model, face_ok = load_emotion_models(ENABLE_FACE)

#     # 1) Record
#     audio_in = record_audio(RECORD_SECONDS, SAMPLE_RATE, CHANNELS)

#     # 2) Optionally capture face
#     raw_face, full_frame = (capture_face_frame() if face_ok else (None, None))

#     # 3) STT
#     print("📝 Transcribing...")
#     text = transcribe(processor, s2x_model, audio_in)
#     print(f"You said: {text}")

#     # 4) Command detection
#     cmd = detect_rover_command(text)
#     audio_emotion = None
#     face_emotion = None
#     fused_label, fused_conf = ("neutral", 0.0)

#     if cmd:
#         # Rover command path
#         print(f"🚗 Rover command detected: {cmd}")
#         send_rover_command(cmd)
#         response_text = ack_for_command(cmd)
#     else:
#         # Generic conversation → Emotion path
#         print("💗 Detecting emotion...")
#         audio_emotion = detect_emotion_speech(ser_processor, ser_model, device, audio_in)
#         face_emotion = detect_emotion_face(face_processor, face_model, device, raw_face)
#         fused_label, fused_conf = fuse_emotions(audio_emotion, face_emotion)
#         print(f"Audio emotion: {audio_emotion}, Face emotion: {face_emotion}, "
#               f"Fused: {fused_label} ({fused_conf:.2f})")

#         response_text = compose_supportive_message(fused_label, text)
#         send_emotion_gesture(fused_label)

#     # 5) TTS + play
#     print("🧡 Response:")
#     print(response_text)
#     print("🔊 Speaking...")
#     audio_out = tts(processor, s2x_model, response_text)
#     if audio_out.size > 0:
#         play_audio(audio_out, SAMPLE_RATE)

#     # 6) Log
#     ts = datetime.utcnow().isoformat() + "Z"
#     log_payload = {
#         "timestamp": ts,
#         "transcript": text,
#         "rover_command": cmd,
#         "audio_emotion": audio_emotion,
#         "face_emotion": face_emotion,
#         "fused_emotion": [fused_label, fused_conf],
#         "reply": response_text,
#     }
#     log_interaction(log_payload)
#     print("✅ Done.")


# if __name__ == "__main__":
#     main_once()
# import os
# os.environ["TRANSFORMERS_NO_TIKTOKEN"] = "1"
# import json
# import soundfile as sf
# import numpy as np
# import pyaudio
# from datetime import datetime
# from transformers import AutoProcessor, SeamlessM4Tv2Model, pipeline
# import torch
# import serial

# # ---------------- CONFIG ----------------
# sample_rate = 16000
# serial_port = "COM3"  # Change for your rover
# serial_baudrate = 9600
# log_dir = "logs"
# os.makedirs(log_dir, exist_ok=True)

# # Load Hugging Face models
# print("Loading models...")
# speech_model_name = "facebook/hf-seamless-m4t-medium"
# speech_model = SeamlessM4Tv2Model.from_pretrained(speech_model_name)
# processor = AutoProcessor.from_pretrained(speech_model_name)
# emotion_pipeline = pipeline("audio-classification", model="superb/hubert-large-superb-er")

# # ---------------- AUDIO I/O ----------------
# def record_audio(duration=5):
#     """Record audio from microphone."""
#     p = pyaudio.PyAudio()
#     stream = p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, input=True, frames_per_buffer=1024)
#     print("🎤 Recording...")
#     frames = [stream.read(1024) for _ in range(int(sample_rate / 1024 * duration))]
#     print("✅ Done recording")
#     stream.stop_stream()
#     stream.close()
#     p.terminate()
#     data = np.frombuffer(b''.join(frames), dtype=np.int16)
#     return data

# def play_audio(waveform, sr):
#     """Play audio from numpy array."""
#     p = pyaudio.PyAudio()
#     stream = p.open(format=pyaudio.paFloat32, channels=1, rate=sr, output=True)
#     stream.write(waveform.astype(np.float32).tobytes())
#     stream.stop_stream()
#     stream.close()
#     p.terminate()

# # ---------------- SPEECH MODELS ----------------
# def transcribe(audio_array):
#     inputs = processor(audio_array, sampling_rate=sample_rate, return_tensors="pt")
#     with torch.no_grad():
#         output = speech_model.generate(**inputs, tgt_lang="eng")
#     return processor.decode(output[0].tolist()[0])

# def tts(text):
#     inputs = processor(text=text, tgt_lang="eng", return_tensors="pt")
#     with torch.no_grad():
#         audio_out = speech_model.generate(**inputs, generate_speech=True)
#     return audio_out["waveform"].cpu().numpy()[0]

# # ---------------- EMOTION DETECTION ----------------
# def detect_audio_emotion(audio_array):
#     temp_file = os.path.join(log_dir, "temp.wav")
#     sf.write(temp_file, audio_array, sample_rate)
#     result = emotion_pipeline(temp_file)
#     return result[0]["label"]

# # ---------------- COMMAND DETECTION ----------------
# ROVER_COMMANDS = {
#     "go forward": "FORWARD",
#     "move forward": "FORWARD",
#     "forward": "FORWARD",
#     "go back": "BACKWARD",
#     "move back": "BACKWARD",
#     "back": "BACKWARD",
#     "turn left": "LEFT",
#     "left": "LEFT",
#     "turn right": "RIGHT",
#     "right": "RIGHT",
#     "stop": "STOP"
# }

# def detect_rover_command(text):
#     text_lower = text.lower()
#     for phrase, cmd in ROVER_COMMANDS.items():
#         if phrase in text_lower:
#             return cmd
#     return None

# def execute_rover_command(cmd):
#     try:
#         with serial.Serial(serial_port, serial_baudrate, timeout=1) as ser:
#             ser.write(f"C:{cmd}\n".encode())
#     except Exception:
#         print("[WARN] Could not send command over serial.")

# # ---------------- RESPONSE LOGIC ----------------
# def compose_response(emotion, text):
#     if emotion == "sad":
#         return "I hear you're feeling sad. I'm here for you."
#     elif emotion == "angry":
#         return "Take a deep breath. It will be okay."
#     elif emotion == "happy":
#         return "That's great to hear! Keep smiling."
#     elif emotion == "neutral":
#         return "I'm listening. Tell me more."
#     else:
#         return "I'm here to support you."

# def log_interaction(data):
#     filename = os.path.join(log_dir, f"log_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
#     with open(filename, "w") as f:
#         json.dump(data, f, indent=2)

# # ---------------- MAIN ----------------
# if __name__ == "__main__":
#     print("🤖 Rover & Emotion Assistant Ready!")
#     audio_in = record_audio(5)
#     print("Transcribing...")
#     text = transcribe(audio_in)
#     print(f"You said: {text}")

#     cmd = detect_rover_command(text)
#     if cmd:
#         print(f"🚗 Command detected: {cmd}")
#         execute_rover_command(cmd)
#         response_text = f"Going {cmd.lower()}"
#     else:
#         print("Detecting audio emotion...")
#         audio_emotion = detect_audio_emotion(audio_in)
#         print(f"Audio emotion: {audio_emotion}")
#         response_text = compose_response(audio_emotion, text)

#     print(f"🧡 Response: {response_text}")
#     audio_out = tts(response_text)
#     play_audio(audio_out, sample_rate)

#     # Log
#     log_interaction({
#         "timestamp": datetime.utcnow().isoformat() + "Z",
#         "transcript": text,
#         "rover_command": cmd,
#         "audio_emotion": None if cmd else audio_emotion,
#         "reply": response_text
#     })

# import os
# import json
# import soundfile as sf
# import numpy as np
# import pyaudio
# from datetime import datetime
# from transformers import AutoProcessor, SeamlessM4TModel, pipeline
# import torch
# import serial

# # ---------------- CONFIG ----------------
# sample_rate = 16000
# serial_port = "COM3"  # Change for your rover
# serial_baudrate = 9600
# log_dir = "logs"
# os.makedirs(log_dir, exist_ok=True)

# # Set device
# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# print(f"Device set to use {device}")

# # Load Hugging Face models
# print("Loading models...")
# speech_model_name = "facebook/hf-seamless-m4t-medium"
# speech_model = SeamlessM4TModel.from_pretrained(speech_model_name).to(device)
# processor = AutoProcessor.from_pretrained(speech_model_name, use_fast=False)
# emotion_pipeline = pipeline("audio-classification", model="superb/hubert-large-superb-er")

# # ---------------- AUDIO I/O ----------------
# def record_audio(duration=5):
#     """Record audio from microphone."""
#     p = pyaudio.PyAudio()
#     stream = p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, input=True, frames_per_buffer=1024)
#     print("🎤 Recording...")
#     frames = [stream.read(1024) for _ in range(int(sample_rate / 1024 * duration))]
#     print("✅ Done recording")
#     stream.stop_stream()
#     stream.close()
#     p.terminate()
#     data = np.frombuffer(b''.join(frames), dtype=np.int16)
#     return data

# def play_audio(waveform, sr):
#     """Play audio from numpy array."""
#     p = pyaudio.PyAudio()
#     stream = p.open(format=pyaudio.paFloat32, channels=1, rate=sr, output=True)
#     stream.write(waveform.astype(np.float32).tobytes())
#     stream.stop_stream()
#     stream.close()
#     p.terminate()

# # ---------------- SPEECH MODELS ----------------
# def transcribe(audio_array):
#     audio_array = audio_array.astype(np.float32) / 32768.0
#     inputs = processor(audios=audio_array, sampling_rate=sample_rate, return_tensors="pt").to(device)

#     with torch.no_grad():
#         output_tokens = speech_model.generate(**inputs, tgt_lang="eng")

#     token_ids = list(output_tokens[0].cpu().numpy().flatten())
#     text = processor.decode(token_ids, skip_special_tokens=True)
#     return text.strip()

# def tts(text):
#     inputs = processor(text=text, return_tensors="pt").to(device)
#     outputs = speech_model.generate(**inputs, tgt_lang="eng", generate_speech=True)

#     audio_tensor = outputs[1]  # waveform tensor
#     if audio_tensor.dim() > 1:
#         audio_tensor = audio_tensor.squeeze(0)
#     return audio_tensor.cpu().numpy()

# # ---------------- EMOTION DETECTION ----------------
# def detect_audio_emotion(audio_array):
#     temp_file = os.path.join(log_dir, "temp.wav")
#     sf.write(temp_file, audio_array, sample_rate)
#     result = emotion_pipeline(temp_file)
#     return result[0]["label"]

# # ---------------- COMMAND DETECTION ----------------
# ROVER_COMMANDS = {
#     "go forward": "FORWARD",
#     "move forward": "FORWARD",
#     "forward": "FORWARD",
#     "go back": "BACKWARD",
#     "move back": "BACKWARD",
#     "back": "BACKWARD",
#     "turn left": "LEFT",
#     "left": "LEFT",
#     "turn right": "RIGHT",
#     "right": "RIGHT",
#     "stop": "STOP"
# }

# def detect_rover_command(text):
#     text_lower = text.lower()
#     for phrase, cmd in ROVER_COMMANDS.items():
#         if phrase in text_lower:
#             return cmd
#     return None

# def execute_rover_command(cmd):
#     try:
#         with serial.Serial(serial_port, serial_baudrate, timeout=1) as ser:
#             ser.write(f"C:{cmd}\n".encode())
#     except Exception:
#         print("[WARN] Could not send command over serial.")

# # ---------------- RESPONSE LOGIC ----------------
# def compose_response(emotion, text, cmd=None):
#     if cmd:
#         if cmd == "FORWARD":
#             return "Moving forward."
#         elif cmd == "BACKWARD":
#             return "Going back."
#         elif cmd == "LEFT":
#             return "Turning left."
#         elif cmd == "RIGHT":
#             return "Turning right."
#         elif cmd == "STOP":
#             return "Stopping now."
#     else:
#         if emotion == "sad":
#             return "I hear you're feeling sad. I'm here for you."
#         elif emotion == "angry":
#             return "Take a deep breath. It will be okay."
#         elif emotion == "happy":
#             return "That's great to hear! Keep smiling."
#         elif emotion == "neutral":
#             return "I'm listening. Tell me more."
#         else:
#             return "I'm here to support you."

# def log_interaction(data):
#     filename = os.path.join(log_dir, f"log_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
#     with open(filename, "w") as f:
#         json.dump(data, f, indent=2)

# # ---------------- MAIN ----------------
# if __name__ == "__main__":
#     print("🤖 Rover & Emotion Assistant Ready!")
#     audio_in = record_audio(5)
#     print("Transcribing...")
#     text = transcribe(audio_in)
#     print(f"You said: {text if text else '[No speech detected]'}")

#     cmd = detect_rover_command(text)
#     if cmd:
#         print(f"🚗 Command detected: {cmd}")
#         execute_rover_command(cmd)
#         response_text = compose_response(None, text, cmd)
#     else:
#         print("Detecting audio emotion...")
#         audio_emotion = detect_audio_emotion(audio_in)
#         print(f"Audio emotion: {audio_emotion}")
#         response_text = compose_response(audio_emotion, text)

#     print(f"🧡 Response: {response_text}")
#     audio_out = tts(response_text)
#     play_audio(audio_out, sample_rate)

#     # Log
#     log_interaction({
#         "timestamp": datetime.utcnow().isoformat() + "Z",
#         "transcript": text,
#         "rover_command": cmd,
#         "audio_emotion": None if cmd else audio_emotion,
#         "reply": response_text
#     })
import os
import json
import soundfile as sf
import numpy as np
import pyaudio
from datetime import datetime, timezone
from transformers import AutoProcessor, SeamlessM4TModel, pipeline
import torch
import serial

# ---------------- CONFIG ----------------
sample_rate = 16000
serial_port = "COM3"  # Change for your rover
serial_baudrate = 9600
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

# ---------------- DEVICE & MODELS ----------------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device set to use {device}")

print("Loading models (this may take a while on first run)...")
speech_model_name = "facebook/hf-seamless-m4t-medium"

# load model and processor (use_fast=False to avoid tiktoken conversions)
speech_model = SeamlessM4TModel.from_pretrained(speech_model_name).to(device)
processor = AutoProcessor.from_pretrained(speech_model_name, use_fast=False)

# audio emotion pipeline (uses ffmpeg to read files; ensure ffmpeg is available)
emotion_pipeline = pipeline("audio-classification", model="superb/hubert-large-superb-er")

# ---------------- UTIL: Voice presence ----------------
def audio_has_voice(int16_audio: np.ndarray, sr: int, rms_threshold: float = 0.01) -> bool:
    """
    Check if audio contains significant energy.
    int16_audio: np.ndarray of dtype int16
    rms_threshold: threshold on normalized RMS (0..1). 0.01 is fairly low.
    """
    if int16_audio.size == 0:
        return False
    audio_f = int16_audio.astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(audio_f ** 2)))
    return rms >= rms_threshold

# ---------------- AUDIO I/O ----------------
def record_audio(duration=5):
    """Record mono int16 audio from default mic for `duration` seconds."""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, input=True, frames_per_buffer=1024)
    print(f"🎤 Recording {duration}s...")
    frames = []
    for _ in range(int(sample_rate / 1024 * duration)):
        data = stream.read(1024, exception_on_overflow=False)
        frames.append(data)
    print("✅ Done recording")
    stream.stop_stream()
    stream.close()
    p.terminate()
    audio_bytes = b"".join(frames)
    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
    return audio_int16

def play_audio(waveform: np.ndarray, sr: int):
    """Play a float32 waveform (values in [-1,1] or any float) with pyaudio."""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=sr, output=True)
    # ensure float32
    wf = waveform.astype(np.float32)
    stream.write(wf.tobytes())
    stream.stop_stream()
    stream.close()
    p.terminate()

# ---------------- SPEECH MODELS ----------------
def transcribe(int16_audio: np.ndarray) -> str:
    """
    Transcribe raw int16 audio using the SeamlessM4T processor & model.
    Returns the decoded string (possibly empty).
    """
    # Normalize to float32 in [-1,1]
    audio_f = int16_audio.astype(np.float32) / 32768.0

    # Prepare inputs properly (use 'audio=' single example)
    inputs = processor(audio=audio_f, sampling_rate=sample_rate, return_tensors="pt")
    # move tensors to device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        # generate returns token ids; ensure we don't request speech generation here
        outputs = speech_model.generate(**inputs, tgt_lang="eng", generate_speech=False)

    # outputs usually is a tensor of ids (batch, seq_len). Handle safely.
    if isinstance(outputs, torch.Tensor):
        token_tensor = outputs
    elif isinstance(outputs, (list, tuple)):
        token_tensor = outputs[0]
    else:
        # fallback: try to convert to tensor
        try:
            token_tensor = torch.tensor(outputs)
        except Exception:
            return ""

    # pick first sequence and flatten to 1D list of ints
    token_ids = token_tensor[0].cpu().numpy().flatten().tolist()
    # decode
    try:
        text = processor.decode(token_ids, skip_special_tokens=True).strip()
    except Exception:
        # fallback to tokenizer decode if processor.decode fails
        try:
            text = processor.tokenizer.decode(token_ids, skip_special_tokens=True).strip()
        except Exception:
            text = ""
    return text

def tts(text: str, tgt_lang: str = "eng") -> np.ndarray:
    """
    Generate speech for `text`. Returns numpy array waveform (float32, samples).
    This function is defensive to support different return formats.
    """
    inputs = processor(text=text, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = speech_model.generate(**inputs, tgt_lang=tgt_lang, generate_speech=True)

    # output can be (tokens, waveform_tensor) or a dict-like — handle both
    audio_tensor = None
    if isinstance(outputs, tuple) or isinstance(outputs, list):
        if len(outputs) >= 2:
            audio_tensor = outputs[1]
        else:
            # unexpected shape
            audio_tensor = outputs[0]
    elif isinstance(outputs, dict):
        # some implementations return dict with key 'waveform' or similar
        if "waveform" in outputs:
            audio_tensor = outputs["waveform"]
        elif "audio" in outputs:
            audio_tensor = outputs["audio"]
        else:
            # last resort, try to find a tensor value
            for v in outputs.values():
                if isinstance(v, torch.Tensor):
                    audio_tensor = v
                    break

    if audio_tensor is None:
        raise RuntimeError("Could not extract waveform from model output")

    # audio_tensor might be shape (batch, samples) or (samples,)
    if isinstance(audio_tensor, torch.Tensor):
        if audio_tensor.dim() > 1:
            audio_tensor = audio_tensor.squeeze(0)
        arr = audio_tensor.cpu().numpy().astype(np.float32)
        # If values are outside [-1,1], you may want to normalize — but keep as is
        return arr
    else:
        # if it's already numpy
        arr = np.array(audio_tensor, dtype=np.float32)
        if arr.ndim > 1:
            arr = arr.squeeze(0)
        return arr

# ---------------- EMOTION DETECTION ----------------
def detect_audio_emotion(int16_audio: np.ndarray) -> str:
    """
    Write a temp wav (float32) and run the pipeline. Returns label string.
    """
    temp_file = os.path.join(log_dir, "temp.wav")
    # convert to float32 in range [-1,1]
    audio_f = int16_audio.astype(np.float32) / 32768.0
    sf.write(temp_file, audio_f, sample_rate)
    result = emotion_pipeline(temp_file)
    # result is a list of dicts with 'label' and 'score'
    if isinstance(result, list) and len(result) > 0 and "label" in result[0]:
        return result[0]["label"]
    return "neutral"

# ---------------- COMMAND DETECTION ----------------
ROVER_COMMANDS = {
    "go forward": "FORWARD",
    "move forward": "FORWARD",
    "forward": "FORWARD",
    "go back": "BACKWARD",
    "move back": "BACKWARD",
    "back": "BACKWARD",
    "turn left": "LEFT",
    "left": "LEFT",
    "turn right": "RIGHT",
    "right": "RIGHT",
    "stop": "STOP"
}

def detect_rover_command(text: str):
    if not text:
        return None
    text_lower = text.lower()
    for phrase, cmd in ROVER_COMMANDS.items():
        if phrase in text_lower:
            return cmd
    return None

def execute_rover_command(cmd: str):
    try:
        with serial.Serial(serial_port, serial_baudrate, timeout=1) as ser:
            ser.write(f"C:{cmd}\n".encode())
    except Exception:
        print("[WARN] Could not send command over serial.")

# ---------------- RESPONSE LOGIC ----------------
def compose_response(emotion: str, text: str, cmd: str = None) -> str:
    if cmd:
        if cmd == "FORWARD":
            return "Moving forward."
        elif cmd == "BACKWARD":
            return "Going back."
        elif cmd == "LEFT":
            return "Turning left."
        elif cmd == "RIGHT":
            return "Turning right."
        elif cmd == "STOP":
            return "Stopping now."
    # emotion fallback
    e = (emotion or "").lower()
    if "sad" in e:
        return "I hear you're feeling sad. I'm here for you."
    if "angry" in e or "frustrat" in e:
        return "I can hear the frustration — try a slow breath with me."
    if "happy" in e or "hap" in e or "joy" in e:
        return "That's great to hear! Keep smiling."
    if "neutral" in e or e == "":
        return "I'm listening. Tell me more."
    return "I'm here to support you."

def log_interaction(data: dict):
    filename = os.path.join(log_dir, f"log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("🤖 Rover & Emotion Assistant Ready!")
    try:
        audio_in = record_audio(5)
        # quick voice presence check
        if not audio_has_voice(audio_in, sample_rate, rms_threshold=0.01):
            print("You said: [No speech detected]")
            # respond politely
            response_text = "I didn't catch that. Could you repeat?"
            print(f"🧡 Response: {response_text}")
            # attempt TTS but protect against failure
            try:
                audio_out = tts(response_text)
                play_audio(audio_out, sample_rate)
            except Exception as e:
                print("[WARN] TTS failed:", str(e))
            # log minimal event
            log_interaction({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "transcript": "",
                "rover_command": None,
                "audio_emotion": None,
                "reply": response_text
            })
        else:
            # we have voice — run transcription
            print("Transcribing...")
            text = transcribe(audio_in)
            print(f"You said: {text if text else '[No speech detected]'}")

            cmd = detect_rover_command(text)
            if cmd:
                print(f"🚗 Command detected: {cmd}")
                execute_rover_command(cmd)
                response_text = compose_response(None, text, cmd)
                audio_emotion = None
            else:
                print("Detecting audio emotion...")
                audio_emotion = detect_audio_emotion(audio_in)
                print(f"Audio emotion: {audio_emotion}")
                response_text = compose_response(audio_emotion, text)

            print(f"🧡 Response: {response_text}")

            # TTS & play (safe)
            try:
                audio_out = tts(response_text)
                play_audio(audio_out, sample_rate)
            except Exception as e:
                print("[WARN] TTS failed:", str(e))

            # Log everything
            log_interaction({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "transcript": text,
                "rover_command": cmd,
                "audio_emotion": audio_emotion,
                "reply": response_text
            })
    except Exception as exc:
        print("Fatal error:", str(exc))




