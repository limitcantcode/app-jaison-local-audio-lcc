import torch
torch.set_num_threads(1)
import numpy as np

# Provided by Alexander Veysov
def int2float(sound):
    abs_max = np.abs(sound).max()
    sound = sound.astype('float32')
    if abs_max > 0:
        sound *= 1/32768
    sound = sound.squeeze()  # depends on the use case
    return sound

class VAD:
    PADDING = 5
    THRESHOLD = 0.3
    
    def __init__(self):
        self.model, _ = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad')
        self.is_voice_detected = False
        self.data = list()
        
    def feed(self, ab: bytes) -> None:
        audio_int16 = np.frombuffer(ab, np.int16)
        audio_float32 = int2float(audio_int16)
        
        new_confidence = self.model(torch.from_numpy(audio_float32), 16000).item()
        
        if self.is_voice_detected and new_confidence < self.THRESHOLD:
            self.is_voice_detected = False
        elif (not self.is_voice_detected) and new_confidence >= self.THRESHOLD:
            self.is_voice_detected = True
            
        self.data.append((self.is_voice_detected, ab))
        return self.is_voice_detected
            
    def extract(self) -> bytes:
        ab = b""
        for i in range(len(self.data)):
            if (self.data[i][0]) or (i+self.PADDING < len(self.data) and self.data[i+self.PADDING][0]) or (i-self.PADDING >= 0 and self.data[i-self.PADDING][0]):
                ab += self.data[i][1].tobytes()
        self.data.clear()
        return ab