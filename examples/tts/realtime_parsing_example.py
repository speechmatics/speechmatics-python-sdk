"""
Real-time streaming TTS with live text parsing examples.

This demonstrates true real-time TTS where audio generation happens
simultaneously with text parsing - no waiting for complete text processing!
"""

import asyncio
import time
from pathlib import Path
from typing import AsyncIterator

# Assuming the real-time streaming client is available
from speechmatics.tts import RealTimeStreamingTTSClient


async def live_file_parsing_example():
    """Demonstrate real-time file parsing with immediate audio synthesis."""
    print("📖 Real-time File Parsing Example")
    print("Audio starts playing while file is still being read!")
    
    # Create a sample file
    sample_text = """
    Welcome to real-time streaming text-to-speech synthesis.
    
    This is paragraph one. As you can hear, the audio begins immediately,
    even though the system is still reading and parsing the rest of this document.
    
    This is paragraph two. The synthesis happens in real-time as each sentence
    is parsed from the file. There's no waiting for the entire document to load.
    
    This is paragraph three. The system intelligently finds sentence boundaries
    and starts synthesis as soon as it has enough text to work with.
    
    This is the final paragraph. By the time you hear this, the system has
    been continuously reading, parsing, and synthesizing throughout the entire process.
    """
    
    sample_file = Path("realtime_sample.txt")
    sample_file.write_text(sample_text)
    
    try:
        async with RealTimeStreamingTTSClient(
            api_key="your-api-key",
            synthesis_threshold=50,  # Start synthesis after 50 characters
            max_parse_delay=0.05,    # Very responsive parsing
        ) as client:
            
            print("🎵 Starting real-time parsing and synthesis...")
            start_time = time.time()
            chunk_count = 0
            
            async for audio_chunk in client.stream_live_from_file(
                sample_file,
                voice="en-US-neural-1",
                read_delay=0.03,  # Simulate fast reading
            ):
                chunk_count += 1
                elapsed = time.time() - start_time
                
                print(f"🔊 Audio chunk {chunk_count} at {elapsed:.2f}s: {len(audio_chunk)} bytes")
                
                # In real application: await play_audio_immediately(audio_chunk)
                # Simulate audio playback time
                await asyncio.sleep(0.1)
                
            total_time = time.time() - start_time
            print(f"✅ Real-time processing complete in {total_time:.2f}s with {chunk_count} chunks")
            
    finally:
        if sample_file.exists():
            sample_file.unlink()


async def live_typing_simulation():
    """Simulate user typing with immediate TTS synthesis."""
    print("\n⌨️  Live Typing Simulation")
    print("Audio generated as text is typed in real-time!")
    
    async def simulate_typing() -> AsyncIterator[str]:
        """Simulate a user typing text in real-time."""
        text = "Hello there! I am typing this text in real time. Each word appears as I type it. The speech synthesis happens immediately as I finish each sentence. This is truly real-time text-to-speech!"
        
        words = text.split()
        for i, word in enumerate(words):
            yield word + " "
            
            # Simulate typing speed (faster for short words, slower for long ones)
            typing_delay = 0.2 + (len(word) * 0.05)
            await asyncio.sleep(typing_delay)
            
            # Add extra pause after sentences
            if word.endswith(('.', '!', '?')):
                await asyncio.sleep(0.3)
    
    async with RealTimeStreamingTTSClient(
        api_key="your-api-key",
        synthesis_threshold=30,  # Quick synthesis trigger
    ) as client:
        
        print("⌨️  Starting typing simulation...")
        start_time = time.time()
        
        async for audio_chunk in client.stream_live_text_input(
            simulate_typing(),
            voice="en-US-neural-2",
            speed=1.1,
        ):
            elapsed = time.time() - start_time
            print(f"🎵 Live audio at {elapsed:.2f}s: {len(audio_chunk)} bytes")
            
            # In real app: await play_audio_immediately(audio_chunk)
            
        print("✅ Live typing synthesis complete!")


async def live_monitoring_example():
    """Demonstrate real-time monitoring with performance metrics."""
    print("\n📊 Real-time Monitoring Example")
    print("Shows performance metrics during live processing!")
    
    # Create a longer sample for monitoring
    long_text = """
    Real-time Performance Monitoring Demo
    
    """ + "\n\n".join([
        f"Section {i}: This section demonstrates real-time performance monitoring "
        f"during live text-to-speech synthesis. The system tracks processing rates, "
        f"audio generation speed, buffer health, and latency metrics in real-time."
        for i in range(1, 8)
    ])
    
    monitor_file = Path("monitoring_sample.txt")
    monitor_file.write_text(long_text)
    
    try:
        async with RealTimeStreamingTTSClient(api_key="your-api-key") as client:
            
            print("📊 Starting monitored real-time synthesis...")
            
            async for result in client.stream_with_live_monitoring(
                monitor_file,
                voice="en-US-neural-3",
                monitor_interval=0.1,
            ):
                audio_chunk = result["audio_chunk"]
                metrics = result["metrics"]
                status = result["status"]
                
                # Display real-time metrics
                print(f"🎵 Chunk {metrics['chunk_id']}: "
                      f"{len(audio_chunk)} bytes | "
                      f"Rate: {metrics['chars_per_second']:.1f} chars/s | "
                      f"Latency: {metrics['elapsed_time']:.2f}s | "
                      f"RT Ratio: {status['real_time_ratio']:.2f}")
                
                # In real app: await play_audio_with_monitoring(audio_chunk, metrics)
                
            print("✅ Monitored synthesis complete!")
            
    finally:
        if monitor_file.exists():
            monitor_file.unlink()


