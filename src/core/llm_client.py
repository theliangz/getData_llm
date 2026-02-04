#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
LLM client for text embedding and chat completion.
"""

from typing import List, Optional
import numpy as np
from openai import OpenAI

from config import get_settings
from utils import get_logger, LLMError

logger = get_logger(__name__)


class LLMClient:
    """LLM client wrapper."""
    
    def __init__(self, config=None):
        """Initialize LLM client."""
        settings = get_settings()
        self.config = config or settings.llm
        
        if not self.config.api_key:
            raise ValueError("LLM_API_KEY is required")
        
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client."""
        try:
            if self.config.api_base:
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.api_base
                )
            else:
                self._client = OpenAI(api_key=self.config.api_key)
            logger.info("LLM client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise LLMError(f"Failed to initialize LLM client: {e}") from e
    
    def embed_texts(self, texts: List[str], model: Optional[str] = None) -> np.ndarray:
        """
        Generate embeddings for texts.
        
        Args:
            texts: List of texts to embed
            model: Optional model name override
            
        Returns:
            numpy array of embeddings
        """
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        
        try:
            model = model or self.config.embedding_model
            logger.debug(f"Generating embeddings for {len(texts)} texts using model {model}")
            
            resp = self._client.embeddings.create(
                model=model,
                input=texts
            )
            
            vecs = [np.array(e.embedding, dtype=np.float32) for e in resp.data]
            result = np.vstack(vecs)
            logger.debug(f"Generated embeddings with shape {result.shape}")
            return result
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise LLMError(f"Failed to generate embeddings: {e}") from e
    
    def chat(self, system_prompt: str, user_prompt: str, model: Optional[str] = None, 
             temperature: Optional[float] = None) -> str:
        """
        Generate chat completion.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            model: Optional model name override
            temperature: Optional temperature override
            
        Returns:
            Generated text response
        """
        try:
            model = model or self.config.chat_model
            temperature = temperature if temperature is not None else self.config.temperature
            
            logger.debug(f"Generating chat completion using model {model}")
            
            resp = self._client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_prompt.strip()},
                ],
            )
            
            content = resp.choices[0].message.content or ""
            content = content.strip()
            
            # Clean up code blocks if present
            if content.startswith("```"):
                content = content.strip("`")
                lines = content.splitlines()
                if lines and lines[0].strip().lower() in {"sql", ""}:


                    lines = lines[1:]
                content = "\n".join(lines).strip()
            
            logger.debug(f"Generated response with length {len(content)}")
            return content
        except Exception as e:
            logger.error(f"Failed to generate chat completion: {e}")
            raise LLMError(f"Failed to generate chat completion: {e}") from e

