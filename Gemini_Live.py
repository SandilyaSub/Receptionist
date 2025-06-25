"""
## Documentation
Quickstart: https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI.py

## Setup

To install the dependencies for this script, run:

```
pip install google-genai opencv-python pyaudio pillow mss
```
"""

import os
import asyncio
import base64
import io
import traceback
import json
from datetime import datetime

import cv2
import pyaudio
import PIL.Image
import mss

import argparse

from google import genai
from google.genai import types



FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.5-flash-preview-native-audio-dialog"

DEFAULT_MODE = "camera"

# Directory to store call transcripts
CALL_DETAILS_DIR = "call_details"

class TranscriptManager:
    """Manages conversation transcripts and saves them to JSON files."""
    
    def __init__(self):
        """Initialize a new transcript manager."""
        # Create the call_details directory if it doesn't exist
        os.makedirs(CALL_DETAILS_DIR, exist_ok=True)
        
        # Initialize transcript data
        self.transcript_data = {
            "call_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "start_time": datetime.now().isoformat(),
            "conversation": []
        }
        self.current_user_text = ""
        self.current_model_text = ""
        self.last_speaker = None
        
    def add_user_transcript(self, text):
        """Add user transcript text."""
        if text:
            # If we were previously getting model text and now have user text,
            # save the model's message and start a new user message
            if self.last_speaker == "model" and self.current_model_text:
                self.transcript_data["conversation"].append({
                    "role": "assistant",
                    "content": self.current_model_text
                })
                self.current_model_text = ""
                self.current_user_text = text
            else:
                # Append to current user transcript
                self.current_user_text += text
            self.last_speaker = "user"
            
    def add_model_transcript(self, text):
        """Add model transcript text."""
        if text:
            # If we were previously getting user text and now have model text,
            # save the user's message and start a new model message
            if self.last_speaker == "user" and self.current_user_text:
                self.transcript_data["conversation"].append({
                    "role": "user",
                    "content": self.current_user_text
                })
                self.current_user_text = ""
                self.current_model_text = text
            else:
                # Append to current model transcript
                self.current_model_text += text
            self.last_speaker = "model"
    
    def save_transcript(self):
        """Save the transcript to a JSON file."""
        # Add the last message if it has any content
        if self.current_user_text:
            self.transcript_data["conversation"].append({
                "role": "user",
                "content": self.current_user_text
            })
        if self.current_model_text:
            self.transcript_data["conversation"].append({
                "role": "assistant",
                "content": self.current_model_text
            })
        
        # Add end time
        self.transcript_data["end_time"] = datetime.now().isoformat()
        
        # Generate filename
        filename = f"{self.transcript_data['call_id']}.json"
        filepath = os.path.join(CALL_DETAILS_DIR, filename)
        
        # Write to file
        with open(filepath, 'w') as f:
            json.dump(self.transcript_data, f, indent=2)
        
        # Remove terminal logging
        return filepath

client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key=GEMINI_API_KEY,
)


