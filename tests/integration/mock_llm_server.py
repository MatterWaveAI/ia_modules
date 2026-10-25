"""
Mock LLM API Server for Testing

Mimics OpenAI/Anthropic API endpoints without making real API calls.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time
import os
import random

app = FastAPI()

# Configuration from environment
MOCK_DELAY_MS = int(os.getenv("MOCK_DELAY_MS", "100"))
MOCK_ERROR_RATE = float(os.getenv("MOCK_ERROR_RATE", "0.0"))


class Message(BaseModel):
    role: str
    content: Any  # Can be string or list for vision


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    max_tokens: Optional[int] = 1000
    temperature: Optional[float] = 1.0


class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]


class EmbeddingRequest(BaseModel):
    model: str
    input: str


class EmbeddingData(BaseModel):
    object: str = "embedding"
    embedding: List[float]
    index: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """Mock OpenAI chat completions endpoint."""
    # Simulate API delay
    time.sleep(MOCK_DELAY_MS / 1000)

    # Simulate random errors
    if random.random() < MOCK_ERROR_RATE:
        raise HTTPException(status_code=500, detail="Mock API error")

    # Extract last message
    last_message = request.messages[-1]
    content = last_message.content

    # Check if this is a vision request
    if isinstance(content, list):
        # Vision API request
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
        has_image = any(isinstance(item, dict) and item.get("type") == "image_url" for item in content)

        if has_image:
            response_text = "This is a mock image description. The image shows various elements as described in the prompt."
        else:
            response_text = f"Mock response to: {' '.join(text_parts)}"
    else:
        # Regular text request
        # Generate intelligent mock responses based on content
        content_lower = content.lower() if isinstance(content, str) else ""

        if "critique" in content_lower or "evaluate" in content_lower:
            response_text = (
                "Score: 8/10\n\n"
                "The response demonstrates good quality with clear explanations. "
                "Areas for improvement include adding more specific examples and "
                "ensuring all technical terms are defined. Overall, this meets "
                "the criteria for helpfulness and accuracy."
            )
        elif "revise" in content_lower or "improve" in content_lower:
            response_text = (
                "Here is an improved version incorporating the feedback: "
                "The content has been enhanced with additional clarity, "
                "specific examples have been added, and technical terminology "
                "is now properly defined for better understanding."
            )
        elif "summarize" in content_lower:
            response_text = (
                "Summary: The key points include important concepts and "
                "main ideas that have been consolidated into a concise overview."
            )
        else:
            response_text = f"Mock response to: {content[:100]}"

    # Build response
    response = ChatCompletionResponse(
        id=f"chatcmpl-{int(time.time())}",
        created=int(time.time()),
        model=request.model,
        choices=[
            Choice(
                index=0,
                message=Message(role="assistant", content=response_text),
                finish_reason="stop"
            )
        ]
    )

    return response.dict()


@app.post("/v1/embeddings")
async def create_embeddings(request: EmbeddingRequest):
    """Mock OpenAI embeddings endpoint."""
    # Simulate API delay
    time.sleep(MOCK_DELAY_MS / 1000)

    # Simulate random errors
    if random.random() < MOCK_ERROR_RATE:
        raise HTTPException(status_code=500, detail="Mock API error")

    # Generate fake embedding (1536 dimensions for text-embedding-ada-002)
    embedding_dim = 1536
    fake_embedding = [random.random() for _ in range(embedding_dim)]

    response = EmbeddingResponse(
        model=request.model,
        data=[
            EmbeddingData(
                embedding=fake_embedding,
                index=0
            )
        ]
    )

    return response.dict()


@app.post("/v1/audio/transcriptions")
async def transcribe_audio():
    """Mock Whisper transcription endpoint."""
    # Simulate API delay
    time.sleep(MOCK_DELAY_MS / 1000)

    return {"text": "This is a mock transcription of the audio content."}


@app.post("/v1/audio/speech")
async def text_to_speech():
    """Mock TTS endpoint."""
    # Simulate API delay
    time.sleep(MOCK_DELAY_MS / 1000)

    # Return mock audio bytes
    return b"MOCK_AUDIO_DATA"


# Anthropic-style endpoints
@app.post("/v1/messages")
async def anthropic_messages(request: Dict[str, Any]):
    """Mock Anthropic messages endpoint."""
    # Simulate API delay
    time.sleep(MOCK_DELAY_MS / 1000)

    # Simulate random errors
    if random.random() < MOCK_ERROR_RATE:
        raise HTTPException(status_code=500, detail="Mock API error")

    # Extract content
    messages = request.get("messages", [])
    last_message = messages[-1] if messages else {}
    content = last_message.get("content", [])

    # Check for images
    has_image = any(isinstance(item, dict) and item.get("type") == "image" for item in content)

    if has_image:
        response_text = "Mock Anthropic vision response: The image contains various visual elements."
    else:
        text_content = " ".join(
            item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"
        )
        response_text = f"Mock Anthropic response to: {text_content[:100]}"

    return {
        "id": f"msg_{int(time.time())}",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": response_text}],
        "model": request.get("model", "claude-3-5-sonnet-20241022"),
        "stop_reason": "end_turn"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
