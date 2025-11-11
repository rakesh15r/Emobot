# fusion_net.py
import torch.nn as nn
import torch

class FusionNet(nn.Module):
    def __init__(self, audio_dim, text_dim, hidden_dim=256, emotion_dim=64, num_classes=6):
        super().__init__()
        total = audio_dim + text_dim
        self.gate = nn.Sequential(
            nn.Linear(total, total//2),
            nn.ReLU(),
            nn.Linear(total//2, audio_dim),
            nn.Sigmoid()
        )
        self.proj_fused = nn.Sequential(
            nn.Linear(audio_dim + text_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, emotion_dim),
            nn.ReLU()
        )
        self.classifier = nn.Linear(emotion_dim, num_classes)

    def forward(self, audio_emb, text_emb):
        # audio_emb, text_emb shape: [B, D_a], [B, D_t]
        concat = torch.cat([audio_emb, text_emb], dim=1)
        gate = self.gate(concat)                         # [B, D_a]
        fused = gate * audio_emb + (1 - gate) * text_emb[:, :audio_emb.shape[1]]  # broadcast safely
        emotion_vec = self.proj_fused(torch.cat([fused, concat], dim=1))
        logits = self.classifier(emotion_vec)
        return logits, emotion_vec