CONFIG = types.LiveConnectConfig(
    response_modalities=[
        "AUDIO",
    ],
    input_audio_transcription={},
    output_audio_transcription={},
    media_resolution="MEDIA_RESOLUTION_MEDIUM",
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        )
    ),
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),
    system_instruction=types.Content(
        parts=[types.Part.from_text(text="""You are working as a receptionist at this bakery taking user orders. 
Be courteous and respond properly. Do this in an Indian accent.

Towards the start of the conversation , ask the customer for his name , so that you can use that to address him during the conversation.

At the end of the conversation , the expectation is that you would have figured out all the relevant details that a baker needs to make a cake and keep it ready. You will tell the customer the price that would be incurred and a timeslot by when the cake would be ready, so that he could pick it up. The menu is towards the bottom of the instructions. The time a customer can come and pick the cake up would be 6hrs for making the cake and the cake is made only during the working hours. 

Typical preferences that customers would need to hear from you are - 
- flavour of the cake ,
- egg / eggless , 
- add-ons that are required like chocolates / some sprinkles , 
- size of the cake in KGs , 
- shape of the cake & occasion
- what is to be written on the cake or any further customizations.


DONOT ANSWER ANY IRRELEVANT QUESTIONS THAT ARE BEYOND THE SCOPE MENTIONED HERE. IF A CUSTOMERS ASKS SUCH A QUESTION POLITELY REPLY THAT YOU ARE SORRY AND CAN'T ANSWER THAT QUESTION AT THIS TIME. 

If a difficult question for which you are unsure of what the answer could be is asked , just reply to the customer that someone from the store will call you back during the next available working hour slot. 
---------------------------
Menu
Open Hours: 10am - 9pm

A-La-Carte Desserts
Russian Medovik – RS 160.00

Opera – RS 180.00

Belgian Truffle – RS 180.00

German Chocolate Cakeslice – RS 140.00

Tres Leches – RS 160.00

Baked Cheese Cake Slice – RS 160.00

Cupcakes
Coconut Crumble – RS 80.00

Chocolate Cheese Cake – RS 80.00

Coffee Caramel – RS 80.00

Classic Red Velvet – RS 80.00

Dairy Milk – RS 80.00

Blueberry – RS 80.00

Decadent Chocolate – RS 80.00

Macarons
Elachi Toffee – RS 60.00

Mewa Rabri – RS 60.00

Coconut – RS 60.00

Lemon Curd – RS 60.00

Banoffee – RS 60.00

Dark Chocolate – RS 60.00

Raspberry – RS 60.00

Dessert Tubs
Tiramisu – RS 280.00

Biscoff – RS 280.00

Chocolate Mousse – RS 280.00

Banoffee – RS 280.00

Bakery & Confectionery
English Toffee – RS 180.00

Caramel Popcorn – RS 180.00

Nan Khataai – RS 300.00

Chocolate Chip Cookies – RS 300.00

Almond Biscotti – RS 300.00

Oatmeal Cookies – RS 300.00

Chocolates
Couverture Chocolate (Each RS 60.00):

Sugarfree Fudge (Dates, Cashew & Sugarfree Dark)

Sugarfree Fruit n Nut (Dried Raspberry, Roasted Almond & Apricot)

Almond Rocks (Dark 45%, Roasted Almond)

Deep Brown (Dark Chocolate 70% Cocoa, Cocoa Nibs)

Banana Toffee (White Chocolate, White Banofee Ganache & Praline)

Kopra (White Chocolate, White Ganache Filling with Aged Coconut)

Salted Caramel (Milk Chocolate, Salted Caramel)

Raspberry Bombs (Milk Chocolate & Dried Raspberry Bits)

Mewa Rabri (Milk Chocolate, Mewa Rabri Filling)

Classic Dairy Milk (Milk Chocolate, Milk Ganache)

Hazelnut Praline (Milk Chocolate, Hazelnuts & Praline)

By the Box:

55% Cocoa Dark (Box of 12) – RS 700.00

55% Cocoa Dark (Box of 16) – RS 750.00

70% Cocoa Dark Sugarfree (Box of 12) – RS 650.00

70% Cocoa Dark Sugarfree (Box of 16) – RS 850.00

46.5% Cocoa Dry Fruit Collection (Box of 12) – RS 900.00

46.5% Cocoa Dry Fruit Collection (Box of 16) – RS 800.00

Cakes
(All cakes available in Half Kg / 1 Kg sizes)

Cake Name	Half Kg	1 Kg
(v) Dutch Truffle	RS 700	RS 1100
(v) Fruit Premium	RS 700	RS 1100
(v) Pineapple	RS 600	RS 900
(v) Dark Forest	RS 650	RS 950
(v) Butterscotch	RS 650	RS 950
(v) German Chocolate Cake	RS 700	RS 1100
(v) Ferroro Rocher Cake	RS 800	RS 1300
(v) Irish Coffee	RS 650	RS 950
Carrotcake	RS 650	RS 950
Blueberry Cheesecake (Cold Set)	RS 800	RS 1300
Tiramisu	RS 800	RS 1300
New York Cheesecake	RS 800	RS 1300
Choice of Topping (for Cheesecakes):

Plain – 0

Strawberry – 95

Caramel – 95

Blueberry – 95

Lemon Curd – 95

Raspberry – 95

Notes:

GST: 5% Extra

Cakes marked with (v) can be made eggless with an additional charge of RS 30 for 500 grams and RS 60 for 1 kg.

Products marked as eggless are also free from gelatin.""")],
        role="user"
    ),
)

