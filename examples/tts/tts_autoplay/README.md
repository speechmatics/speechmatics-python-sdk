# Speechmatics TTS Async Streaming API Client

This example shows how to use the Speechmatics TTS API to generate audio from text and autoplay it using sounddevice through the systems default audio output device.
You must have an audio output device configured on their system for this example to work.
## How it Works

There are two main components in this example, an audio generator and an audio player. These components are run concurrently using asyncio as tasks, ochestrated by the main() function, to generate and play audio in real-time.
### audio_generator() 

This producer function connects to the Speechmatics TTS API using the AsyncClient. It calls client.generate() with your text, the voice you want to use, and the output format - RAW_PCM_16000 in this example. 
The code iterates over the audio data as it is streamed in chunks (iter_chunked), and accumulates in a bytearray buffer. 
The while len(buffer) >= 2 loop reads each audio sample containing 2 bytes, from the buffer, and converts it to a numpy array of int-16 values, which is then put into the audio_queue.
The processed 2 byte sample is then removed from the front of the buffer. 
END_OF_STREAM is used as a sentinel value to signal the end of the audio stream, with no more audio data to process.
If an error occurs during audio generation, the END_OF_STREAM sentinel value is still put into the queue to signal the end of the audio stream to prevent the consumer, audio_player(), from getting stuck in an infinite loop, and raises the exception.
### audio_player() 

This consumer function initialises a sounddevice OutputStream, which is responsible for streaming the audio data to the default audio output device. Within the outputstream, the while True loop means there is continous processing of the incoming audio data. 
sample = await asyncio.wait_for(play_queue.get(), timeout=0.1) fetches the next sample from the queue, or waits for 0.1 seconds if the queue is empty. 
If the sample is END_OF_STREAM, the while loop breaks and the audio player exits. 
If the sample is not END_OF_STREAM, it is converted to a numpy array of int-16 values and written to the audio output device using the sounddevice OutputStream.
play_queue.task_done() is called to signal that the sample has been processed. 
If an error occurs during audio playback, the END_OF_STREAM sentinel value is still put into the queue to signal the end of the audio stream to prevent the audio_player() from getting stuck in an infinite loop, and raises the exception.

## Installation

```bash
pip install speechmatics-tts
```

## Usage

To run the example, use the following command:

```bash
python tts_stream_example.py
```

## Environment Variables

The client supports the following environment variables:

- `SPEECHMATICS_API_KEY`: Your Speechmatics API key
