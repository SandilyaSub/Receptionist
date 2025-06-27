import asyncio
import base64
import json
import logging
import os
import audioop

from google import genai
from google.genai import types
import websockets

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- Gemini API Configuration ---
# It's recommended to use environment variables for sensitive data like API keys.

# This is the detailed system instruction for the bakery receptionist persona.
SYSTEM_INSTRUCTIONS = """

You are working as a receptionist at Happy Endings bakery taking user orders. 

As soon as a connection is established, greet the customer and ask for his name.

Be courteous and respond well. Do this in an Indian accent.
Speak in short and simple sentences.

At the end of the conversation , the expectation is that you would have figured out all the relevant details that a baker needs to make a cake and keep it ready. You will tell the customer the price that would be incurred and a timeslot by when the cake would be ready, so that he could pick it up. The menu is towards the bottom of the instructions. 

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

The time a customer can come and pick the cake up would be 6hrs for making the cake and the cake is made only during the working hours. 
Open Hours: 10am IST - 9pm IST

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

Products marked as eggless are also free from gelatin.

"""

# Load API key from environment variable or use a default for local testing
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDmnCmel5kqMzi7ShnbNiYrcUxzA_kaDkM")

client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key=GEMINI_API_KEY,
)

# Configuration for Gemini session
GEMINI_CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
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
        parts=[types.Part.from_text(text=SYSTEM_INSTRUCTIONS)]
    )
)

# Menu items (part of the system instructions)
# (v) Fruit Premium	RS 700	RS 1100
# (v) Pineapple	RS 600	RS 900
# (v) Dark Forest	RS 650	RS 950
# (v) Butterscotch	RS 650	RS 950
# (v) German Chocolate Cake	RS 700	RS 1100
# (v) Ferroro Rocher Cake	RS 800	RS 1300
# (v) Irish Coffee	RS 650	RS 950
# Carrotcake	RS 650	RS 950
# Blueberry Cheesecake (Cold Set)	RS 800	RS 1300
# Tiramisu	RS 800	RS 1300
# New York Cheesecake	RS 800	RS 1300

# Notes:

# GST: 5% Extra

# Cakes marked with (v) can be made eggless with an additional charge of RS 30 for 500 grams and RS 60 for 1 kg.

# Products marked as eggless are also free from gelatin."""

# Configuration for Gemini session

# --- Audio Configuration ---
EXOTEL_SAMPLE_RATE = 8000
GEMINI_SAMPLE_RATE = 16000  # Gemini supports 16k and 24k. 16k is sufficient.
AUDIO_CHANNELS = 1
AUDIO_WIDTH = 2  # 16-bit PCM = 2 bytes

# --- Audio Utilities ---

