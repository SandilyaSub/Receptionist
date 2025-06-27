import os
import asyncio
import sounddevice as sd
import numpy as np
from dotenv import load_dotenv
import google.generativeai as genai
import wave

# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API key
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

SAMPLE_RATE = 16000
DURATION = 5  # seconds

def record_audio(filename, duration, samplerate):
    """Records audio from the microphone and saves it as a WAV file."""
    print(f"Recording {duration} seconds of audio... Speak now!")
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
    sd.wait()  # Wait for the recording to complete
    
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit audio
        wf.setframerate(samplerate)
        wf.writeframes(recording.tobytes())
    print(f"Recording finished. Audio saved to {filename}")

async def main():
    """Records audio, uploads it, and gets a description from the Gemini API."""
    audio_filename = "prompt.wav"
    record_audio(audio_filename, DURATION, SAMPLE_RATE)

    # Upload the audio file
    print(f"Uploading {audio_filename} to Gemini...")
    audio_file = genai.upload_file(path=audio_filename)
    print(f"Completed upload: {audio_file.uri}")

    # Use a model that supports audio input
    model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")

    print("Sending audio to Gemini for analysis...")
    # Send the audio data to the model
    response = await model.generate_content_async(["What is in this audio?", audio_file])

    print("\n--- RESPONSE FROM GEMINI ---")
    print(response.text)
    print("--------------------------")

    # Clean up the uploaded file
    print(f"Deleting uploaded file: {audio_file.name}")
    await genai.delete_file_async(name=audio_file.name)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")
