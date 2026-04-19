"""
FAISS Vector Index Manager for Insurance Product Recommendations

This module provides FAISS-based vector indexing for insurance products,
enabling efficient similarity search for RAG (Retrieval Augmented Generation).

Key Features:
- IndexFlatIP with dimension 768 for inner product similarity
- Product ID to vector ID mapping for bidirectional lookup
- Persistence (save/load) to disk
- Thread-safe operations
"""
import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import threading
import numpy as np

try:
    import faiss
except ImportError:
    raise ImportError(
        "FAISS is not installed. Please install it with: pip install faiss-cpu"
    )

from config import get_settings

logger = logging.getLogger(__name__)


class FAISSIndexError(Exception):
    """Base exception for FAISS index operations"""
    pass


class ProductNotFoundError(FAISSIndexError):
    """Raised when a product ID is not found in the index"""
    pass


class FAISSIndexManager:
    """
    FAISS Vector Index Manager for Insurance Products
    
    Uses IndexFlatIP (inner product) for similarity search with dimension 768.
    Maintains bidirectional mapping between product_id and vector_id.
    
    Attributes:
        dimension: Vector dimension (default: 768)
        index: FAISS index instance
        product_to_vector: Mapping from product_id to vector_id
        vector_to_product: Mapping from vector_id to product_id
        index_path: Path for index persistence
    """
    
    def __init__(
        self,
        dimension: int = 768,
        index_path: Optional[str] = None,
        auto_load: bool = True
    ):
        """
        Initialize FAISS Index Manager
        
        Args:
            dimension: Vector dimension (default: 768 for standard embeddings)
            index_path: Path for index persistence (default: from config)
            auto_load: Whether to automatically load existing index on init
        """
        settings = get_settings()
        self.dimension = dimension
        self.index_path = index_path or settings.FAISS_INDEX_PATH
        
        # Initialize FAISS index (IndexFlatIP for inner product similarity)
        self.index: Optional[faiss.IndexFlatIP] = None
        
        # Bidirectional mappings
        self.product_to_vector: Dict[str, int] = {}  # product_id -> vector_id
        self.vector_to_product: Dict[int, str] = {}  # vector_id -> product_id
        
        # Thread lock for concurrent access
        self._lock = threading.RLock()
        
        # Track if index is trained (IndexFlatIP doesn't need training, but keep for consistency)
        self._is_trained = False
        
        # Initialize index
        self._initialize_index()
        
        # Auto-load if path exists
        if auto_load and self._index_file_exists():
            self.load()
    
    def _initialize_index(self) -> None:
        """Initialize a new FAISS IndexFlatIP index"""
        with self._lock:
            self.index = faiss.IndexFlatIP(self.dimension)
            self._is_trained = True  # IndexFlatIP doesn't need training
            logger.info(f"Initialized FAISS IndexFlatIP with dimension {self.dimension}")
    
    def _index_file_exists(self) -> bool:
        """Check if index file exists on disk"""
        index_file = self._get_index_file_path()
        mapping_file = self._get_mapping_file_path()
        return index_file.exists() and mapping_file.exists()
    
    def _get_index_file_path(self) -> Path:
        """Get the full path for the index file"""
        return Path(self.index_path) / "index.faiss"
    
    def _get_mapping_file_path(self) -> Path:
        """Get the full path for the mapping file"""
        return Path(self.index_path) / "mappings.json"
    
    def _ensure_directory_exists(self) -> None:
        """Ensure the index directory exists"""
        Path(self.index_path).mkdir(parents=True, exist_ok=True)
    
    def add_product_vector(
        self,
        product_id: str,
        embedding: np.ndarray,
        allow_update: bool = False
    ) -> int:
        """
        Add a product vector to the index
        
        Args:
            product_id: Unique product identifier
            embedding: Product embedding vector (shape: [dimension] or [1, dimension])
            allow_update: Whether to allow updating existing product vector
            
        Returns:
            vector_id: The assigned vector ID in the index
            
        Raises:
            FAISSIndexError: If embedding shape is invalid
            ProductNotFoundError: If product already exists and allow_update is False
        """
        with self._lock:
            # Check if product already exists
            if product_id in self.product_to_vector:
                if not allow_update:
                    raise FAISSIndexError(
                        f"Product {product_id} already exists in index. "
                        "Use allow_update=True to update."
                    )
                # Remove old vector (we'll add new one)
                # Note: FAISS doesn't support removal, so we track it separately
                old_vector_id = self.product_to_vector[product_id]
                logger.warning(
                    f"Product {product_id} already exists with vector_id {old_vector_id}. "
                    "Adding new vector (old vector will remain in index but unmapped)."
                )
            
            # Validate embedding shape
            if embedding.ndim == 1:
                embedding = embedding.reshape(1, -1)
            elif embedding.ndim != 2 or embedding.shape[0] != 1:
                raise FAISSIndexError(
                    f"Invalid embedding shape: {embedding.shape}. "
                    "Expected shape: [dimension] or [1, dimension]"
                )
            
            if embedding.shape[1] != self.dimension:
                raise FAISSIndexError(
                    f"Embedding dimension mismatch: got {embedding.shape[1]}, "
                    f"expected {self.dimension}"
                )
            
            # Ensure float32 type for FAISS
            embedding = embedding.astype(np.float32)
            
            # Add to index
            vector_id = self.index.ntotal
            self.index.add(embedding)
            
            # Update mappings
            self.product_to_vector[product_id] = vector_id
            self.vector_to_product[vector_id] = product_id
            
            logger.debug(f"Added product {product_id} with vector_id {vector_id}")
            
            return vector_id
    
    def add_product_vectors(
        self,
        product_ids: List[str],
        embeddings: np.ndarray,
        allow_update: bool = False
    ) -> List[int]:
        """
        Add multiple product vectors to the index
        
        Args:
            product_ids: List of unique product identifiers
            embeddings: Product embedding matrix (shape: [n, dimension])
            allow_update: Whether to allow updating existing product vectors
            
        Returns:
            List of assigned vector IDs
        """
        with self._lock:
            # Validate shapes
            if embeddings.ndim != 2:
                raise FAISSIndexError(
                    f"Invalid embeddings shape: {embeddings.shape}. "
                    "Expected shape: [n, dimension]"
                )
            
            if embeddings.shape[0] != len(product_ids):
                raise FAISSIndexError(
                    f"Number of product_ids ({len(product_ids)}) doesn't match "
                    f"number of embeddings ({embeddings.shape[0]})"
                )
            
            if embeddings.shape[1] != self.dimension:
                raise FAISSIndexError(
                    f"Embedding dimension mismatch: got {embeddings.shape[1]}, "
                    f"expected {self.dimension}"
                )
            
            # Ensure float32 type
            embeddings = embeddings.astype(np.float32)
            
            # Check for existing products
            existing_products = [
                pid for pid in product_ids if pid in self.product_to_vector
            ]
            if existing_products and not allow_update:
                raise FAISSIndexError(
                    f"Products already exist in index: {existing_products}. "
                    "Use allow_update=True to update."
                )
            
            # Add to index
            start_id = self.index.ntotal
            self.index.add(embeddings)
            end_id = self.index.ntotal
            
            # Update mappings
            vector_ids = []
            for i, product_id in enumerate(product_ids):
                vector_id = start_id + i
                vector_ids.append(vector_id)
                self.product_to_vector[product_id] = vector_id
                self.vector_to_product[vector_id] = product_id
            
            logger.info(f"Added {len(product_ids)} products to index")
            
            return vector_ids
    
    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Search for similar products using vector similarity
        
        Args:
            query_embedding: Query embedding vector (shape: [dimension] or [1, dimension])
            k: Number of results to return
            
        Returns:
            Tuple of (distances, product_ids)
            
        Raises:
            FAISSIndexError: If index is empty or query shape is invalid
        """
        with self._lock:
            if self.index.ntotal == 0:
                raise FAISSIndexError("Index is empty. Add products before searching.")
            
            # Validate and reshape query
            if query_embedding.ndim == 1:
                query_embedding = query_embedding.reshape(1, -1)
            elif query_embedding.ndim != 2 or query_embedding.shape[0] != 1:
                raise FAISSIndexError(
                    f"Invalid query shape: {query_embedding.shape}. "
                    "Expected shape: [dimension] or [1, dimension]"
                )
            
            if query_embedding.shape[1] != self.dimension:
                raise FAISSIndexError(
                    f"Query dimension mismatch: got {query_embedding.shape[1]}, "
                    f"expected {self.dimension}"
                )
            
            # Ensure float32 type
            query_embedding = query_embedding.astype(np.float32)
            
            # Adjust k if it's larger than index size
            k = min(k, self.index.ntotal)
            
            # Search
            distances, indices = self.index.search(query_embedding, k)
            
            # Convert indices to product IDs
            product_ids = []
            for idx in indices[0]:
                if idx in self.vector_to_product:
                    product_ids.append(self.vector_to_product[idx])
                else:
                    # This shouldn't happen, but handle gracefully
                    logger.warning(f"Vector ID {idx} not found in mapping")
                    product_ids.append("")
            
            return distances[0], product_ids
    
    def search_with_scores(
        self,
        query_embedding: np.ndarray,
        k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Search for similar products and return (product_id, score) pairs
        
        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            
        Returns:
            List of (product_id, similarity_score) tuples, sorted by score descending
        """
        distances, product_ids = self.search(query_embedding, k)
        
        results = [
            (pid, float(score))
            for pid, score in zip(product_ids, distances)
            if pid  # Filter out empty product IDs
        ]
        
        return results
    
    def get_product_vector_id(self, product_id: str) -> Optional[int]:
        """
        Get the vector ID for a product
        
        Args:
            product_id: Product identifier
            
        Returns:
            Vector ID if found, None otherwise
        """
        return self.product_to_vector.get(product_id)
    
    def get_product_id(self, vector_id: int) -> Optional[str]:
        """
        Get the product ID for a vector ID
        
        Args:
            vector_id: Vector identifier in the index
            
        Returns:
            Product ID if found, None otherwise
        """
        return self.vector_to_product.get(vector_id)
    
    def has_product(self, product_id: str) -> bool:
        """Check if a product exists in the index"""
        return product_id in self.product_to_vector
    
    def get_total_products(self) -> int:
        """Get the total number of products in the index"""
        return len(self.product_to_vector)
    
    def get_index_size(self) -> int:
        """Get the total number of vectors in the FAISS index"""
        return self.index.ntotal if self.index else 0
    
    def save(self, path: Optional[str] = None) -> None:
        """
        Save the index and mappings to disk
        
        Args:
            path: Optional custom path (uses self.index_path if not provided)
        """
        with self._lock:
            save_path = path or self.index_path
            self._ensure_directory_exists()
            
            # Save FAISS index
            index_file = Path(save_path) / "index.faiss"
            faiss.write_index(self.index, str(index_file))
            
            # Save mappings
            mapping_file = Path(save_path) / "mappings.json"
            mappings = {
                "dimension": self.dimension,
                "product_to_vector": self.product_to_vector,
                "vector_to_product": {str(k): v for k, v in self.vector_to_product.items()}
            }
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(mappings, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved FAISS index with {self.index.ntotal} vectors to {save_path}")
    
    def load(self, path: Optional[str] = None) -> bool:
        """
        Load the index and mappings from disk
        
        Args:
            path: Optional custom path (uses self.index_path if not provided)
            
        Returns:
            True if loaded successfully, False if no index found
        """
        with self._lock:
            load_path = path or self.index_path
            index_file = Path(load_path) / "index.faiss"
            mapping_file = Path(load_path) / "mappings.json"
            
            if not index_file.exists() or not mapping_file.exists():
                logger.warning(f"Index files not found at {load_path}")
                return False
            
            try:
                # Load FAISS index
                self.index = faiss.read_index(str(index_file))
                
                # Load mappings
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    mappings = json.load(f)
                
                # Validate dimension
                loaded_dimension = mappings.get("dimension", self.dimension)
                if loaded_dimension != self.dimension:
                    logger.warning(
                        f"Loaded index has dimension {loaded_dimension}, "
                        f"but expected {self.dimension}. Updating dimension."
                    )
                    self.dimension = loaded_dimension
                
                # Restore mappings
                self.product_to_vector = mappings.get("product_to_vector", {})
                self.vector_to_product = {
                    int(k): v for k, v in mappings.get("vector_to_product", {}).items()
                }
                
                self._is_trained = True
                
                logger.info(
                    f"Loaded FAISS index with {self.index.ntotal} vectors "
                    f"and {len(self.product_to_vector)} product mappings from {load_path}"
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to load FAISS index: {e}")
                # Re-initialize empty index
                self._initialize_index()
                return False
    
    def clear(self) -> None:
        """Clear the index and all mappings"""
        with self._lock:
            self._initialize_index()
            self.product_to_vector.clear()
            self.vector_to_product.clear()
            logger.info("Cleared FAISS index and mappings")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the index
        
        Returns:
            Dictionary with index statistics
        """
        with self._lock:
            return {
                "dimension": self.dimension,
                "total_vectors": self.index.ntotal if self.index else 0,
                "total_products": len(self.product_to_vector),
                "index_type": "IndexFlatIP",
                "is_trained": self._is_trained,
                "index_path": self.index_path
            }
    
    def __len__(self) -> int:
        """Return the number of products in the index"""
        return self.get_total_products()
    
    def __contains__(self, product_id: str) -> bool:
        """Check if a product exists in the index"""
        return self.has_product(product_id)
    
    def __repr__(self) -> str:
        return (
            f"FAISSIndexManager("
            f"dimension={self.dimension}, "
            f"products={self.get_total_products()}, "
            f"vectors={self.get_index_size()})"
        )


# Global instance (lazy initialization)
_faiss_index_manager: Optional[FAISSIndexManager] = None
_faiss_lock = threading.Lock()


def get_faiss_index_manager(
    dimension: int = 768,
    index_path: Optional[str] = None,
    auto_load: bool = True,
    force_new: bool = False
) -> FAISSIndexManager:
    """
    Get the global FAISS index manager instance (singleton pattern)
    
    Args:
        dimension: Vector dimension
        index_path: Path for index persistence
        auto_load: Whether to auto-load existing index
        force_new: Force create a new instance (for testing)
        
    Returns:
        FAISSIndexManager instance
    """
    global _faiss_index_manager
    
    with _faiss_lock:
        if _faiss_index_manager is None or force_new:
            _faiss_index_manager = FAISSIndexManager(
                dimension=dimension,
                index_path=index_path,
                auto_load=auto_load
            )
        return _faiss_index_manager


def reset_faiss_index_manager() -> None:
    """Reset the global FAISS index manager (for testing)"""
    global _faiss_index_manager
    
    with _faiss_lock:
        if _faiss_index_manager is not None:
            _faiss_index_manager.clear()
        _faiss_index_manager = None
