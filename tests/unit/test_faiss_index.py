"""
Unit tests for FAISS Vector Index Manager

Tests cover:
- Index initialization
- Adding product vectors (single and batch)
- Vector search
- Persistence (save/load)
- Product ID mapping
- Error handling
"""
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import numpy as np

from utils.faiss_index import (
    FAISSIndexManager,
    FAISSIndexError,
    ProductNotFoundError,
    get_faiss_index_manager,
    reset_faiss_index_manager
)


class TestFAISSIndexManager:
    """Test suite for FAISSIndexManager"""
    
    @pytest.fixture
    def temp_index_path(self):
        """Create a temporary directory for index files"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def index_manager(self, temp_index_path):
        """Create a fresh FAISSIndexManager for each test"""
        manager = FAISSIndexManager(
            dimension=768,
            index_path=temp_index_path,
            auto_load=False
        )
        yield manager
        manager.clear()
    
    @pytest.fixture
    def sample_embedding(self):
        """Generate a sample embedding vector"""
        np.random.seed(42)
        return np.random.randn(768).astype(np.float32)
    
    @pytest.fixture
    def sample_embeddings(self):
        """Generate multiple sample embedding vectors"""
        np.random.seed(42)
        return np.random.randn(10, 768).astype(np.float32)
    
    # ==================== Initialization Tests ====================
    
    def test_initialization_default_dimension(self, temp_index_path):
        """Test initialization with default dimension"""
        manager = FAISSIndexManager(index_path=temp_index_path, auto_load=False)
        assert manager.dimension == 768
        assert manager.get_total_products() == 0
        assert manager.get_index_size() == 0
    
    def test_initialization_custom_dimension(self, temp_index_path):
        """Test initialization with custom dimension"""
        manager = FAISSIndexManager(dimension=512, index_path=temp_index_path, auto_load=False)
        assert manager.dimension == 512
    
    def test_initialization_creates_index(self, index_manager):
        """Test that initialization creates a valid FAISS index"""
        assert index_manager.index is not None
        assert index_manager.get_stats()["index_type"] == "IndexFlatIP"
    
    # ==================== Add Product Vector Tests ====================
    
    def test_add_single_product_vector(self, index_manager, sample_embedding):
        """Test adding a single product vector"""
        product_id = "prod-001"
        vector_id = index_manager.add_product_vector(product_id, sample_embedding)
        
        assert vector_id == 0
        assert index_manager.has_product(product_id)
        assert index_manager.get_product_vector_id(product_id) == 0
        assert index_manager.get_total_products() == 1
    
    def test_add_product_vector_reshapes_1d(self, index_manager, sample_embedding):
        """Test that 1D embeddings are automatically reshaped"""
        product_id = "prod-001"
        vector_id = index_manager.add_product_vector(product_id, sample_embedding)
        assert vector_id == 0
    
    def test_add_multiple_product_vectors(self, index_manager, sample_embeddings):
        """Test adding multiple product vectors"""
        product_ids = [f"prod-{i:03d}" for i in range(10)]
        vector_ids = index_manager.add_product_vectors(product_ids, sample_embeddings)
        
        assert len(vector_ids) == 10
        assert index_manager.get_total_products() == 10
        
        for i, product_id in enumerate(product_ids):
            assert index_manager.has_product(product_id)
            assert index_manager.get_product_vector_id(product_id) == i
    
    def test_add_product_vector_dimension_mismatch(self, index_manager):
        """Test that dimension mismatch raises error"""
        wrong_dimension_embedding = np.random.randn(512).astype(np.float32)
        
        with pytest.raises(FAISSIndexError) as exc_info:
            index_manager.add_product_vector("prod-001", wrong_dimension_embedding)
        
        assert "dimension mismatch" in str(exc_info.value).lower()
    
    def test_add_duplicate_product_without_update(self, index_manager, sample_embedding):
        """Test that adding duplicate product raises error"""
        product_id = "prod-001"
        index_manager.add_product_vector(product_id, sample_embedding)
        
        with pytest.raises(FAISSIndexError) as exc_info:
            index_manager.add_product_vector(product_id, sample_embedding)
        
        assert "already exists" in str(exc_info.value).lower()
    
    def test_add_duplicate_product_with_update(self, index_manager, sample_embedding):
        """Test that adding duplicate product with allow_update succeeds"""
        product_id = "prod-001"
        vector_id1 = index_manager.add_product_vector(product_id, sample_embedding)
        
        # Add with allow_update=True
        new_embedding = np.random.randn(768).astype(np.float32)
        vector_id2 = index_manager.add_product_vector(
            product_id, new_embedding, allow_update=True
        )
        
        # New vector should have different ID
        assert vector_id2 != vector_id1
        # Product should map to new vector
        assert index_manager.get_product_vector_id(product_id) == vector_id2
    
    # ==================== Search Tests ====================
    
    def test_search_finds_similar_products(self, index_manager, sample_embeddings):
        """Test that search returns similar products"""
        # Add products
        product_ids = [f"prod-{i:03d}" for i in range(10)]
        index_manager.add_product_vectors(product_ids, sample_embeddings)
        
        # Search with first product's embedding (should find itself as most similar)
        query = sample_embeddings[0]
        distances, found_ids = index_manager.search(query, k=5)
        
        assert len(found_ids) == 5
        assert found_ids[0] == "prod-000"  # Most similar should be itself
        assert all(isinstance(d, (int, float, np.floating)) for d in distances)
    
    def test_search_with_scores(self, index_manager, sample_embeddings):
        """Test search_with_scores returns (product_id, score) pairs"""
        product_ids = [f"prod-{i:03d}" for i in range(10)]
        index_manager.add_product_vectors(product_ids, sample_embeddings)
        
        query = sample_embeddings[0]
        results = index_manager.search_with_scores(query, k=5)
        
        assert len(results) == 5
        assert all(isinstance(pid, str) for pid, _ in results)
        assert all(isinstance(score, float) for _, score in results)
        # Results should be sorted by score (descending for inner product)
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)
    
    def test_search_empty_index_raises_error(self, index_manager, sample_embedding):
        """Test that searching empty index raises error"""
        with pytest.raises(FAISSIndexError) as exc_info:
            index_manager.search(sample_embedding, k=5)
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_search_k_larger_than_index(self, index_manager, sample_embeddings):
        """Test that k is adjusted when larger than index size"""
        product_ids = [f"prod-{i:03d}" for i in range(5)]
        index_manager.add_product_vectors(product_ids, sample_embeddings[:5])
        
        query = sample_embeddings[0]
        distances, found_ids = index_manager.search(query, k=10)
        
        # Should return only 5 results (index size)
        assert len(found_ids) == 5
    
    def test_search_dimension_mismatch(self, index_manager, sample_embeddings):
        """Test that search with wrong dimension raises error"""
        product_ids = [f"prod-{i:03d}" for i in range(5)]
        index_manager.add_product_vectors(product_ids, sample_embeddings[:5])
        
        wrong_query = np.random.randn(512).astype(np.float32)
        
        with pytest.raises(FAISSIndexError) as exc_info:
            index_manager.search(wrong_query, k=5)
        
        assert "dimension mismatch" in str(exc_info.value).lower()
    
    # ==================== Mapping Tests ====================
    
    def test_product_to_vector_mapping(self, index_manager, sample_embeddings):
        """Test product_id to vector_id mapping"""
        product_ids = ["prod-a", "prod-b", "prod-c"]
        index_manager.add_product_vectors(product_ids, sample_embeddings[:3])
        
        assert index_manager.get_product_vector_id("prod-a") == 0
        assert index_manager.get_product_vector_id("prod-b") == 1
        assert index_manager.get_product_vector_id("prod-c") == 2
        assert index_manager.get_product_vector_id("nonexistent") is None
    
    def test_vector_to_product_mapping(self, index_manager, sample_embeddings):
        """Test vector_id to product_id mapping"""
        product_ids = ["prod-a", "prod-b", "prod-c"]
        index_manager.add_product_vectors(product_ids, sample_embeddings[:3])
        
        assert index_manager.get_product_id(0) == "prod-a"
        assert index_manager.get_product_id(1) == "prod-b"
        assert index_manager.get_product_id(2) == "prod-c"
        assert index_manager.get_product_id(999) is None
    
    def test_has_product(self, index_manager, sample_embedding):
        """Test has_product method"""
        assert not index_manager.has_product("prod-001")
        
        index_manager.add_product_vector("prod-001", sample_embedding)
        
        assert index_manager.has_product("prod-001")
        assert not index_manager.has_product("prod-002")
    
    def test_contains_operator(self, index_manager, sample_embedding):
        """Test __contains__ operator"""
        assert "prod-001" not in index_manager
        
        index_manager.add_product_vector("prod-001", sample_embedding)
        
        assert "prod-001" in index_manager
        assert "prod-002" not in index_manager
    
    def test_len_operator(self, index_manager, sample_embeddings):
        """Test __len__ operator"""
        assert len(index_manager) == 0
        
        product_ids = ["prod-a", "prod-b", "prod-c"]
        index_manager.add_product_vectors(product_ids, sample_embeddings[:3])
        
        assert len(index_manager) == 3
    
    # ==================== Persistence Tests ====================
    
    def test_save_and_load(self, index_manager, sample_embeddings, temp_index_path):
        """Test saving and loading index"""
        # Add products
        product_ids = [f"prod-{i:03d}" for i in range(5)]
        index_manager.add_product_vectors(product_ids, sample_embeddings[:5])
        
        # Save
        index_manager.save()
        
        # Verify files exist
        assert (Path(temp_index_path) / "index.faiss").exists()
        assert (Path(temp_index_path) / "mappings.json").exists()
        
        # Create new manager and load
        new_manager = FAISSIndexManager(
            dimension=768,
            index_path=temp_index_path,
            auto_load=False
        )
        success = new_manager.load()
        
        assert success
        assert new_manager.get_total_products() == 5
        assert new_manager.has_product("prod-000")
        assert new_manager.has_product("prod-004")
    
    def test_auto_load_on_init(self, sample_embeddings, temp_index_path):
        """Test auto-loading on initialization"""
        # Create and save index
        manager1 = FAISSIndexManager(
            dimension=768,
            index_path=temp_index_path,
            auto_load=False
        )
        product_ids = [f"prod-{i:03d}" for i in range(3)]
        manager1.add_product_vectors(product_ids, sample_embeddings[:3])
        manager1.save()
        
        # Create new manager with auto_load=True
        manager2 = FAISSIndexManager(
            dimension=768,
            index_path=temp_index_path,
            auto_load=True
        )
        
        assert manager2.get_total_products() == 3
        assert manager2.has_product("prod-000")
    
    def test_load_nonexistent_index(self, temp_index_path):
        """Test loading from nonexistent path"""
        manager = FAISSIndexManager(
            dimension=768,
            index_path=temp_index_path,
            auto_load=False
        )
        
        # Try to load from empty path
        empty_path = tempfile.mkdtemp()
        shutil.rmtree(empty_path)
        
        success = manager.load(empty_path)
        assert not success
        assert manager.get_total_products() == 0
    
    def test_save_creates_directory(self, sample_embedding):
        """Test that save creates directory if it doesn't exist"""
        temp_base = tempfile.mkdtemp()
        new_path = os.path.join(temp_base, "new", "nested", "path")
        
        try:
            manager = FAISSIndexManager(
                dimension=768,
                index_path=new_path,
                auto_load=False
            )
            manager.add_product_vector("prod-001", sample_embedding)
            manager.save()
            
            assert os.path.exists(new_path)
            assert os.path.exists(os.path.join(new_path, "index.faiss"))
        finally:
            shutil.rmtree(temp_base, ignore_errors=True)
    
    # ==================== Clear Tests ====================
    
    def test_clear_index(self, index_manager, sample_embeddings):
        """Test clearing the index"""
        product_ids = [f"prod-{i:03d}" for i in range(5)]
        index_manager.add_product_vectors(product_ids, sample_embeddings[:5])
        
        assert index_manager.get_total_products() == 5
        
        index_manager.clear()
        
        assert index_manager.get_total_products() == 0
        assert index_manager.get_index_size() == 0
        assert not index_manager.has_product("prod-000")
    
    # ==================== Statistics Tests ====================
    
    def test_get_stats(self, index_manager, sample_embeddings):
        """Test get_stats method"""
        stats = index_manager.get_stats()
        
        assert stats["dimension"] == 768
        assert stats["total_vectors"] == 0
        assert stats["total_products"] == 0
        assert stats["index_type"] == "IndexFlatIP"
        assert stats["is_trained"] is True
        
        # Add products and check stats
        product_ids = [f"prod-{i:03d}" for i in range(3)]
        index_manager.add_product_vectors(product_ids, sample_embeddings[:3])
        
        stats = index_manager.get_stats()
        assert stats["total_vectors"] == 3
        assert stats["total_products"] == 3
    
    # ==================== Error Handling Tests ====================
    
    def test_invalid_embedding_shape_3d(self, index_manager):
        """Test that 3D embeddings raise error"""
        invalid_embedding = np.random.randn(1, 768, 1).astype(np.float32)
        
        with pytest.raises(FAISSIndexError) as exc_info:
            index_manager.add_product_vector("prod-001", invalid_embedding)
        
        assert "invalid" in str(exc_info.value).lower()
    
    def test_batch_embeddings_count_mismatch(self, index_manager, sample_embeddings):
        """Test that mismatched product_ids and embeddings count raises error"""
        product_ids = ["prod-001", "prod-002"]  # 2 IDs
        embeddings = sample_embeddings[:5]  # 5 embeddings
        
        with pytest.raises(FAISSIndexError) as exc_info:
            index_manager.add_product_vectors(product_ids, embeddings)
        
        assert "doesn't match" in str(exc_info.value).lower()
    
    # ==================== Thread Safety Tests ====================
    
    def test_repr(self, index_manager, sample_embeddings):
        """Test __repr__ method"""
        repr_str = repr(index_manager)
        assert "FAISSIndexManager" in repr_str
        assert "dimension=768" in repr_str
        assert "products=0" in repr_str
        
        product_ids = [f"prod-{i:03d}" for i in range(3)]
        index_manager.add_product_vectors(product_ids, sample_embeddings[:3])
        
        repr_str = repr(index_manager)
        assert "products=3" in repr_str


