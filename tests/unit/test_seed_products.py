"""测试保险产品种子数据脚本"""
import pytest
import json
import os
from datetime import datetime


class TestSeedProductsScript:
    """测试种子数据生成脚本"""
    
    def test_generate_all_products_count(self):
        """测试生成的产品总数"""
        from scripts.seed_products import generate_all_products
        
        products = generate_all_products()
        
        # 验证总数至少50个
        assert len(products) >= 50, f"Expected at least 50 products, got {len(products)}"
    
    def test_generate_products_by_type(self):
        """测试各类型产品数量"""
        from scripts.seed_products import generate_all_products
        
        products = generate_all_products()
        
        # 统计各类型数量
        by_type = {}
        for product in products:
            product_type = product['product_type']
            by_type[product_type] = by_type.get(product_type, 0) + 1
        
        # 验证每个类型都有产品
        assert 'critical_illness' in by_type, "Missing critical_illness products"
        assert 'medical' in by_type, "Missing medical products"
        assert 'accident' in by_type, "Missing accident products"
        assert 'life' in by_type, "Missing life products"
        
        # 验证每个类型至少有10个产品
        for product_type, count in by_type.items():
            assert count >= 10, f"Expected at least 10 {product_type} products, got {count}"
    
    def test_product_required_fields(self):
        """测试产品必填字段"""
        from scripts.seed_products import generate_all_products
        
        products = generate_all_products()
        
        required_fields = [
            'product_id', 'product_name', 'product_type', 'provider',
            'coverage_scope', 'premium_min', 'premium_max',
            'age_min', 'age_max', 'is_available'
        ]
        
        for product in products:
            for field in required_fields:
                assert field in product, f"Product {product.get('product_id', 'unknown')} missing required field: {field}"
    
    def test_product_id_format(self):
        """测试产品ID格式"""
        from scripts.seed_products import generate_all_products
        
        products = generate_all_products()
        
        expected_prefixes = {
            'critical_illness': 'CI-',
            'medical': 'MED-',
            'accident': 'ACC-',
            'life': 'LIFE-'
        }
        
        for product in products:
            product_type = product['product_type']
            product_id = product['product_id']
            expected_prefix = expected_prefixes.get(product_type)
            
            assert expected_prefix is not None, f"Unknown product type: {product_type}"
            assert product_id.startswith(expected_prefix), f"Product ID {product_id} should start with {expected_prefix}"
    
    def test_product_age_range_valid(self):
        """测试产品年龄范围有效性"""
        from scripts.seed_products import generate_all_products
        
        products = generate_all_products()
        
        for product in products:
            age_min = product.get('age_min', 0)
            age_max = product.get('age_max', 0)
            
            assert age_min >= 0, f"Product {product['product_id']} has invalid age_min: {age_min}"
            assert age_max >= age_min, f"Product {product['product_id']} has age_max < age_min"
            assert age_max <= 120, f"Product {product['product_id']} has age_max > 120: {age_max}"
    
    def test_product_premium_range_valid(self):
        """测试产品保费范围有效性"""
        from scripts.seed_products import generate_all_products
        
        products = generate_all_products()
        
        for product in products:
            premium_min = product.get('premium_min', 0)
            premium_max = product.get('premium_max', 0)
            
            assert premium_min >= 0, f"Product {product['product_id']} has invalid premium_min: {premium_min}"
            assert premium_max >= premium_min, f"Product {product['product_id']} has premium_max < premium_min"
    
    def test_product_type_valid(self):
        """测试产品类型有效性"""
        from scripts.seed_products import generate_all_products
        
        products = generate_all_products()
        
        valid_types = {'critical_illness', 'medical', 'accident', 'life'}
        
        for product in products:
            product_type = product['product_type']
            assert product_type in valid_types, f"Product {product['product_id']} has invalid type: {product_type}"
    
    def test_json_file_exists(self):
        """测试JSON文件是否存在"""
        json_path = "data/insurance_products.json"
        
        assert os.path.exists(json_path), f"Seed data file not found: {json_path}"
    
    def test_json_file_valid(self):
        """测试JSON文件有效性"""
        json_path = "data/insurance_products.json"
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 验证结构
        assert 'products' in data, "JSON file missing 'products' key"
        assert 'total_count' in data, "JSON file missing 'total_count' key"
        assert 'by_type' in data, "JSON file missing 'by_type' key"
        
        # 验证数量一致
        assert data['total_count'] == len(data['products']), "total_count does not match products length"
    
    def test_featured_products_exist(self):
        """测试是否有推荐产品"""
        from scripts.seed_products import generate_all_products
        
        products = generate_all_products()
        
        featured_products = [p for p in products if p.get('is_featured', False)]
        
        assert len(featured_products) > 0, "No featured products found"
    
    def test_all_products_available(self):
        """测试所有产品是否可用"""
        from scripts.seed_products import generate_all_products
        
        products = generate_all_products()
        
        for product in products:
            assert product.get('is_available', False) is True, f"Product {product['product_id']} is not available"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
