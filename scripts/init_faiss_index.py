"""
Script to initialize FAISS index with insurance products

This script:
1. Loads insurance products from data/insurance_products.json
2. Generates embeddings for each product (using a mock embedding for now)
3. Adds products to the FAISS index
4. Saves the index to disk

Usage:
    uv run python scripts/init_faiss_index.py
"""
import json
import logging
from pathlib import Path

import numpy as np

from utils.faiss_index import get_faiss_index_manager, reset_faiss_index_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_insurance_products(file_path: str = "data/insurance_products.json") -> list:
    """Load insurance products from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("products", [])


def generate_product_embedding(product: dict, dimension: int = 768) -> np.ndarray:
    """
    Generate embedding for a product
    
    NOTE: This is a placeholder implementation that generates random embeddings.
    In production, you would use a real embedding model like:
    - sentence-transformers
    - OpenAI embeddings
    - Custom trained model
    
    For now, we use a deterministic hash-based approach to generate consistent
    embeddings for the same product.
    """
    # Use product_id as seed for reproducibility
    product_id = product.get("product_id", "unknown")
    seed = hash(product_id) % (2**31)
    np.random.seed(seed)
    
    # Generate random embedding
    embedding = np.random.randn(dimension).astype(np.float32)
    
    # Normalize to unit length (for inner product similarity)
    embedding = embedding / np.linalg.norm(embedding)
    
    return embedding


def main():
    """Initialize FAISS index with insurance products"""
    logger.info("Starting FAISS index initialization...")
    
    # Reset any existing global instance
    reset_faiss_index_manager()
    
    # Get index manager
    index_manager = get_faiss_index_manager(
        dimension=768,
        index_path="data/faiss_index",
        auto_load=False
    )
    
    # Load products
    products = load_insurance_products()
    logger.info(f"Loaded {len(products)} products from data/insurance_products.json")
    
    if not products:
        logger.warning("No products found. Exiting.")
        return
    
    # Generate embeddings
    logger.info("Generating embeddings for products...")
    embeddings = []
    product_ids = []
    
    for product in products:
        product_id = product.get("product_id")
        if not product_id:
            logger.warning(f"Product missing product_id: {product}")
            continue
        
        embedding = generate_product_embedding(product)
        embeddings.append(embedding)
        product_ids.append(product_id)
    
    # Convert to numpy array
    embeddings_array = np.array(embeddings, dtype=np.float32)
    
    # Add to index
    logger.info(f"Adding {len(product_ids)} products to FAISS index...")
    vector_ids = index_manager.add_product_vectors(product_ids, embeddings_array)
    
    logger.info(f"Successfully added {len(vector_ids)} products to index")
    
    # Save index
    logger.info("Saving index to disk...")
    index_manager.save()
    
    # Verify
    stats = index_manager.get_stats()
    logger.info(f"Index statistics: {stats}")
    
    # Test search
    logger.info("\nTesting search functionality...")
    query_embedding = embeddings[0]  # Use first product as query
    results = index_manager.search_with_scores(query_embedding, k=5)
    
    logger.info("Top 5 similar products for first product:")
    for product_id, score in results:
        logger.info(f"  {product_id}: {score:.4f}")
    
    logger.info("\nFAISS index initialization complete!")


if __name__ == "__main__":
    main()