class TestGlobalIndexManager:
    """Test global index manager functions"""
    
    def test_get_faiss_index_manager_singleton(self):
        """Test that get_faiss_index_manager returns singleton"""
        reset_faiss_index_manager()
        
        manager1 = get_faiss_index_manager(force_new=True)
        manager2 = get_faiss_index_manager()
        
        assert manager1 is manager2
    
    def test_reset_faiss_index_manager(self):
        """Test that reset clears the singleton"""
        manager1 = get_faiss_index_manager(force_new=True)
        
        reset_faiss_index_manager()
        
        manager2 = get_faiss_index_manager(force_new=True)
        
        assert manager1 is not manager2


class TestFAISSIndexManagerIntegration:
    """Integration tests for FAISSIndexManager"""
    
    @pytest.fixture
    def temp_index_path(self):
        """Create a temporary directory for index files"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_full_workflow(self, temp_index_path):
        """Test complete workflow: create, add, search, save, load, search again"""
        # 1. Create index
        manager = FAISSIndexManager(
            dimension=768,
            index_path=temp_index_path,
            auto_load=False
        )
        
        # 2. Generate embeddings (simulate product vectors)
        np.random.seed(42)
        embeddings = np.random.randn(20, 768).astype(np.float32)
        product_ids = [f"insurance-product-{i:03d}" for i in range(20)]
        
        # 3. Add products
        manager.add_product_vectors(product_ids, embeddings)
        assert manager.get_total_products() == 20
        
        # 4. Search
        query = embeddings[0]
        results = manager.search_with_scores(query, k=5)
        assert len(results) == 5
        assert results[0][0] == product_ids[0]  # Most similar is itself
        
        # 5. Save
        manager.save()
        
        # 6. Load in new manager
        new_manager = FAISSIndexManager(
            dimension=768,
            index_path=temp_index_path,
            auto_load=False
        )
        new_manager.load()
        
        # 7. Search again
        results2 = new_manager.search_with_scores(query, k=5)
        assert len(results2) == 5
        assert results2[0][0] == product_ids[0]
        
        # 8. Verify mappings
        for product_id in product_ids:
            assert new_manager.has_product(product_id)
