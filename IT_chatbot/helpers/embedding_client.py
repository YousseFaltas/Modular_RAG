"""
Embedding Service Client
Module for communicating with the Embedding Service API
"""

import requests
import os
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class EmbeddingServiceClient:
    """Client for interacting with the Embedding Service API"""
    
    def __init__(self, base_url: str = None):
        """
        Initialize the embedding service client
        
        Args:
            base_url: Base URL of the embedding service.
                     Defaults to env var EMBEDDING_SERVICE_URL or http://localhost:8001
        """
        self.base_url = base_url or os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")
        self.timeout = 300  # 5 minutes timeout for embedding operations
        
    def health_check(self) -> bool:
        """
        Check if the embedding service is healthy
        
        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def embed_single(self, text: str) -> List[float]:
        """
        Embed a single text string
        
        Args:
            text: Text to embed
            
        Returns:
            List[float]: Embedding vector
            
        Raises:
            Exception: If embedding fails
        """
        try:
            response = requests.post(
                f"{self.base_url}/embed",
                json={"text": text},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            logger.error(f"Error embedding single text: {e}")
            raise
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts in batch
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List[List[float]]: List of embedding vectors
            
        Raises:
            Exception: If embedding fails
        """
        try:
            response = requests.post(
                f"{self.base_url}/embed-batch",
                json={"texts": texts},
                timeout=self.timeout
            )
            response.raise_for_status()
            embeddings = response.json()["embeddings"]
            return [item["embedding"] for item in embeddings]
        except Exception as e:
            logger.error(f"Error embedding batch: {e}")
            raise
    
    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Embed chunks data structure
        Adds 'vector' field to each chunk
        
        Args:
            chunks: List of chunk dictionaries with 'text' field
            
        Returns:
            List[Dict[str, Any]]: Chunks with added 'vector' field
            
        Raises:
            Exception: If embedding fails
        """
        try:
            response = requests.post(
                f"{self.base_url}/embed-chunks",
                json={"chunks": chunks},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()["chunks"]
        except Exception as e:
            logger.error(f"Error embedding chunks: {e}")
            raise
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded embedding model
        
        Returns:
            Dict[str, Any]: Model information including dimensions and device
            
        Raises:
            Exception: If request fails
        """
        try:
            response = requests.get(
                f"{self.base_url}/model-info",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            raise


# Singleton instance for convenience
_client = None

def get_embedding_client(base_url: str = None) -> EmbeddingServiceClient:
    """
    Get or create the embedding service client singleton
    
    Args:
        base_url: Optional base URL to override default
        
    Returns:
        EmbeddingServiceClient: Client instance
    """
    global _client
    if _client is None:
        _client = EmbeddingServiceClient(base_url)
    return _client