def resample_audio(data: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resamples audio data using audioop."""
    try:
        # audioop.ratecv returns (new_data, new_state)
        resampled_data, _ = audioop.ratecv(data, AUDIO_WIDTH, AUDIO_CHANNELS, from_rate, to_rate, None)
        return resampled_data
    except audioop.error as e:
        logging.error(f"Audio resampling failed: {e}")
        return data # Return original data on error

# --- WebSocket Handler Tasks ---

async def forward_to_gemini(websocket, gemini_session):
    """Receives audio from Exotel, processes it, and sends it to Gemini."""
    silence_counter = 0
    max_silence_frames = 5  # Number of silent frames before sending end marker
    last_audio_time = None
    silence_timeout = 1.0  # Seconds of silence to trigger end marker
    
    while True:
        try:
            message = await websocket.recv()
            data = json.loads(message)

            # Process only media messages
            if data.get("event") == "media":
                media_payload = data.get("media", {}).get("payload")
                if media_payload:
                    # 1. Decode from Base64
                    raw_audio = base64.b64decode(media_payload)
                    
                    # Check if this is silence (very low amplitude)
                    is_silence = False
                    if len(raw_audio) > 0:
                        # Simple silence detection - check if max amplitude is below threshold
                        try:
                            max_amplitude = max(abs(b - 128) for b in raw_audio) if len(raw_audio) > 0 else 0
                            is_silence = max_amplitude < 5  # Threshold for silence
                            
                            if is_silence:
                                silence_counter += 1
                                logging.info(f"Detected silence frame {silence_counter}/{max_silence_frames}")
                            else:
                                silence_counter = 0
                                last_audio_time = asyncio.get_event_loop().time()
                        except Exception as e:
                            logging.error(f"Error in silence detection: {e}")
                    
                    # 2. Resample from 8kHz to 16kHz
                    resampled_audio = resample_audio(raw_audio, EXOTEL_SAMPLE_RATE, GEMINI_SAMPLE_RATE)
                    
                    # 3. Send to Gemini with proper MIME type
                    await gemini_session.send_realtime_input(
                        audio=types.Blob(
                            data=resampled_audio,
                            mime_type=f"audio/pcm;rate={GEMINI_SAMPLE_RATE}"
                        )
                    )
                    
                    # If we've detected enough silence, send a text message to signal end of audio
                    current_time = asyncio.get_event_loop().time()
                    if silence_counter >= max_silence_frames or \
                       (last_audio_time and current_time - last_audio_time > silence_timeout):
                        logging.info("Detected end of speech, sending end marker")
                        # Signal end of turn using send_realtime_input with end-of-turn text
                        await gemini_session.send_realtime_input(text="[END_OF_TURN]")
                        silence_counter = 0

        except websockets.exceptions.ConnectionClosed:
            logging.info("Client connection closed in forward_to_gemini.")
            # Signal end of turn using send_realtime_input when connection closes
            try:
                await gemini_session.send_realtime_input(text="[END_OF_TURN]")
                logging.info("Sent end-of-turn signal after connection closed")
            except Exception as e:
                logging.error(f"Error sending end-of-turn signal: {e}")
            # Don't break the loop - allow forward_to_exotel to continue receiving responses
            # We'll return from this function but the TaskGroup will keep other tasks running
            return
        except Exception as e:
            logging.error(f"Error in forward_to_gemini: {e}", exc_info=True)
            break

async def forward_to_exotel(websocket, gemini_session):
    """Receives audio from Gemini, processes it, and sends it back to Exotel."""
    logging.info("Starting to listen for responses from Gemini...")
    logging.info(f"Gemini session object: {gemini_session}")
    logging.info(f"Gemini session type: {type(gemini_session)}")
    logging.info(f"Gemini session attributes: {dir(gemini_session)}")
    
    try:
        logging.info("About to start iterating through gemini_session.receive()")
        response_count = 0
        async for response in gemini_session.receive():
            response_count += 1
            logging.info(f"Received response #{response_count} from Gemini: {type(response)}")
            
            # Log the raw response for debugging
            logging.info(f"Raw response object: {response}")
            
            # Log all available attributes and their values for debugging
            for attr in dir(response):
                if not attr.startswith('_'):
                    try:
                        value = getattr(response, attr)
                        if callable(value):
                            logging.info(f"Response has callable attribute: {attr}")
                        else:
                            logging.info(f"Response.{attr} = {value}")
                    except Exception as e:
                        logging.info(f"Error accessing attribute {attr}: {e}")
                        
            # Try to inspect the response as a dictionary if possible
            try:
                if hasattr(response, '__dict__'):
                    logging.info(f"Response __dict__: {response.__dict__}")
                if hasattr(response, 'to_dict') and callable(response.to_dict):
                    logging.info(f"Response to_dict(): {response.to_dict()}")
            except Exception as e:
                logging.info(f"Error inspecting response as dict: {e}")
                
            # Check if response is a dictionary itself
            if isinstance(response, dict):
                logging.info(f"Response is a dictionary with keys: {response.keys()}")
                if 'audio' in response:
                    logging.info(f"Found 'audio' key in response dictionary")
                if 'text' in response:
                    logging.info(f"Found 'text' key with value: {response['text']}")
                if 'content' in response:
                    logging.info(f"Found 'content' key in response dictionary")
                    if isinstance(response['content'], dict) and 'audio' in response['content']:
                        logging.info(f"Found 'audio' in response['content']")
            
            # Check if response has a content attribute that might be a dictionary
            if hasattr(response, 'content'):
                content = response.content
                if isinstance(content, dict):
                    logging.info(f"Response.content is a dictionary with keys: {content.keys()}")
                    if 'audio' in content:
                        logging.info(f"Found 'audio' key in response.content dictionary")
                elif hasattr(content, '__dict__'):
                    logging.info(f"Response.content.__dict__: {content.__dict__}")
                    
            # Check if response has a parts attribute that might contain audio
            if hasattr(response, 'parts'):
                logging.info(f"Response has 'parts' attribute: {response.parts}")
                for i, part in enumerate(response.parts):
                    logging.info(f"Examining part {i}: {type(part)}")
                    if hasattr(part, 'audio') and part.audio:
                        logging.info(f"Found audio in part {i}")
                    if hasattr(part, 'text') and part.text:
                        logging.info(f"Found text in part {i}: {part.text}")
                    if hasattr(part, '__dict__'):
                        logging.info(f"Part {i} __dict__: {part.__dict__}")
                        
            # Check for response_type attribute
            if hasattr(response, 'response_type'):
                logging.info(f"Response has response_type: {response.response_type}")
                
            # Check for candidates attribute
            if hasattr(response, 'candidates'):
                logging.info(f"Response has candidates: {len(response.candidates)}")
                for i, candidate in enumerate(response.candidates):
                    logging.info(f"Examining candidate {i}: {type(candidate)}")
                    if hasattr(candidate, 'content') and candidate.content:
                        logging.info(f"Candidate {i} has content")
                        if hasattr(candidate.content, 'parts'):
                            for j, part in enumerate(candidate.content.parts):
                                logging.info(f"Examining candidate {i} part {j}: {type(part)}")
                                if hasattr(part, 'audio') and part.audio:
                                    logging.info(f"Found audio in candidate {i} part {j}")
                                if hasattr(part, 'text') and part.text:
                                    logging.info(f"Found text in candidate {i} part {j}: {part.text}")
                                if hasattr(part, '__dict__'):
                                    logging.info(f"Candidate {i} part {j} __dict__: {part.__dict__}")

            
            # Check for text responses
            if hasattr(response, 'text') and response.text:
                logging.info(f"Text response received: {response.text}")
            
            # Check for audio responses in different possible formats
            audio_data = None
            
            # Try different possible attribute names for audio data
            if hasattr(response, 'audio') and response.audio:
                audio_data = response.audio
                logging.info(f"Found audio in response.audio: {len(audio_data)} bytes")
            elif hasattr(response, 'audio_content') and response.audio_content:
                audio_data = response.audio_content
                logging.info(f"Found audio in response.audio_content: {len(audio_data)} bytes")
            elif hasattr(response, 'content') and hasattr(response.content, 'audio'):
                audio_data = response.content.audio
                logging.info(f"Found audio in response.content.audio: {len(audio_data)} bytes")
            
            # If we found audio data, process and send it
            if audio_data:
                try:
                    # 1. Resample from Gemini's rate down to Exotel's 8kHz
                    resampled_audio = resample_audio(audio_data, GEMINI_SAMPLE_RATE, EXOTEL_SAMPLE_RATE)
                    # 2. Encode to Base64
                    base64_audio = base64.b64encode(resampled_audio).decode('utf-8')
                    # 3. Wrap in Exotel's JSON format and send
                    exotel_payload = {
                        "event": "media",
                        "media": {
                            "payload": base64_audio
                        }
                    }
                    await websocket.send(json.dumps(exotel_payload))
                    logging.info(f"Successfully sent {len(base64_audio)} bytes of audio to Exotel")
                except Exception as e:
                    logging.error(f"Error processing/sending audio: {e}", exc_info=True)
            else:
                logging.warning("Response contained no audio data")
    except Exception as e:
        logging.error(f"Error in forward_to_exotel main loop: {e}", exc_info=True)


async def handler(websocket):
    """Handles a single WebSocket connection from Exotel."""
    logging.info(f"New connection from {websocket.remote_address}")
    try:
        # 1. Wait for the 'start' message from Exotel
        start_message = await websocket.recv()
        start_data = json.loads(start_message)

        if start_data.get("event") == "start":
            stream_sid = start_data.get("stream_sid", "N/A")
            call_sid = start_data.get("start", {}).get("call_sid", "N/A")
            logging.info(f"[{stream_sid}] Call started for call SID: {call_sid}")
        else:
            logging.warning("First message was not a 'start' event. Closing connection.")
            return

        # 2. Initialize Gemini session
        # Using gemini-2.5-flash-preview-native-audio-dialog as requested by the user
        async with client.aio.live.connect(model="models/gemini-2.5-flash-preview-native-audio-dialog", config=GEMINI_CONFIG) as session:
            logging.info(f"[{stream_sid}] Gemini session started.")

            # 3. Start bidirectional streaming tasks using separate tasks for better control
            try:
                # Create tasks for bidirectional audio streaming
                to_gemini_task = asyncio.create_task(forward_to_gemini(websocket, session))
                to_exotel_task = asyncio.create_task(forward_to_exotel(websocket, session))
                
                logging.info(f"[{stream_sid}] Created separate tasks for bidirectional streaming")
                
                # Wait for the forward_to_gemini task to complete (client disconnects)
                await to_gemini_task
                logging.info(f"[{stream_sid}] forward_to_gemini task completed")
                
                # Don't cancel the forward_to_exotel task - let it continue receiving responses
                # Wait for a reasonable amount of time for Gemini to respond
                try:
                    logging.info(f"[{stream_sid}] Waiting for Gemini responses (30 seconds)...")
                    await asyncio.wait_for(to_exotel_task, timeout=30.0)
                except asyncio.TimeoutError:
                    logging.info(f"[{stream_sid}] Timeout waiting for Gemini responses")
                finally:
                    # Now we can cancel the forward_to_exotel task if it's still running
                    if not to_exotel_task.done():
                        to_exotel_task.cancel()
                        logging.info(f"[{stream_sid}] Cancelled forward_to_exotel task")
            except Exception as e:
                logging.error(f"[{stream_sid}] Error in task management: {e}", exc_info=True)
            finally:
                logging.info(f"[{stream_sid}] Session tasks cleaned up.")

    except websockets.exceptions.ConnectionClosed as e:
        logging.info(f"Connection closed: {e}")
    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)

# --- Main Server Logic ---

async def main():
    """Starts the WebSocket server."""
    port = int(os.environ.get("PORT", 8081))
    logging.info(f"Starting WebSocket server on port {port}...")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server shutting down.")
