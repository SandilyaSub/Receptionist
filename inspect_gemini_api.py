import asyncio
import os
from google import genai

async def inspect_api():
    """Connects to Gemini and inspects the live session object."""
    print("--- Inspecting Gemini Live API ---")
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            # Fallback for local testing if the key is not in the environment
            try:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.environ.get("GEMINI_API_KEY")
                if not api_key:
                     # In your exotel_bridge.py you hardcoded it, so I'll do the same here for inspection
                    api_key = "AIzaSyDmnCmel5kqMzi7ShnbNiYrcUxzA_kaDkM"
            except ImportError:
                api_key = "AIzaSyDmnCmel5kqMzi7ShnbNiYrcUxzA_kaDkM"

        client = genai.Client(api_key=api_key)

        config = {
            "system_instruction": {
                "parts": [{"text": "You are a helpful assistant."}]
            },
            "response_modalities": ["AUDIO"],
            "speech_config": genai.types.SpeechConfig(
                voice_config=genai.types.VoiceConfig(
                    prebuilt_voice_config=genai.types.PrebuiltVoiceConfig(voice_name="Zephyr")
                )
            ),
        }

        print("Connecting to Gemini to get a session object...")
        async with client.aio.live.connect(
            model="models/gemini-2.5-flash-preview-native-audio-dialog",
            config=config
        ) as session:
            print("\nSuccessfully created a Gemini session object.")
            print("\nAttributes and methods available on the 'session' object:")
            print("---------------------------------------------------------")
            # Print all attributes and methods
            for attr in dir(session):
                if not attr.startswith('_'): # Hide private attributes
                    print(attr)
            print("---------------------------------------------------------")
            print("\nInspection complete. Check the list above for the correct methods to send/receive data.")

    except Exception as e:
        print(f"\nAn error occurred during inspection: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_api())
