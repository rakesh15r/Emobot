# infer.py
import numpy as np, torch, torch.nn.functional as F
from transformers import AutoFeatureExtractor, AutoModel, AutoTokenizer, AutoModel as TextModel
from fusion_net import FusionNet

# pick model ids used in extract
AUDIO_MODEL = "superb/wavlm-base-superb-er"
TEXT_MODEL  = "distilbert-base-uncased"

feat = AutoFeatureExtractor.from_pretrained(AUDIO_MODEL)
audio_model = AutoModel.from_pretrained(AUDIO_MODEL).eval()
tokenizer = AutoTokenizer.from_pretrained(TEXT_MODEL)
text_model = TextModel.from_pretrained(TEXT_MODEL).eval()

# load fusion
sample = np.load("embeddings/" + sorted(__import__("glob").glob("embeddings/*.npz"))[0], allow_pickle=True)
audio_dim = sample['audio'].shape[0]
text_dim  = sample['text'].shape[0]
num_classes = 6  # set correctly
model = FusionNet(audio_dim, text_dim, hidden_dim=256, emotion_dim=64, num_classes=num_classes)
model.load_state_dict(torch.load("models/fusion_epoch10.pt", map_location="cpu"))
model.eval()

def get_embedding(audio_path, text):
    import torchaudio
    wav, sr = torchaudio.load(audio_path)
    if sr != feat.sampling_rate:
        wav = torchaudio.functional.resample(wav, sr, feat.sampling_rate)
    with torch.no_grad():
        a_in = feat(wav, sampling_rate=feat.sampling_rate, return_tensors="pt")
        a_emb = audio_model(**a_in).last_hidden_state.mean(dim=1)
        t_in = tokenizer(text, return_tensors="pt", truncation=True, max_length=128)
        t_emb = text_model(**t_in).last_hidden_state.mean(dim=1)
    return a_emb, t_emb

a,t = get_embedding("data/audio/happy1.wav", "I got the job!")
logits,_ = model(a, t)
probs = F.softmax(logits, dim=1).squeeze().numpy()
print("Probs:", probs)
