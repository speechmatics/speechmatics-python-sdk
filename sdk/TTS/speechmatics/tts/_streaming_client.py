"""
Streaming TTS client for real-time text-to-speech synthesis.

This module provides streaming text-to-speech capabilities with chunked processing,
real-time audio delivery, and WebSocket/SSE support for incremental synthesis.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import AsyncGenerator, Optional, Union, List, Dict, Any
from pathlib import Path

import aiohttp
import aiofiles

from ._auth import AuthBase, StaticKeyAuth
from ._exceptions import AuthenticationError, TransportError
from ._logging import get_logger
from ._models import ConnectionConfig
from ._transport import Transport


class StreamingTTSClient:
    """
    Streaming Text-to-Speech client with real-time audio generation.
    
    This client provides streaming TTS capabilities including:
    - Chunked text processing for large documents
    - Real-time audio streaming via WebSocket/SSE
    - Incremental audio delivery as chunks are synthesized
    - Support for both file and text input streaming
    
    Args:
        auth: Authentication instance
        api_key: Speechmatics API key (if auth not provided)
        url: TTS API endpoint URL
        conn_config: Connection configuration
        
    Examples:
        Basic streaming:
            >>> async with StreamingTTSClient(api_key="key") as client:
            ...     async for audio_chunk in client.stream_speech("Long text..."):
            ...         # Play audio_chunk in real-time
            ...         await play_audio(audio_chunk)
                        
        File streaming:
            >>> async for audio_chunk in client.stream_from_file("book.txt"):
            ...     await save_audio_chunk(audio_chunk)
    """
    
    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
        chunk_size: int = 500,
        overlap_size: int = 50,
    ) -> None:
        """Initialize streaming TTS client."""
        self._auth = auth or StaticKeyAuth(api_key)
        self._url = url or "wss://tts.api.speechmatics.com/v1"  # WebSocket endpoint
        self._conn_config = conn_config or ConnectionConfig()
        self._chunk_size = chunk_size  # Characters per chunk
        self._overlap_size = overlap_size  # Overlap to prevent word cuts
        
        self._logger = get_logger(__name__)
        self._session: Optional[aiohttp.ClientSession] = None
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        
    async def __aenter__(self) -> StreamingTTSClient:
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
            
    def _chunk_text(self, text: str) -> List[str]:
        """
        Break text into chunks with smart sentence/word boundaries.
        
        Args:
            text: Input text to chunk
            
        Returns:
            List of text chunks with overlap for continuity
        """
        if len(text) <= self._chunk_size:
            return [text]
            
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self._chunk_size
            
            if end >= len(text):
                # Last chunk
                chunks.append(text[start:])
                break
                
            # Find good break point (sentence end, then word boundary)
            chunk_text = text[start:end + self._overlap_size]
            
            # Look for sentence endings
            sentence_breaks = [m.end() for m in re.finditer(r'[.!?]\s+', chunk_text)]
            if sentence_breaks:
                break_point = sentence_breaks[-1]
            else:
                # Fall back to word boundary
                word_breaks = [m.start() for m in re.finditer(r'\s+', chunk_text)]
                if word_breaks:
                    break_point = word_breaks[-1]
                else:
                    break_point = self._chunk_size
                    
            actual_end = start + break_point
            chunks.append(text[start:actual_end])
            start = actual_end - self._overlap_size  # Overlap for continuity
            
        return chunks
        
    async def _connect_websocket(self) -> aiohttp.ClientWebSocketResponse:
        """Establish WebSocket connection for streaming."""
        await self._ensure_session()
        
        headers = await self._auth.get_headers()
        
        self._websocket = await self._session.ws_connect(
            f"{self._url}/stream-synthesize",
            headers=headers,
            heartbeat=30
        )
        
        return self._websocket
        
    async def stream_speech(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        output_format: str = "wav",
        sample_rate: Optional[int] = None,
        speed: Optional[float] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream text-to-speech with chunked processing.
        
        Args:
            text: Text to convert to speech
            voice: Voice ID for synthesis
            output_format: Audio format ("wav", "mp3", "ogg")
            sample_rate: Audio sample rate in Hz
            speed: Speech speed multiplier
            
        Yields:
            Audio chunks as bytes as they're generated
            
        Examples:
            >>> async for audio_chunk in client.stream_speech("Hello world"):
            ...     await play_audio_chunk(audio_chunk)
        """
        chunks = self._chunk_text(text)
        self._logger.info(f"Processing {len(chunks)} text chunks")
        
        ws = await self._connect_websocket()
        
        try:
            # Send synthesis configuration
            config = {
                "type": "start_synthesis",
                "voice": voice,
                "output_format": output_format,
                "sample_rate": sample_rate,
                "speed": speed,
            }
            await ws.send_str(json.dumps({k: v for k, v in config.items() if v is not None}))
            
            # Process chunks concurrently for better performance
            chunk_tasks = []
            for i, chunk in enumerate(chunks):
                task = asyncio.create_task(self._process_chunk(ws, chunk, i))
                chunk_tasks.append(task)
                
            # Yield audio chunks as they become available
            async for audio_chunk in self._collect_audio_chunks(ws, len(chunks)):
                yield audio_chunk
                
        finally:
            # Send end signal
            await ws.send_str(json.dumps({"type": "end_synthesis"}))
            
    async def _process_chunk(self, ws: aiohttp.ClientWebSocketResponse, chunk: str, chunk_id: int) -> None:
        """Process a single text chunk."""
        message = {
            "type": "text_chunk",
            "chunk_id": chunk_id,
            "text": chunk,
        }
        await ws.send_str(json.dumps(message))
        
    async def _collect_audio_chunks(
        self, 
        ws: aiohttp.ClientWebSocketResponse, 
        expected_chunks: int
    ) -> AsyncGenerator[bytes, None]:
        """Collect and yield audio chunks from WebSocket."""
        received_chunks = 0
        
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                
                if data.get("type") == "audio_chunk":
                    # Decode base64 audio data
                    import base64
                    audio_data = base64.b64decode(data["audio"])
                    yield audio_data
                    
                elif data.get("type") == "chunk_complete":
                    received_chunks += 1
                    if received_chunks >= expected_chunks:
                        break
                        
                elif data.get("type") == "error":
                    raise TransportError(f"Synthesis error: {data.get('message')}")
                    
            elif msg.type == aiohttp.WSMsgType.ERROR:
                raise TransportError(f"WebSocket error: {ws.exception()}")
                
    async def stream_from_file(
        self,
        file_path: Union[str, Path],
        *,
        voice: Optional[str] = None,
        output_format: str = "wav",
        sample_rate: Optional[int] = None,
        speed: Optional[float] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS from a text file with real-time processing.
        
        Args:
            file_path: Path to text file
            voice: Voice ID for synthesis
            output_format: Audio format
            sample_rate: Audio sample rate
            speed: Speech speed multiplier
            
        Yields:
            Audio chunks as they're generated from file content
            
        Examples:
            >>> async for audio_chunk in client.stream_from_file("book.txt"):
            ...     await save_audio_chunk(audio_chunk)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # Read file content asynchronously
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            text_content = await f.read()
            
        # Stream the file content
        async for audio_chunk in self.stream_speech(
            text_content,
            voice=voice,
            output_format=output_format,
            sample_rate=sample_rate,
            speed=speed,
        ):
            yield audio_chunk
            
    async def stream_from_file_incremental(
        self,
        file_path: Union[str, Path],
        *,
        voice: Optional[str] = None,
        output_format: str = "wav",
        sample_rate: Optional[int] = None,
        speed: Optional[float] = None,
        read_chunk_size: int = 8192,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS from file with incremental reading for very large files.
        
        This method reads the file in chunks and processes them as they're read,
        providing true streaming for massive text files.
        
        Args:
            file_path: Path to text file
            read_chunk_size: Size of file read chunks in bytes
            
        Yields:
            Audio chunks as file is read and processed
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        ws = await self._connect_websocket()
        
        try:
            # Send synthesis configuration
            config = {
                "type": "start_synthesis",
                "voice": voice,
                "output_format": output_format,
                "sample_rate": sample_rate,
                "speed": speed,
            }
            await ws.send_str(json.dumps({k: v for k, v in config.items() if v is not None}))
            
            # Read and process file incrementally
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                buffer = ""
                chunk_id = 0
                
                while True:
                    # Read file chunk
                    file_chunk = await f.read(read_chunk_size)
                    if not file_chunk:
                        break
                        
                    buffer += file_chunk
                    
                    # Process complete sentences from buffer
                    while len(buffer) > self._chunk_size:
                        # Find sentence boundary
                        sentence_end = buffer.rfind('.', 0, self._chunk_size)
                        if sentence_end == -1:
                            sentence_end = buffer.rfind(' ', 0, self._chunk_size)
                        if sentence_end == -1:
                            sentence_end = self._chunk_size
                            
                        text_chunk = buffer[:sentence_end + 1]
                        buffer = buffer[sentence_end + 1:]
                        
                        # Send chunk for processing
                        await self._process_chunk(ws, text_chunk, chunk_id)
                        chunk_id += 1
                        
                        # Yield any available audio
                        try:
                            msg = await asyncio.wait_for(ws.receive(), timeout=0.1)
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                if data.get("type") == "audio_chunk":
                                    import base64
                                    audio_data = base64.b64decode(data["audio"])
                                    yield audio_data
                        except asyncio.TimeoutError:
                            pass  # No audio ready yet
                            
                # Process remaining buffer
                if buffer.strip():
                    await self._process_chunk(ws, buffer, chunk_id)
                    
            # Collect remaining audio chunks
            await ws.send_str(json.dumps({"type": "end_synthesis"}))
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "audio_chunk":
                        import base64
                        audio_data = base64.b64decode(data["audio"])
                        yield audio_data
                    elif data.get("type") == "synthesis_complete":
                        break
                        
        finally:
            if self._websocket:
                await self._websocket.close()
                self._websocket = None
