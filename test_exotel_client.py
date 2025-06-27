import asyncio
import base64
import json
import wave
import websockets

SERVER_URL = "ws://localhost:8081"
TEST_AUDIO_FILE = "test_audio.wav"
RESPONSE_AUDIO_FILE = "response_audio.wav"

async def run_test():
    """Connects to the bridge, sends audio, and saves the response."""
    print(f"Connecting to WebSocket server at {SERVER_URL}...")
    try:
        async with websockets.connect(SERVER_URL) as websocket:
            print("Connection established.")

            # 1. Send 'start' event to simulate the beginning of a call
            start_event = {
                "event": "start",
                "stream_sid": "test_stream_12345",
                "call_sid": "test_call_67890"
            }
            await websocket.send(json.dumps(start_event))
            print(f"Sent 'start' event: {start_event}")

            # 2. Create a task to listen for responses from the server
            response_frames = []
            async def receive_handler():
                print("Listening for responses from the server...")
                try:
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        if data.get("event") == "media":
                            payload = data.get("media", {}).get("payload")
                            if payload:
                                audio_data = base64.b64decode(payload)
                                response_frames.append(audio_data)
                                print(f"Received {len(audio_data)} bytes of audio data.")
                except websockets.exceptions.ConnectionClosed:
                    print("Server closed the connection.")
                except Exception as e:
                    print(f"Error receiving message: {e}")

            receiver_task = asyncio.create_task(receive_handler())

            # 3. Read the test audio file and stream it to the server
            print(f"Streaming audio from {TEST_AUDIO_FILE}...")
            with wave.open(TEST_AUDIO_FILE, 'rb') as wf:
                chunk_size = 800 # 100ms of 8kHz, 16-bit audio
                while True:
                    audio_chunk = wf.readframes(chunk_size)
                    if not audio_chunk:
                        break
                    
                    base64_audio = base64.b64encode(audio_chunk).decode('utf-8')
                    media_event = {
                        "event": "media",
                        "media": {
                            "payload": base64_audio
                        }
                    }
                    await websocket.send(json.dumps(media_event))
                    await asyncio.sleep(0.1) # Simulate real-time streaming

            print("Finished streaming audio.")

            # 4. Wait longer for final responses, then close
            print("Waiting for Gemini responses (30 seconds)...")
            await asyncio.sleep(30) # Extended wait time for Gemini to process and respond
            # Don't close the connection, just let the receiver_task continue running
            # await websocket.close()
            # receiver_task.cancel()

            # 5. Save the collected response audio to a file
            if response_frames:
                print(f"Saving response audio to {RESPONSE_AUDIO_FILE}...")
                with wave.open(RESPONSE_AUDIO_FILE, 'wb') as wf_out:
                    wf_out.setnchannels(1)
                    wf_out.setsampwidth(2) # 16-bit
                    wf_out.setframerate(8000)
                    wf_out.writeframes(b''.join(response_frames))
                print("Response audio saved.")
            else:
                print("No audio received from the server.")

    except Exception as e:
        print(f"Failed to connect or run test: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
