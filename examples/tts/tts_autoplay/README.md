# Speechmatics TTS Async Streaming API Client

This example shows how to use the Speechmatics TTS API to generate audio from text and autoplay it using sounddevice.

# audio_generator() 
This producer function takes a string of text, fetches and decodes audio chunks from the Speechmatics TTS API, and converts the audio data into a queue of samples, ready for the audio player to consume.


# audio_player() 
This consumer function continuously reads raw audio data from the queue, converts to numpy arrays, and writes the chunk to the audio stream. 
This audio stream is then played in real-time using sounddevice through the systems default audio output device.

# main()
This function orchestrates and creates asyncio tasks for the audio_generator() and audio_player() functions, and then runs them using asyncio.gather(). This allows the audio_generator() and audio_player() functions to run concurrently, and the audio_player() function to autoplay the audio as it is generated.

## Installation

```bash
pip install speechmatics-tts
```

## Usage

To run the example, use the following command:

```bash
python tts_stream_example.py
```

This example will generate audio from text and autoplay it using sounddevice. You will need a configured output audio device for it to work.

## Environment Variables

The client supports the following environment variables:

- `SPEECHMATICS_API_KEY`: Your Speechmatics API key


