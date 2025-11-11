# from faster_whisper import WhisperModel
import requests
import json
import torchaudio
import json
import numpy as np
import pandas as pd
import speech_recognition as sr
from extract_audio_feature import extract_audio_features_with_praat  # your existing script
from postprocess_audio_feature_iemocap import (
    extract_thresholds_and_stats,
    standardize_and_process_df,
    generate_concise_description,
    generate_impression
)
import paho.mqtt.client as mqtt
import base64
import io


# ✅ Ollama API endpoint for chat
OLLAMA_API = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "llama3.1"  # Change this if you pulled a different model

# ====== Initialize recognizer ======
recognizer = sr.Recognizer()

conversation_history = []

def emotion_classification(wav_path, transcript, dataset="iemocap", use_audio_description=True, use_audio_impression=False):
    """
    Generate the same style prompt template SpeechCueLLM uses,
    but for a single custom audio file + transcript.
    
    wav_path: path to your .wav file
    transcript: the spoken text (must be provided or transcribed via ASR)
    dataset: "iemocap" or "meld" (controls label set and wording)
    """
    # label sets as in data_process.py
    label_text_set = {
        'iemocap':'happy, sad, neutral, angry, excited, frustrated',
        'meld'   :'neutral, surprise, fear, sad, joyful, disgust, angry',
    }

    # 1. Extract audio features  
    wav_file = wav_path

    # Load the full dataset first to compute thresholds and stats
    df = pd.read_csv("iemocap_audio_features.csv")

    # Set number of classes
    num_classes = 6  

    # Compute thresholds and stats using training data
    train_df = df[df["mode"] == "train"]
    thresholds, stats = extract_thresholds_and_stats(train_df, num_classes)

    # --- Step 1: Extract features for this single wav file ---
    features = extract_audio_features_with_praat(wav_file)  # ✅ you already have this function in extract_audio_feature.py
    single_df = pd.DataFrame([features])

    if "gender" not in single_df.columns:
        single_df["gender"] = "overall"

    # --- Step 2: Standardize + Process ---
    processed_df = standardize_and_process_df(single_df, thresholds, stats, num_classes)

    # --- Step 3: Generate description + impression ---
    processed_df["description"] = processed_df.apply(
        lambda row: generate_concise_description(row, num_classes), axis=1
    )
    processed_df["impression"] = processed_df.apply(
        lambda row: generate_impression(row, num_classes), axis=1
    )

    # --- Step 4: Drop raw acoustic features ---
    original_features = [
        "avg_intensity", "intensity_variation", "avg_pitch",
        "pitch_std", "pitch_range", "articulation_rate", "mean_hnr"
    ]
    columns_to_keep = [col for col in processed_df.columns if col not in original_features]
    output_df = processed_df[columns_to_keep]

    # If you just want the impression and description:
    # print("Description:", output_df["description"].iloc[0])
    # print("Impression:", output_df["impression"].iloc[0])

    # 2. Build base instruction
    prompt = "Now you are expert of sentiment and emotional analysis."
    prompt += "The following conversation noted between '### ###' involves several speakers. "
    prompt += "### \t Speaker_0:\"{}\"".format(transcript)
    prompt += f" {output_df['description'].iloc[0]}"
    prompt += f" {output_df['impression'].iloc[0]}"

    prompt += " ###"

    # 4. Final classification request (same as training)
    prompt += f" Please select the emotional label of < Speaker_0:\"{transcript}\">"
    prompt += f" from <{label_text_set[dataset]}> based on both the context and audio features."
    prompt += " Respond with just one label:(just give emotion label)"
    print(prompt)
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        with requests.post(OLLAMA_API, json=payload, stream=True, timeout=120) as response:
            response.raise_for_status()
            
            emotion_label = ""
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line.decode("utf-8"))
                if "message" in data and "content" in data["message"]:
                    emotion_label += data["message"]["content"]

            if not emotion_label:
                emotion_label = "[No response received from Ollama]"
            return emotion_label

    except Exception as e:
        return f"[Error contacting Ollama: {e}]"
    

def response_llama(user_text, emotion):
    emotion = emotion.lower()

    # Save user input
    conversation_history.append({"role": "user", "content": f"[Emotion: {emotion}] {user_text}"})
    if len(conversation_history) > 20:
        conversation_history.pop(0)

    # Dynamic system prompt
    if emotion == "angry":
        system_prompt = (
            "If the user seems angry, reply in a short and calm way (1 line max), "
            "like 'Okay, moving away' or 'Alright, I’ll give you space.' "
            "Do NOT give long or emotional replies."
        )
    else:
        system_prompt = (
            "Respond like a friendly, emotionally aware assistant using 1–2 concise sentences."
        )

    # ✅ Ollama chat payload format
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}] + conversation_history,
        "options": {
            "temperature": 0.7,
            "num_predict": 80 if emotion != "angry" else 20
        }
    }

    try:
        # Use streaming mode so Ollama returns JSONL (one JSON per line)
        with requests.post(OLLAMA_API, json=payload, stream=True, timeout=120) as response:
            response.raise_for_status()

            reply_text = ""
            for line in response.iter_lines():
                if not line:
                    continue  # Skip empty lines

                # Decode bytes → string safely
                line_str = line.decode("utf-8")

                # Each line should be a JSON object
                try:
                    data = json.loads(line_str)
                    if "message" in data and "content" in data["message"]:
                        reply_text += data["message"]["content"]
                except json.JSONDecodeError:
                    # Skip any partial lines
                    continue

            if not reply_text:
                reply_text = "[No response received from Ollama]"

    except Exception as e:
        reply_text = f"[Error contacting Ollama: {e}]"

    # Save assistant reply
    conversation_history.append({"role": "assistant", "content": reply_text})
    if len(conversation_history) > 20:
        conversation_history.pop(0)

    return reply_text

def stt(wav_file):
    with sr.AudioFile(wav_file) as source:
        audio = recognizer.record(source)

    try:
        transcript = recognizer.recognize_google(audio)
        print(f"Text from audio file: {transcript}")
        return transcript
    except sr.UnknownValueError:
        print("Could not understand audio from file")
    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")