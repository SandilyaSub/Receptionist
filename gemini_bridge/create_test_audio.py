#!/usr/bin/env python3
import wave
import numpy as np

# Create a simple sine wave audio file
samplerate = 16000
duration = 3  # seconds
frequency = 440  # Hz (A4 note)

# Generate the sine wave
t = np.linspace(0, duration, int(samplerate * duration), False)
audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)

# Convert to 16-bit PCM
audio = (audio * 32767).astype(np.int16)

# Write to WAV file
with wave.open('test_audio.wav', 'wb') as wf:
    wf.setnchannels(1)  # Mono
    wf.setsampwidth(2)  # 2 bytes = 16 bits
    wf.setframerate(samplerate)
    wf.writeframes(audio.tobytes())

print("Created test_audio.wav")
