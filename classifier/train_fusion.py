# train_fusion.py
import glob, numpy as np, torch, torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import LabelEncoder
from fusion_net import FusionNet
import torch.optim as optim

class EmbeddingDataset(Dataset):
    def __init__(self, npz_files, le):
        self.files = npz_files
        self.le = le
    def __len__(self): return len(self.files)
    def __getitem__(self, i):
        d = np.load(self.files[i], allow_pickle=True)
        a = d['audio'].astype('float32')
        t = d['text'].astype('float32')
        lbl = self.le.transform([d['label'].tolist()])[0]
        return a, t, lbl

files = glob.glob("embeddings/*.npz")
# build label encoder
labels = [np.load(f, allow_pickle=True)['label'].tolist() for f in files]
le = LabelEncoder().fit(labels)

# split
np.random.shuffle(files)
split = int(0.8 * len(files))
train_files, val_files = files[:split], files[split:]

train_ds = EmbeddingDataset(train_files, le)
val_ds = EmbeddingDataset(val_files, le)
train_loader = DataLoader(train_ds, batch_size=8, shuffle=True)
val_loader = DataLoader(val_ds, batch_size=16)

# load one file to get dims
sample = np.load(files[0], allow_pickle=True)
audio_dim = sample['audio'].shape[0]
text_dim = sample['text'].shape[0]
num_classes = len(le.classes_)

model = FusionNet(audio_dim, text_dim, hidden_dim=256, emotion_dim=64, num_classes=num_classes)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

opt = optim.Adam(model.parameters(), lr=1e-4)
best_val = 1e9

for epoch in range(1, 31):
    model.train()
    total_loss = 0.0
    for a,t,y in train_loader:
        a = a.to(device); t = t.to(device); y = y.to(device)
        opt.zero_grad()
        logits, _ = model(a, t)
        loss = F.cross_entropy(logits, y)
        loss.backward(); opt.step()
        total_loss += loss.item()
    # validation
    model.eval()
    correct, total = 0,0
    with torch.no_grad():
        for a,t,y in val_loader:
            a=a.to(device); t=t.to(device); y=y.to(device)
            logits,_ = model(a,t)
            preds = logits.argmax(dim=1)
            correct += (preds==y).sum().item()
            total += y.size(0)
    val_acc = correct/total if total>0 else 0
    print(f"Epoch {epoch}: train_loss={(total_loss/len(train_loader)):.4f} val_acc={val_acc:.3f}")
    # save best
    torch.save(model.state_dict(), f"models/fusion_epoch{epoch}.pt")