async def streaming_vs_batch_comparison():
    """Compare real-time streaming vs traditional batch processing."""
    print("\n⚡ Streaming vs Batch Comparison")
    
    test_text = """
    This is a comparison test between real-time streaming synthesis
    and traditional batch processing. In batch mode, you would wait
    for this entire text to be processed before hearing any audio.
    In streaming mode, you hear audio immediately as text is parsed.
    """
    
    test_file = Path("comparison_test.txt")
    test_file.write_text(test_text)
    
    try:
        print("🐌 Simulating BATCH processing (traditional approach):")
        batch_start = time.time()
        
        # Simulate batch processing delay
        print("   ⏳ Loading entire file...")
        await asyncio.sleep(1.0)
        print("   ⏳ Processing all text...")
        await asyncio.sleep(2.0)
        print("   ⏳ Synthesizing complete audio...")
        await asyncio.sleep(3.0)
        
        batch_time = time.time() - batch_start
        print(f"   ✅ Batch complete after {batch_time:.1f}s - NOW audio starts playing")
        
        print("\n🚀 Real-time STREAMING processing:")
        stream_start = time.time()
        
        async with RealTimeStreamingTTSClient(api_key="your-api-key") as client:
            first_audio = True
            
            async for audio_chunk in client.stream_live_from_file(
                test_file,
                read_delay=0.02,  # Fast parsing
            ):
                if first_audio:
                    first_audio_time = time.time() - stream_start
                    print(f"   🎵 FIRST audio at {first_audio_time:.2f}s - Audio playing while still parsing!")
                    first_audio = False
                    
                # Continue processing...
                
        stream_total = time.time() - stream_start
        print(f"   ✅ Streaming complete in {stream_total:.1f}s total")
        
        print(f"\n📈 Results:")
        print(f"   Batch: {batch_time:.1f}s wait before ANY audio")
        print(f"   Streaming: {first_audio_time:.2f}s to FIRST audio ({batch_time/first_audio_time:.1f}x faster!)")
        
    finally:
        if test_file.exists():
            test_file.unlink()


async def live_document_reader():
    """Simulate a live document reader with real-time TTS."""
    print("\n📚 Live Document Reader Simulation")
    print("Simulates reading a document with real-time speech synthesis!")
    
    # Simulate a document being written/received in real-time
    async def live_document_stream() -> AsyncIterator[str]:
        """Simulate a document being written or received live."""
        sentences = [
            "Breaking news: Real-time text-to-speech technology has reached new heights. ",
            "Scientists have developed a system that can synthesize speech as text is being written. ",
            "This breakthrough enables immediate audio feedback for live content creation. ",
            "Applications include live transcription, real-time translation, and accessibility tools. ",
            "The system processes text incrementally, starting synthesis before complete sentences are finished. ",
            "This represents a significant advancement in human-computer interaction. ",
            "Users can now hear their text being spoken as they type or as content arrives. ",
            "The technology promises to revolutionize how we interact with text-based systems. "
        ]
        
        for sentence in sentences:
            # Simulate sentence arriving word by word
            words = sentence.split()
            for word in words:
                yield word + " "
                await asyncio.sleep(0.15)  # Simulate writing/receiving speed
                
            # Pause between sentences
            await asyncio.sleep(0.5)
    
    async with RealTimeStreamingTTSClient(
        api_key="your-api-key",
        synthesis_threshold=40,  # Start synthesis quickly
    ) as client:
        
        print("📰 Starting live document reader...")
        
        async for audio_chunk in client.stream_live_text_input(
            live_document_stream(),
            voice="en-US-neural-1",
            output_format="wav",
        ):
            print(f"🔊 Live audio: {len(audio_chunk)} bytes")
            # In real app: await play_live_audio(audio_chunk)
            
        print("✅ Live document reading complete!")


async def main():
    """Run all real-time streaming examples."""
    print("🚀 Real-time Streaming TTS Examples")
    print("=" * 60)
    print("🎯 Audio synthesis happens WHILE text is being parsed!")
    print("=" * 60)
    
    examples = [
        live_file_parsing_example,
        live_typing_simulation,
        live_monitoring_example,
        streaming_vs_batch_comparison,
        live_document_reader,
    ]
    
    for example in examples:
        try:
            await example()
        except Exception as e:
            print(f"❌ Example failed: {e}")
        
        print("\n" + "-" * 40 + "\n")
        await asyncio.sleep(1)
    
    print("🎉 All real-time streaming examples completed!")
    print("\n💡 Key Benefits Demonstrated:")
    print("   • Audio starts immediately (no waiting for complete parsing)")
    print("   • Continuous synthesis during text processing")
    print("   • Real-time performance monitoring")
    print("   • Live input processing (typing, streaming content)")
    print("   • Intelligent boundary detection for optimal synthesis")


if __name__ == "__main__":
    print("⚠️  Remember to set your actual Speechmatics API key!")
    print("🎧 In real usage, replace print statements with actual audio playback!")
    asyncio.run(main())
