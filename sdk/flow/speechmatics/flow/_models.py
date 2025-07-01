from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from enum import Enum
from typing import Any
from typing import Optional


class AudioEncoding(str, Enum):
    """Supported audio encoding formats."""

    PCM_F32LE = "pcm_f32le"
    PCM_S16LE = "pcm_s16le"


class ClientMessageType(str, Enum):
    """Message types sent from client to server."""

    START_CONVERSATION = "StartConversation"
    ADD_AUDIO = "AddAudio"
    AUDIO_ENDED = "AudioEnded"
    AUDIO_RECEIVED = "AudioReceived"
    TOOL_RESULT = "ToolResult"
    ADD_INPUT = "AddInput"


class ServerMessageType(str, Enum):
    """Message types received from server."""

    CONVERSATION_STARTED = "ConversationStarted"
    CONVERSATION_ENDED = "ConversationEnded"
    CONVERSATION_ENDING = "ConversationEnding"
    ADD_TRANSCRIPT = "AddTranscript"
    ADD_PARTIAL_TRANSCRIPT = "AddPartialTranscript"
    RESPONSE_STARTED = "ResponseStarted"
    RESPONSE_COMPLETED = "ResponseCompleted"
    RESPONSE_INTERRUPTED = "ResponseInterrupted"
    ADD_AUDIO = "AddAudio"
    AUDIO_ADDED = "AudioAdded"
    TOOL_INVOKE = "ToolInvoke"
    PROMPT = "prompt"
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"
    DEBUG = "Debug"


@dataclass
class AudioFormat:
    """
    Audio configuration for Flow conversations.

    Attributes:
        encoding: Audio encoding format
        sample_rate: Sample rate in Hz
        chunk_size: Audio chunk size in bytes
    """

    encoding: AudioEncoding = AudioEncoding.PCM_S16LE
    sample_rate: int = 16000
    chunk_size: int = 160

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "raw",
            "encoding": self.encoding.value,
            "sample_rate": self.sample_rate,
        }


@dataclass
class DebugMode:
    """
    Configuration for debug flags.

    Attributes:
        llm: Flag indicating whether to receive LLM debug messages
    """

    llm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"llm": self.llm}


@dataclass
class AddInput:
    """
    Message to be sent to the LLM.

    Attributes:
        input: Input text to be sent to the LLM
        immediate: Flag indicating whether the input is immediate
        interrupt_response: Flag indicating whether to interrupt current response
    """

    input: str
    immediate: bool = False
    interrupt_response: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": "AddInput",
            "input": self.input,
            "interrupt_response": self.interrupt_response,
            "immediate": self.immediate,
        }


@dataclass
class ConversationConfig:
    """
    Configuration for Flow conversations.

    Attributes:
        template_id: Conversation template identifier or template name
        template_variables: Variables to substitute in template

    Example:
        >>> config = ConversationConfig(
        ...     template_id="default",
        ...     template_variables = {
        ...        "persona": "You're a witty pet expert who loves animals and knows your stuff.",
        ...        "style": "Friendly, sharp, and a little playful — but always helpful.",
        ...        "context": "You help pet parents find great products and advice for all kinds of quirky companions."
        ...    }
        ... )
    """

    template_id: str = "default"
    template_variables: Optional[dict[str, str]] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"template_id": self.template_id}
        if self.template_variables:
            result["template_variables"] = self.template_variables
        return result


@dataclass
class ConnectionConfig:
    """
    Configuration for WebSocket connection parameters.

    This class defines WebSocket-specific settings like ping intervals,
    message sizes, and connection timeouts.

    Attributes:
        open_timeout: Timeout for establishing WebSocket connection.
        ping_interval: Interval for WebSocket ping frames.
        ping_timeout: Timeout waiting for pong response.
        close_timeout: Timeout for closing WebSocket connection.
        max_size: Maximum message size in bytes.
        max_queue: Maximum number of messages in receive queue.
        read_limit: Maximum number of bytes to read from WebSocket.
        write_limit: Maximum number of bytes to write to WebSocket.

    Returns:
        Websocket connection configuration as a dict while excluding None values.
    """

    open_timeout: Optional[float] = None
    ping_interval: Optional[float] = None
    ping_timeout: Optional[float] = 60
    close_timeout: Optional[float] = None
    max_size: Optional[int] = None
    max_queue: Optional[int] = None
    read_limit: Optional[int] = None
    write_limit: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})


@dataclass
class SessionInfo:
    """
    Information about the current conversation session.

    Attributes:
        request_id: Unique request identifier
        conversation_id: Server-assigned conversation ID
        client_seq_no: Client sequence number
        server_seq_no: Server sequence number
        is_running: Whether session is active
    """

    request_id: str
    conversation_id: Optional[str] = None
    client_seq_no: int = 0
    server_seq_no: int = 0
    is_running: bool = False


@dataclass
class FunctionParamProperty:
    """Tool function property definition."""

    type: str
    description: str


@dataclass
class FunctionParam:
    """Tool function parameters definition."""

    type: str
    properties: dict[str, FunctionParamProperty]
    required: Optional[list[str]] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.type,
            "properties": {k: {"type": v.type, "description": v.description} for k, v in self.properties.items()},
        }
        if self.required:
            result["required"] = self.required
        return result


@dataclass
class FunctionDefinition:
    """Tool function definition."""

    name: str
    description: Optional[str] = None
    parameters: Optional[FunctionParam] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name}
        if self.description:
            result["description"] = self.description
        if self.parameters:
            result["parameters"] = self.parameters.to_dict()
        return result


@dataclass
class ToolFunctionParam:
    """Tool definition for LLM function calling."""

    function: FunctionDefinition
    type: str = "function"
    """Currently, only 'function' is supported."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "function": self.function.to_dict(),
        }
