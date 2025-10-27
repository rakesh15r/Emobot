# # # Requires: librosa
# # from transformers import AutoModelForAudioClassification, AutoFeatureExtractor
# # import librosa
# # import torch
# # import numpy as np

# # model_id = "firdhokk/speech-emotion-recognition-with-openai-whisper-large-v3"
# # model = AutoModelForAudioClassification.from_pretrained(model_id)

# # feature_extractor = AutoFeatureExtractor.from_pretrained(model_id, do_normalize=True)
# # id2label = model.config.id2label

# # def preprocess_audio(audio_path, feature_extractor, max_duration=30.0):
# #     audio_array, sampling_rate = librosa.load(audio_path, sr=feature_extractor.sampling_rate)
    
# #     max_length = int(feature_extractor.sampling_rate * max_duration)
# #     if len(audio_array) > max_length:
# #         audio_array = audio_array[:max_length]
# #     else:
# #         audio_array = np.pad(audio_array, (0, max_length - len(audio_array)))

# #     inputs = feature_extractor(
# #         audio_array,
# #         sampling_rate=feature_extractor.sampling_rate,
# #         max_length=max_length,
# #         truncation=True,
# #         return_tensors="pt",
# #     )
# #     return inputs

# # def predict_emotion(audio_path, model, feature_extractor, id2label, max_duration=30.0):
# #     inputs = preprocess_audio(audio_path, feature_extractor, max_duration)
    
# #     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# #     model = model.to(device)
# #     inputs = {key: value.to(device) for key, value in inputs.items()}

# #     with torch.no_grad():
# #         outputs = model(**inputs)

# #     logits = outputs.logits
# #     predicted_id = torch.argmax(logits, dim=-1).item()
# #     predicted_label = id2label[predicted_id]
    
# #     return predicted_label

# # audio_path = "/content/drive/MyDrive/Audio/Speech_URDU/Happy/SM5_F4_H058.wav"

# # predicted_emotion = predict_emotion(audio_path, model, feature_extractor, id2label)
# # print(f"Predicted Emotion: {predicted_emotion}")

# # Requires: transformers, librosa, sounddevice, scipy
# import sounddevice as sd
# import numpy as np
# import torch
# import scipy.io.wavfile as wav
# from transformers import AutoModelForAudioClassification, AutoFeatureExtractor

# # Load model and feature extractor
# model_id = "firdhokk/speech-emotion-recognition-with-openai-whisper-large-v3"
# model = AutoModelForAudioClassification.from_pretrained(model_id)
# feature_extractor = AutoFeatureExtractor.from_pretrained(model_id, do_normalize=True)
# id2label = model.config.id2label

# # Function to record audio from the microphone
# def record_audio(duration=5, samplerate=16000):
#     print(f"[INFO] Recording for {duration} seconds...")
#     recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='float32')
#     sd.wait()  # Wait until recording is finished
#     return recording.flatten(), samplerate

# # Function to predict emotion from a NumPy audio array
# def predict_emotion_from_array(audio_array, sr, model, feature_extractor, id2label):
#     # Extract features from audio
#     inputs = feature_extractor(audio_array, sampling_rate=sr, return_tensors="pt", padding=True)
    
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#     model = model.to(device)
#     inputs = {key: value.to(device) for key, value in inputs.items()}

#     # Inference
#     with torch.no_grad():
#         outputs = model(**inputs)

#     logits = outputs.logits
#     probs = torch.softmax(logits, dim=-1)
#     predicted_id = torch.argmax(probs, dim=-1).item()
#     predicted_label = id2label[predicted_id]
#     confidence = probs[0][predicted_id].item()

#     return predicted_label, confidence

# # Main loop
# if __name__ == "__main__":
#     duration = 5  # Record for 5 seconds
#     samplerate = feature_extractor.sampling_rate  # Model's expected sample rate
    
#     while True:
#         print("\nPress ENTER to start recording or type 'exit' to quit:")
#         command = input().strip().lower()
#         if command == "exit":
#             break
        
#         # Record audio from mic
#         audio_array, sr = record_audio(duration=duration, samplerate=samplerate)
        
#         # Predict emotion
#         predicted_emotion, confidence = predict_emotion_from_array(audio_array, sr, model, feature_extractor, id2label)
#         print(f"Predicted Emotion: {predicted_emotion} (Confidence: {confidence:.2f})")

import sounddevice as sd
import numpy as np
import torch
from transformers import AutoModelForAudioClassification, AutoFeatureExtractor

# Load model & feature extractor
model_id = "firdhokk/speech-emotion-recognition-with-openai-whisper-large-v3"
print("[INFO] Loading model... This may take a while the first time.")
model = AutoModelForAudioClassification.from_pretrained(model_id)
feature_extractor = AutoFeatureExtractor.from_pretrained(model_id, do_normalize=True)
id2label = model.config.id2label

def record_audio():
    """Record audio until user presses Enter again."""
    sr = feature_extractor.sampling_rate
    print(f"\n[INFO] Recording... Press ENTER to stop.")
    print(f"[INFO] Sample Rate: {sr} Hz")

    audio_data = []

    def callback(indata, frames, time, status):
        if status:
            print(status)
        audio_data.append(indata.copy())

    with sd.InputStream(samplerate=sr, channels=1, callback=callback):
        input()  # Wait until Enter is pressed

    audio_array = np.concatenate(audio_data, axis=0).flatten()
    return audio_array, sr

def predict_emotion_from_array(audio_array, sampling_rate, model, feature_extractor, id2label):
    """Predict emotion from raw audio array."""
    # Pad/truncate automatically for Whisper
    inputs = feature_extractor(
        audio_array,
        sampling_rate=sampling_rate,
        return_tensors="pt",
        padding="max_length",
        truncation=True,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits
    predicted_id = torch.argmax(logits, dim=-1).item()
    confidence = torch.softmax(logits, dim=-1)[0, predicted_id].item()

    return id2label[predicted_id], confidence

if __name__ == "__main__":
    try:
        while True:
            user_input = input("\nPress ENTER to start recording or type 'exit' to quit: ")
            if user_input.lower() == 'exit':
                break

            print("[INFO] Speak now. Press ENTER when you're done speaking...")
            audio_array, sr = record_audio()

            print(f"[INFO] Audio captured: {len(audio_array) / sr:.2f} seconds")
            print("[INFO] Predicting emotion...")

            predicted_emotion, confidence = predict_emotion_from_array(audio_array, sr, model, feature_extractor, id2label)
            print(f"\n✅ Predicted Emotion: {predicted_emotion} (Confidence: {confidence:.2f})")

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
    finally:
        input("\nPress Enter to exit...")
