"""
Real-time streaming TTS client with live text parsing and synthesis.

This module provides true real-time TTS where audio generation happens
simultaneously with text parsing, providing immediate audio output
as text becomes available.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import AsyncGenerator, Optional, Union, List, Dict, Any, AsyncIterator
from pathlib import Path
import time

import aiohttp
import aiofiles

from ._auth import AuthBase, StaticKeyAuth
from ._exceptions import AuthenticationError, TransportError
from ._logging import get_logger
from ._models import ConnectionConfig


class RealTimeStreamingTTSClient:
    """
    Real-time streaming TTS client with live text parsing.
    
    This client provides true real-time TTS where:
    - Text is parsed/read incrementally from source
    - Audio synthesis happens immediately as text becomes available
    - Audio chunks are delivered while more text is still being processed
    - No waiting for complete text parsing before synthesis begins
    
    Examples:
        Live file parsing with immediate audio:
            >>> async with RealTimeStreamingTTSClient(api_key="key") as client:
            ...     async for audio_chunk in client.stream_live_from_file("book.txt"):
            ...         await play_audio_immediately(audio_chunk)
            ...         # Audio plays while file is still being read!
                        
        Real-time text input streaming:
            >>> async for audio_chunk in client.stream_live_text_input():
            ...     await play_audio_chunk(audio_chunk)
            ...     # Audio generated as user types!
    """
    
    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
        parse_chunk_size: int = 256,  # Smaller for real-time parsing
        synthesis_threshold: int = 100,  # Start synthesis after this many chars
        max_parse_delay: float = 0.1,  # Max delay between parse chunks (seconds)
    ) -> None:
        """Initialize real-time streaming TTS client."""
        self._auth = auth or StaticKeyAuth(api_key)
        self._url = url or "wss://tts.api.speechmatics.com/v1"
        self._conn_config = conn_config or ConnectionConfig()
        
        # Real-time parsing configuration
        self._parse_chunk_size = parse_chunk_size
        self._synthesis_threshold = synthesis_threshold
        self._max_parse_delay = max_parse_delay
        
        self._logger = get_logger(__name__)
        self._session: Optional[aiohttp.ClientSession] = None
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        
    async def __aenter__(self) -> RealTimeStreamingTTSClient:
        """Async context manager entry."""
        await self._ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with cleanup."""
        await self.close()
        
    async def _ensure_session(self) -> None:
        """Ensure aiohttp session is created."""
        if not self._session:
            self._session = aiohttp.ClientSession()
            
    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        if self._websocket:
            await self._websocket.close()
            self._websocket = None
            
        if self._session:
            await self._session.close()
            self._session = None
            
    async def _connect_websocket(self) -> aiohttp.ClientWebSocketResponse:
        """Establish WebSocket connection for real-time streaming."""
        await self._ensure_session()
        
        headers = await self._auth.get_auth_headers()
        
        self._websocket = await self._session.ws_connect(
            f"{self._url}/realtime-synthesize",
            headers=headers,
            heartbeat=30
        )
        
        return self._websocket
        
    async def _find_synthesis_boundary(self, text: str) -> int:
        """
        Find optimal boundary for synthesis (sentence/phrase end).
        
        Returns position where synthesis should start, or -1 if not ready.
        """
        if len(text) < self._synthesis_threshold:
            return -1
            
        # Look for sentence endings first
        sentence_patterns = [r'[.!?]\s+', r'[.!?]$']
        for pattern in sentence_patterns:
            matches = list(re.finditer(pattern, text))
            if matches:
                return matches[-1].end()
                
        # Look for phrase boundaries
        phrase_patterns = [r'[,;:]\s+', r'\s+and\s+', r'\s+but\s+', r'\s+or\s+']
        for pattern in phrase_patterns:
            matches = list(re.finditer(pattern, text))
            if matches and len(text[:matches[-1].end()]) >= self._synthesis_threshold:
                return matches[-1].end()
                
        # If text is long enough, find word boundary
        if len(text) >= self._synthesis_threshold * 2:
            word_boundaries = [m.start() for m in re.finditer(r'\s+', text)]
            if word_boundaries:
                # Find boundary closest to middle
                target = len(text) // 2
                closest = min(word_boundaries, key=lambda x: abs(x - target))
                return closest
                
        return -1
        
    async def stream_live_from_file(
        self,
        file_path: Union[str, Path],
        *,
        voice: Optional[str] = None,
        output_format: str = "wav",
        sample_rate: Optional[int] = None,
        speed: Optional[float] = None,
        read_delay: float = 0.05,  # Simulate real-time reading
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS with real-time file parsing and immediate synthesis.
        
        This method reads the file incrementally and starts synthesis
        as soon as enough text is available, without waiting for
        complete file reading.
        
        Args:
            file_path: Path to text file
            read_delay: Delay between file reads (simulates real-time input)
            
        Yields:
            Audio chunks as they're generated from live parsing
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        ws = await self._connect_websocket()
        
        try:
            # Send synthesis configuration
            config = {
                "type": "start_realtime_synthesis",
                "voice": voice,
                "output_format": output_format,
                "sample_rate": sample_rate,
                "speed": speed,
                "realtime_mode": True,
            }
            await ws.send_str(json.dumps({k: v for k, v in config.items() if v is not None}))
            
            # Start concurrent tasks for parsing and audio collection
            parse_task = asyncio.create_task(
                self._parse_file_realtime(ws, file_path, read_delay)
            )
            
            # Yield audio chunks as they become available
            async for audio_chunk in self._collect_realtime_audio(ws):
                yield audio_chunk
                
        finally:
            # Cleanup
            if not parse_task.done():   
                parse_task.cancel()
            await ws.send_str(json.dumps({"type": "end_realtime_synthesis"}))
            
    async def _parse_file_realtime(
        self, 
        ws: aiohttp.ClientWebSocketResponse, 
        file_path: Path, 
        read_delay: float
    ) -> None:
        """Parse file in real-time and send text chunks for immediate synthesis."""
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            text_buffer = ""
            chunk_id = 0
            
            while True:
                # Read small chunk from file
                file_chunk = await f.read(self._parse_chunk_size)
                if not file_chunk:
                    break
                    
                text_buffer += file_chunk
                self._logger.debug(f"Read chunk: {len(file_chunk)} chars, buffer: {len(text_buffer)} chars")
                
                # Check if we have enough text for synthesis
                synthesis_pos = await self._find_synthesis_boundary(text_buffer)
                
                if synthesis_pos > 0:
                    # Extract text for synthesis
                    synthesis_text = text_buffer[:synthesis_pos].strip()
                    text_buffer = text_buffer[synthesis_pos:]
                    
                    if synthesis_text:
                        # Send for immediate synthesis
                        message = {
                            "type": "realtime_text_chunk",
                            "chunk_id": chunk_id,
                            "text": synthesis_text,
                            "timestamp": time.time(),
                        }
                        await ws.send_str(json.dumps(message))
                        chunk_id += 1
                        
                        self._logger.info(f"Sent for synthesis: '{synthesis_text[:50]}...' ({len(synthesis_text)} chars)")
                
                # Simulate real-time reading delay
                await asyncio.sleep(read_delay)
                
            # Process remaining buffer
            if text_buffer.strip():
                message = {
                    "type": "realtime_text_chunk",
                    "chunk_id": chunk_id,
                    "text": text_buffer.strip(),
                    "timestamp": time.time(),
                    "final": True,
                }
                await ws.send_str(json.dumps(message))
                
    async def _collect_realtime_audio(
        self, 
        ws: aiohttp.ClientWebSocketResponse
    ) -> AsyncGenerator[bytes, None]:
        """Collect audio chunks in real-time as they're generated."""
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                
                if data.get("type") == "realtime_audio_chunk":
                    # Decode and yield audio immediately
                    import base64
                    audio_data = base64.b64decode(data["audio"])
                    
                    # Log timing information
                    chunk_id = data.get("chunk_id", "unknown")
                    latency = time.time() - data.get("synthesis_start", time.time())
                    self._logger.info(f"Audio chunk {chunk_id}: {len(audio_data)} bytes (latency: {latency:.3f}s)")
                    
                    yield audio_data
                    
                elif data.get("type") == "synthesis_complete":
                    self._logger.info("Real-time synthesis complete")
                    break
                    
                elif data.get("type") == "error":
                    raise TransportError(f"Real-time synthesis error: {data.get('message')}")
                    
            elif msg.type == aiohttp.WSMsgType.ERROR:
                raise TransportError(f"WebSocket error: {ws.exception()}")
                
    async def stream_live_text_input(
        self,
        text_source: AsyncIterator[str],
        *,
        voice: Optional[str] = None,
        output_format: str = "wav",
        sample_rate: Optional[int] = None,
        speed: Optional[float] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS from live text input (e.g., user typing, live transcription).
        
        Args:
            text_source: Async iterator providing text chunks as they become available
            
        Yields:
            Audio chunks generated from live text input
            
        Examples:
            >>> async def user_typing():
            ...     # Simulate user typing
            ...     words = "Hello world this is live typing".split()
            ...     for word in words:
            ...         yield word + " "
            ...         await asyncio.sleep(0.5)  # Typing delay
            ...
            >>> async for audio in client.stream_live_text_input(user_typing()):
            ...     await play_audio_immediately(audio)
        """
        ws = await self._connect_websocket()
        
        try:
            # Send configuration
            config = {
                "type": "start_live_input_synthesis",
                "voice": voice,
                "output_format": output_format,
                "sample_rate": sample_rate,
                "speed": speed,
                "live_input_mode": True,
            }
            await ws.send_str(json.dumps({k: v for k, v in config.items() if v is not None}))
            
            # Start concurrent processing
            input_task = asyncio.create_task(
                self._process_live_input(ws, text_source)
            )
            
            # Yield audio as it becomes available
            async for audio_chunk in self._collect_realtime_audio(ws):
                yield audio_chunk
                
        finally:
            if not input_task.done():
                input_task.cancel()
            await ws.send_str(json.dumps({"type": "end_live_input_synthesis"}))
            
    async def _process_live_input(
        self, 
        ws: aiohttp.ClientWebSocketResponse, 
        text_source: AsyncIterator[str]
    ) -> None:
        """Process live text input and send for immediate synthesis."""
        text_buffer = ""
        chunk_id = 0
        
        async for text_chunk in text_source:
            text_buffer += text_chunk
            self._logger.debug(f"Received input: '{text_chunk}', buffer: '{text_buffer}'")
            
            # Check for synthesis opportunity
            synthesis_pos = await self._find_synthesis_boundary(text_buffer)
            
            if synthesis_pos > 0:
                synthesis_text = text_buffer[:synthesis_pos].strip()
                text_buffer = text_buffer[synthesis_pos:]
                
                if synthesis_text:
                    message = {
                        "type": "live_input_chunk",
                        "chunk_id": chunk_id,
                        "text": synthesis_text,
                        "timestamp": time.time(),
                    }
                    await ws.send_str(json.dumps(message))
                    chunk_id += 1
                    
                    self._logger.info(f"Live synthesis: '{synthesis_text}'")
                    
        # Process final buffer
        if text_buffer.strip():
            message = {
                "type": "live_input_chunk",
                "chunk_id": chunk_id,
                "text": text_buffer.strip(),
                "timestamp": time.time(),
                "final": True,
            }
            await ws.send_str(json.dumps(message))
            
    async def stream_with_live_monitoring(
        self,
        file_path: Union[str, Path],
        *,
        voice: Optional[str] = None,
        output_format: str = "wav",
        monitor_interval: float = 0.1,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream with real-time monitoring and metrics.
        
        Yields dictionaries containing:
        - audio_chunk: The audio bytes
        - metrics: Real-time performance metrics
        - status: Current processing status
        """
        start_time = time.time()
        total_chars_processed = 0
        total_audio_bytes = 0
        chunk_count = 0
        
        async for audio_chunk in self.stream_live_from_file(
            file_path, 
            voice=voice, 
            output_format=output_format
        ):
            chunk_count += 1
            total_audio_bytes += len(audio_chunk)
            
            # Calculate real-time metrics
            elapsed_time = time.time() - start_time
            processing_rate = total_chars_processed / elapsed_time if elapsed_time > 0 else 0
            audio_rate = total_audio_bytes / elapsed_time if elapsed_time > 0 else 0
            
            yield {
                "audio_chunk": audio_chunk,
                "metrics": {
                    "chunk_id": chunk_count,
                    "chunk_size_bytes": len(audio_chunk),
                    "total_audio_bytes": total_audio_bytes,
                    "elapsed_time": elapsed_time,
                    "chars_per_second": processing_rate,
                    "audio_bytes_per_second": audio_rate,
                    "estimated_audio_duration": total_audio_bytes / 44100 / 2,  # Rough estimate
                },
                "status": {
                    "processing": True,
                    "real_time_ratio": processing_rate / 150 if processing_rate > 0 else 0,  # Assuming 150 chars/sec reading
                    "buffer_health": "good",  # Could be calculated based on actual buffer status
                }
            }
