# extract_embeddings.py
import os
import numpy as np
import pandas as pd
import torch
import torchaudio
from transformers import AutoFeatureExtractor, AutoModel, AutoTokenizer, AutoModel as TextModel

# === CONFIG ===
AUDIO_MODEL = "superb/wavlm-base-superb-er"   # audio encoder (change if you prefer)
TEXT_MODEL  = "distilbert-base-uncased"       # text encoder
CSV_PATH    = "data/transcripts.csv"
AUDIO_DIR   = "data/audio"
OUT_DIR     = "embeddings"
MAX_TEXT_LEN = 128
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# =============

os.makedirs(OUT_DIR, exist_ok=True)

print("Loading models (this may take a minute)...")
audio_feat = AutoFeatureExtractor.from_pretrained(AUDIO_MODEL)
audio_model = AutoModel.from_pretrained(AUDIO_MODEL).to(DEVICE).eval()
tokenizer = AutoTokenizer.from_pretrained(TEXT_MODEL)
text_model = TextModel.from_pretrained(TEXT_MODEL).to(DEVICE).eval()

df = pd.read_csv(CSV_PATH)
print(f"Found {len(df)} rows in {CSV_PATH}")

for idx, row in df.iterrows():
    file_name = str(row['file'])
    text = str(row['text'])
    label = str(row['label'])
    wav_path = os.path.join(AUDIO_DIR, file_name)

    if not os.path.exists(wav_path):
        print(f"[SKIP] missing audio: {wav_path}")
        continue

    # load audio
    wav, sr = torchaudio.load(wav_path)  # wav shape: [channels, samples]
    # If stereo, convert to mono by mean
    if wav.shape[0] > 1:
        wav = wav.mean(dim=0, keepdim=True)
    # resample if needed
    target_sr = getattr(audio_feat, "sampling_rate", None) or 16000
    if sr != target_sr:
        wav = torchaudio.functional.resample(wav, orig_freq=sr, new_freq=target_sr)
        sr = target_sr

    # audio embedding
    with torch.no_grad():
        # feature extractor expects numpy-like waveform or torch tensor batched; return_tensors="pt"
        audio_inputs = audio_feat(wav, sampling_rate=sr, return_tensors="pt")
        # move input tensors to device
        audio_inputs = {k: v.to(DEVICE) for k, v in audio_inputs.items()}
        a_out = audio_model(**audio_inputs)
        # take mean pooling over time dimension
        # many models set last_hidden_state; we handle the common case
        if hasattr(a_out, "last_hidden_state"):
            a_emb = a_out.last_hidden_state.mean(dim=1).squeeze(0).cpu().numpy()
        else:
            # fallback to pooled output if available
            a_emb = a_out.pooler_output.squeeze(0).cpu().numpy()

    # text embedding
    with torch.no_grad():
        t_inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_TEXT_LEN)
        t_inputs = {k: v.to(DEVICE) for k, v in t_inputs.items()}
        t_out = text_model(**t_inputs)
        if hasattr(t_out, "last_hidden_state"):
            t_emb = t_out.last_hidden_state.mean(dim=1).squeeze(0).cpu().numpy()
        else:
            t_emb = t_out.pooler_output.squeeze(0).cpu().numpy()

    out_path = os.path.join(OUT_DIR, f"{os.path.splitext(file_name)[0]}.npz")
    np.savez(out_path, audio=a_emb, text=t_emb, label=label)
    print(f"[SAVED] {out_path} (audio_dim={a_emb.shape[0]}, text_dim={t_emb.shape[0]})")
print("All embeddings extracted and saved.")