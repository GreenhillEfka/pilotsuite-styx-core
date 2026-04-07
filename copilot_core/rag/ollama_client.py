"""P2-001: Ollama Integration — Local LLM, Model Management, Fallback."""
from __future__ import annotations

import logging
import asyncio
import aiohttp
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import time

logger = logging.getLogger(__name__)


class ModelCapability(Enum):
    """Model capabilities."""
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    VISION = "vision"


@dataclass
class ModelInfo:
    """Information about an Ollama model."""
    name: str
    size_gb: float
    capabilities: List[ModelCapability]
    family: str
    format: str
    parameter_size: str
    quantization: Optional[str] = None


@dataclass
class OllamaConfig:
    """Configuration for Ollama client."""
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 120.0
    max_retries: int = 3
    fallback_enabled: bool = True
    fallback_models: List[str] = field(default_factory=lambda: ["llama3.2", "gemma2"])


@dataclass
class GenerationRequest:
    """Request for text generation."""
    model: str
    prompt: str
    system: Optional[str] = None
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    num_predict: int = 512
    stream: bool = False


@dataclass
class GenerationResponse:
    """Response from text generation."""
    model: str
    response: str
    done: bool
    total_duration_ms: float
    load_duration_ms: float
    prompt_eval_count: int
    eval_count: int
    eval_duration_ms: float


class OllamaClient:
    """Async Ollama client with fallback and model management."""

    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._available_models: List[ModelInfo] = []
        self._current_model: Optional[str] = None
        self._fallback_chain: List[str] = []

    async def connect(self):
        """Initialize HTTP session."""
        if not self._session:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds))
        await self._refresh_models()

    async def disconnect(self):
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def _refresh_models(self):
        """Fetch available models from Ollama."""
        try:
            assert self._session is not None
            async with self._session.get(f"{self.config.base_url}/api/tags") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._available_models = []
                    for model in data.get("models", []):
                        self._available_models.append(ModelInfo(
                            name=model.get("name", "unknown"),
                            size_gb=model.get("size", 0) / (1024**3),
                            capabilities=[ModelCapability.CHAT],  # Simplified
                            family=model.get("details", {}).get("family", "unknown"),
                            format=model.get("details", {}).get("format", "unknown"),
                            parameter_size=model.get("details", {}).get("parameter_size", "unknown"),
                            quantization=model.get("details", {}).get("quantization_level"),
                        ))
                    logger.info(f"Found {len(self._available_models)} Ollama models")
        except Exception as e:
            logger.warning(f"Failed to refresh models: {e}")

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> Optional[GenerationResponse]:
        """Generate text with automatic fallback."""
        await self.connect()
        
        model = model or self._current_model or self._available_models[0].name if self._available_models else "llama3.2"
        
        request = GenerationRequest(
            model=model,
            prompt=prompt,
            system=system,
            temperature=temperature,
            num_predict=max_tokens,
        )
        
        return await self._generate_with_retry(request)

    async def _generate_with_retry(self, request: GenerationRequest) -> Optional[GenerationResponse]:
        """Generate with retry and fallback."""
        models_to_try = [request.model] + self.config.fallback_models
        
        for attempt, model in enumerate(models_to_try):
            try:
                assert self._session is not None
                start = time.time()
                
                async with self._session.post(
                    f"{self.config.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": request.prompt,
                        "system": request.system,
                        "options": {
                            "temperature": request.temperature,
                            "top_p": request.top_p,
                            "top_k": request.top_k,
                            "num_predict": request.num_predict,
                        },
                        "stream": False,
                    }
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        duration_ms = (time.time() - start) * 1000
                        
                        return GenerationResponse(
                            model=model,
                            response=data.get("response", ""),
                            done=data.get("done", True),
                            total_duration_ms=duration_ms,
                            load_duration_ms=0,
                            prompt_eval_count=data.get("prompt_eval_count", 0),
                            eval_count=data.get("eval_count", 0),
                            eval_duration_ms=data.get("eval_duration", 0),
                        )
                    else:
                        logger.warning(f"Model {model} failed with status {resp.status}")
                        
            except Exception as e:
                logger.warning(f"Model {model} failed: {e}")
                if attempt < len(models_to_try) - 1:
                    logger.info(f"Falling back to next model...")
                else:
                    logger.error("All models failed")
                    return None
        
        return None

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Optional[str]:
        """Chat completion with message history."""
        await self.connect()
        
        model = model or self._current_model or "llama3.2"
        
        try:
            assert self._session is not None
            async with self._session.post(
                f"{self.config.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "options": {"temperature": temperature},
                    "stream": False,
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Chat failed: {e}")
        
        return None

    def get_available_models(self) -> List[ModelInfo]:
        """Get list of available models."""
        return self._available_models.copy()

    def set_current_model(self, model: str):
        """Set default model for generation."""
        self._current_model = model
        logger.info(f"Set current model: {model}")


# Global default client
default_ollama: Optional[OllamaClient] = None


def init_ollama(config: Optional[OllamaConfig] = None) -> OllamaClient:
    """Initialize global Ollama client."""
    global default_ollama
    default_ollama = OllamaClient(config)
    return default_ollama


async def generate_text(prompt: str, **kwargs) -> Optional[str]:
    """Convenience function for text generation."""
    if default_ollama:
        response = await default_ollama.generate(prompt, **kwargs)
        return response.response if response else None
    return None


async def chat_completion(messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
    """Convenience function for chat completion."""
    if default_ollama:
        return await default_ollama.chat(messages, **kwargs)
    return None