pya = pyaudio.PyAudio()


class GeminiLive:
    def __init__(self, mode=DEFAULT_MODE):
        self.mode = mode
        self.video_mode = mode  # Add video_mode attribute for backward compatibility
        self.audio_stream = None
        self.session = None
        self.out_queue = None
        self.audio_in_queue = None
        self.transcript_manager = TranscriptManager()
        self.receive_audio_task = None
        self.play_audio_task = None

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(
                input,
                "message > ",
            )
            if text.lower() == "q":
                break
            await self.session.send_client_content(turns={"parts": [{"text": text or "."}]}, turn_complete=True)

    def _get_frame(self, cap):
        # Read the frameq
        ret, frame = cap.read()
        # Check if the frame was read successfully
        if not ret:
            return None
        # Fix: Convert BGR to RGB color space
        # OpenCV captures in BGR but PIL expects RGB format
        # This prevents the blue tint in the video feed
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)  # Now using RGB frame
        img.thumbnail([1024, 1024])

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_frames(self):
        # This takes about a second, and will block the whole program
        # causing the audio pipeline to overflow if you don't to_thread it.
        cap = await asyncio.to_thread(
            cv2.VideoCapture, 0
        )  # 0 represents the default camera

        while True:
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

        # Release the VideoCapture object
        cap.release()

    def _get_screen(self):
        sct = mss.mss()
        monitor = sct.monitors[0]

        i = sct.grab(monitor)

        mime_type = "image/jpeg"
        image_bytes = mss.tools.to_png(i.rgb, i.size)
        img = PIL.Image.open(io.BytesIO(image_bytes))

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_screen(self):

        while True:
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            # Use 'audio' parameter instead of 'input' for audio data
            if isinstance(msg, dict) and 'mime_type' in msg and 'audio' in msg['mime_type']:
                await self.session.send_realtime_input(audio=types.Blob(
                    data=msg['data'],
                    mime_type=msg['mime_type']
                ))
            else:
                # For other types of data, determine the appropriate parameter
                await self.session.send_realtime_input(media=msg)

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="")
                # Process input audio transcription (user speech)
                if hasattr(response.server_content, 'input_transcription') and response.server_content.input_transcription:
                    user_text = response.server_content.input_transcription.text
                    # Remove terminal logging, only save to transcript
                    if self.transcript_manager:
                        self.transcript_manager.add_user_transcript(user_text)
                # Process output audio transcription (model speech)
                if hasattr(response.server_content, 'output_transcription') and response.server_content.output_transcription:
                    model_text = response.server_content.output_transcription.text
                    # Remove terminal logging, only save to transcript
                    if self.transcript_manager:
                        self.transcript_manager.add_model_transcript(model_text)

            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                send_text_task = tg.create_task(self.send_text())
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                if self.video_mode == "camera":
                    tg.create_task(self.get_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.get_screen())

                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")

        except asyncio.CancelledError:
            # Save transcript when user exits
            if hasattr(self, 'transcript_manager'):
                self.transcript_manager.save_transcript()
            pass
        except ExceptionGroup as EG:
            # Only close audio_stream if it exists
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                self.audio_stream.close()
            traceback.print_exception(EG)
            # Save transcript on error
            if hasattr(self, 'transcript_manager'):
                self.transcript_manager.save_transcript()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    args = parser.parse_args()
    main = GeminiLive(mode=args.mode)
    asyncio.run(main.run())
