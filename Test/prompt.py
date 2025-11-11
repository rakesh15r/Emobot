from faster_whisper import WhisperModel

# Load a model (tiny, base, small, medium, large-v2)
model = WhisperModel("small", device="cpu")

# Transcribe audio file
wav_file = "/kaggle/input/audio-files/audio_files/anger.wav"
segments, info = model.transcribe(wav_file)

# Combine text
transcript = " ".join([seg.text for seg in segments])
print("Transcription:", transcript)



import torchaudio
import json
from extract_audio_feature import extract_audio_features_with_praat  # your existing script
from postprocess_audio_feature_iemocap import (
    extract_thresholds_and_stats,
    standardize_and_process_df,
    generate_concise_description,
    generate_impression
)

# optionally syllable_nuclei if used in postprocessing

def build_prompt_from_wav(wav_path, transcript, dataset="iemocap", use_audio_description=True, use_audio_impression=False):
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
    df = pd.read_csv("/kaggle/input/iemocap/iemocap_audio_features.csv")

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
    print("Description:", output_df["description"].iloc[0])
    print("Impression:", output_df["impression"].iloc[0])

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
    prompt += " Respond with just one label:"

    return prompt

# Example usage
if __name__ == "__main__":
    transcript = transcript# ideally from ASR
    prompt = build_prompt_from_wav(wav_file, transcript)
    print("\nGenerated Prompt:\n", prompt)