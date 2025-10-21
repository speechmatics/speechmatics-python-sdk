"""
Example usage of the Streaming TTS Client.

This example demonstrates real-time text-to-speech streaming with chunked processing,
WebSocket communication, and incremental audio delivery.
"""

import asyncio
import io
from pathlib import Path

# Assuming the streaming client is available
from speechmatics.tts import StreamingTTSClient


async def basic_streaming_example():
    """Basic streaming TTS example."""
    print("🎵 Basic Streaming TTS Example")
    
    text = """
    This is a demonstration of streaming text-to-speech synthesis.
    The text is being processed in real-time, chunk by chunk.
    You should hear audio being generated as each segment is processed.
    This enables immediate playback without waiting for the entire text to be synthesized.
    """
    
    async with StreamingTTSClient(api_key="your-api-key") as client:
        print("📝 Starting streaming synthesis...")
        
        audio_chunks = []
        async for audio_chunk in client.stream_speech(
            text,
            voice="en-US-neural-1",
            output_format="wav",
            sample_rate=22050
        ):
            print(f"🔊 Received audio chunk: {len(audio_chunk)} bytes")
            audio_chunks.append(audio_chunk)
            
            # In a real application, you would play this chunk immediately
            # await play_audio_chunk(audio_chunk)
            
        print(f"✅ Streaming complete! Total chunks: {len(audio_chunks)}")
        
        # Save complete audio
        with open("streaming_output.wav", "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)


async def file_streaming_example():
    """Stream TTS from a text file."""
    print("\n📄 File Streaming TTS Example")
    
    # Create a sample text file
    sample_text = """
    Chapter 1: The Beginning
    
    In the realm of streaming text-to-speech, we embark on a journey of real-time audio generation.
    Each sentence flows seamlessly into the next, creating a continuous stream of synthesized speech.
    
    The technology behind this process involves breaking down large texts into manageable chunks,
    processing them through advanced neural networks, and delivering audio incrementally.
    
    This approach enables immediate playback, reduced memory usage, and better user experience
    for applications dealing with long-form content like audiobooks, articles, and documents.
    """
    
    # Write sample file
    sample_file = Path("sample_text.txt")
    sample_file.write_text(sample_text)
    
    try:
        async with StreamingTTSClient(api_key="your-api-key") as client:
            print(f"📖 Streaming from file: {sample_file}")
            
            chunk_count = 0
            async for audio_chunk in client.stream_from_file(
                sample_file,
                voice="en-US-neural-2",
                output_format="mp3",
                speed=1.1
            ):
                chunk_count += 1
                print(f"🎵 File chunk {chunk_count}: {len(audio_chunk)} bytes")
                
                # In real usage: await play_audio_chunk(audio_chunk)
                
            print(f"✅ File streaming complete! Processed {chunk_count} chunks")
            
    finally:
        # Cleanup
        if sample_file.exists():
            sample_file.unlink()


async def incremental_file_streaming_example():
    """Stream very large files with incremental reading."""
    print("\n📚 Incremental File Streaming Example")
    
    # Create a larger sample file
    large_text = """
    The Art of Streaming Text-to-Speech
    
    """ + "\n\n".join([
        f"Paragraph {i}: This is a demonstration of incremental file processing. "
        f"The system reads the file in chunks and processes them as they become available. "
        f"This approach is particularly useful for very large documents, books, or articles "
        f"where loading the entire content into memory might not be feasible."
        for i in range(1, 21)
    ])
    
    large_file = Path("large_sample.txt")
    large_file.write_text(large_text)
    
    try:
        async with StreamingTTSClient(
            api_key="your-api-key",
            chunk_size=300,  # Smaller chunks for demo
            overlap_size=30
        ) as client:
            print(f"📖 Incremental streaming from: {large_file}")
            
            chunk_count = 0
            total_bytes = 0
            
            async for audio_chunk in client.stream_from_file_incremental(
                large_file,
                voice="en-US-neural-3",
                output_format="wav",
                read_chunk_size=1024  # Read 1KB at a time
            ):
                chunk_count += 1
                total_bytes += len(audio_chunk)
                print(f"🎵 Incremental chunk {chunk_count}: {len(audio_chunk)} bytes "
                      f"(Total: {total_bytes} bytes)")
                
                # Simulate real-time playback delay
                await asyncio.sleep(0.1)
                
            print(f"✅ Incremental streaming complete! "
                  f"Chunks: {chunk_count}, Total audio: {total_bytes} bytes")
            
    finally:
        # Cleanup
        if large_file.exists():
            large_file.unlink()


async def real_time_playback_simulation():
    """Simulate real-time audio playback with streaming."""
    print("\n🎮 Real-time Playback Simulation")
    
    text = """
    Welcome to the real-time streaming demonstration.
    This example simulates how you would integrate streaming TTS
    with an audio playback system for immediate user experience.
    """
    
    class AudioPlayer:
        """Simulated audio player."""
        
        def __init__(self):
            self.buffer = io.BytesIO()
            self.playing = False
            
        async def add_chunk(self, audio_chunk: bytes):
            """Add audio chunk to playback buffer."""
            self.buffer.write(audio_chunk)
            if not self.playing:
                await self.start_playback()
                
        async def start_playback(self):
            """Start audio playback (simulated)."""
            self.playing = True
            print("🔊 Audio playback started...")
            
            # Simulate playback time
            await asyncio.sleep(1.0)
            
            print("🔇 Audio playback finished")
            self.playing = False
    
    player = AudioPlayer()
    
    async with StreamingTTSClient(api_key="your-api-key") as client:
        print("🎵 Starting real-time synthesis and playback...")
        
        # Process streaming TTS and playback concurrently
        async for audio_chunk in client.stream_speech(
            text,
            voice="en-US-neural-1",
            output_format="wav"
        ):
            print(f"📦 Received chunk: {len(audio_chunk)} bytes")
            await player.add_chunk(audio_chunk)
            
        print("✅ Real-time streaming and playback complete!")


async def error_handling_example():
    """Demonstrate error handling in streaming TTS."""
    print("\n⚠️  Error Handling Example")
    
    async with StreamingTTSClient(api_key="invalid-key") as client:
        try:
            async for audio_chunk in client.stream_speech("Test text"):
                print(f"Chunk: {len(audio_chunk)} bytes")
                
        except Exception as e:
            print(f"❌ Error occurred: {type(e).__name__}: {e}")
            print("🔧 In production, implement proper error recovery")


async def main():
    """Run all streaming TTS examples."""
    print("🚀 Speechmatics Streaming TTS Examples")
    print("=" * 50)
    
    examples = [
        basic_streaming_example,
        file_streaming_example,
        incremental_file_streaming_example,
        real_time_playback_simulation,
        error_handling_example,
    ]
    
    for example in examples:
        try:
            await example()
        except Exception as e:
            print(f"❌ Example failed: {e}")
        
        print("\n" + "-" * 30 + "\n")
        await asyncio.sleep(1)  # Brief pause between examples
    
    print("🎉 All examples completed!")


if __name__ == "__main__":
    # Note: Replace "your-api-key" with actual Speechmatics API key
    print("⚠️  Remember to set your actual Speechmatics API key!")
    asyncio.run(main())
