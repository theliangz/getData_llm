#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Vector store client for Milvus.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from pymilvus import connections, Collection, utility

from config import get_settings
from utils import get_logger, VectorDBError

logger = get_logger(__name__)


class VectorStore:
    """Vector store client for Milvus."""
    
    def __init__(self, config=None):
        """Initialize vector store client."""
        settings = get_settings()
        self.config = config or settings.milvus
        self._connected = False
    
    def connect(self) -> None:
        """Connect to Milvus."""
        if self._connected:
            return
        
        try:
            params = {
                "host": self.config.host,
                "port": self.config.port
            }
            if self.config.user and self.config.password:
                params["user"] = self.config.user
                params["password"] = self.config.password
            
            connections.connect(self.config.connection_alias, **params)
            self._connected = True
            logger.info(f"Connected to Milvus at {self.config.host}:{self.config.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise VectorDBError(f"Failed to connect to Milvus: {e}") from e
    
    def disconnect(self) -> None:
        """Disconnect from Milvus."""
        if self._connected:
            try:
                connections.disconnect(self.config.connection_alias)
                self._connected = False
                logger.info("Disconnected from Milvus")
            except Exception as e:
                logger.warning(f"Error disconnecting from Milvus: {e}")
    
    def get_collection(self, collection_name: str) -> Collection:
        """Get collection by name."""
        if not self._connected:
            self.connect()
        
        try:
            return Collection(collection_name)
        except Exception as e:
            logger.error(f"Failed to get collection {collection_name}: {e}")
            raise VectorDBError(f"Failed to get collection {collection_name}: {e}") from e
    
    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        top_k: int = 5,
        output_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search similar vectors in collection.
        
        Args:
            collection_name: Name of the collection
            query_vector: Query vector
            top_k: Number of results to return
            output_fields: Fields to return in results
            
        Returns:
            List of search results
        """
        if not self._connected:
            self.connect()
        
        try:
            collection = self.get_collection(collection_name)
            collection.load()
            
            search_params = {
                "metric_type": self.config.search_metric,
                "params": {"nprobe": self.config.search_nprobe}
            }
            
            output_fields = output_fields or ["text", "meta"]
            
            results = collection.search(
                data=[query_vector.tolist()],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                output_fields=output_fields,
            )
            
            hits = results[0]
            return [
                {
                    "text": hit.entity.get("text"),
                    "meta": hit.entity.get("meta"),
                    "score": hit.distance
                }
                for hit in hits
            ]
        except Exception as e:
            logger.error(f"Failed to search in collection {collection_name}: {e}")
            raise VectorDBError(f"Failed to search in collection {collection_name}: {e}") from e
    
    def ensure_collection(self, name: str, dim: int) -> Collection:
        """
        Ensure collection exists, create if not.
        
        Args:
            name: Collection name
            dim: Vector dimension
            
        Returns:
            Collection instance
        """
        if not self._connected:
            self.connect()
        
        try:
            if utility.has_collection(name):
                collection = Collection(name)
                logger.info(f"Collection {name} already exists")
                return collection
            
            from pymilvus import FieldSchema, CollectionSchema, DataType
            
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=60000),
                FieldSchema(name="meta", dtype=DataType.JSON),
            ]
            schema = CollectionSchema(fields, description=name)
            collection = Collection(name, schema)
            
            # Create index
            index_params = {
                "index_type": "IVF_FLAT",
                "metric_type": self.config.search_metric,
                "params": {"nlist": self.config.index_nlist}
            }
            collection.create_index("vector", index_params)
            
            logger.info(f"Created collection {name} with dimension {dim}")
            return collection
        except Exception as e:
            logger.error(f"Failed to ensure collection {name}: {e}")
            raise VectorDBError(f"Failed to ensure collection {name}: {e}") from e
    
    def upsert(
        self,
        collection: Collection,
        vectors: np.ndarray,
        texts: List[str],
        metas: List[Dict[str, Any]]
    ) -> None:
        """
        Upsert documents to collection.
        
        Args:
            collection: Collection instance
            vectors: Vector embeddings
            texts: Text contents
            metas: Metadata for each document
        """
        try:
            if len(vectors) != len(texts) or len(texts) != len(metas):
                raise ValueError("Vectors, texts, and metas must have the same length")
            
            insert_data = [
                # [None] * len(texts),  # auto_id
                vectors.tolist(),
                texts,
                metas,
            ]
            collection.insert(insert_data)
            collection.flush()
            logger.info(f"Upserted {len(texts)} documents to collection {collection.name}")
        except Exception as e:
            logger.error(f"Failed to upsert documents: {e}")
            raise VectorDBError(f"Failed to upsert documents: {e}") from e

