"""seed insurance products

Revision ID: seed_insurance_products
Revises: add_warm_data_layer
Create Date: 2026-04-19 16:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import json
import os

# revision identifiers, used by Alembic.
revision = 'seed_insurance_products'
down_revision = 'add_warm_data_layer'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Seed insurance products data into the database
    
    This migration inserts 50 insurance products across 4 categories:
    - 重疾险 (Critical Illness): 13 products
    - 医疗险 (Medical): 12 products
    - 意外险 (Accident): 12 products
    - 寿险 (Life): 13 products
    """
    # Get the path to the seed data file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    seed_file = os.path.join(project_root, 'data', 'insurance_products.json')
    
    # Check if seed file exists
    if not os.path.exists(seed_file):
        print(f"Warning: Seed file not found at {seed_file}")
        return
    
    # Load seed data
    with open(seed_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    products = data.get('products', [])
    
    if not products:
        print("Warning: No products found in seed file")
        return
    
    # Get database connection
    conn = op.get_bind()
    
    # Check if products already exist
    result = conn.execute(sa.text("SELECT COUNT(*) FROM insurance_products"))
    existing_count = result.scalar()
    
    if existing_count > 0:
        print(f"Database already contains {existing_count} products, skipping seed")
        return
    
    # Insert products
    for product in products:
        conn.execute(
            sa.text("""
                INSERT INTO insurance_products (
                    product_id, product_name, product_type, provider,
                    coverage_scope, coverage_amount_min, coverage_amount_max,
                    exclusions, premium_min, premium_max,
                    payment_period, coverage_period,
                    age_min, age_max,
                    occupation_restrictions, health_requirements, region_restrictions,
                    features, advantages, suitable_for,
                    claim_process, waiting_period_days, deductible,
                    is_available, is_featured, version
                ) VALUES (
                    :product_id, :product_name, :product_type, :provider,
                    :coverage_scope, :coverage_amount_min, :coverage_amount_max,
                    :exclusions, :premium_min, :premium_max,
                    :payment_period, :coverage_period,
                    :age_min, :age_max,
                    :occupation_restrictions, :health_requirements, :region_restrictions,
                    :features, :advantages, :suitable_for,
                    :claim_process, :waiting_period_days, :deductible,
                    :is_available, :is_featured, 1
                )
            """),
            {
                'product_id': product['product_id'],
                'product_name': product['product_name'],
                'product_type': product['product_type'],
                'provider': product['provider'],
                'coverage_scope': product.get('coverage_scope', []),
                'coverage_amount_min': product.get('coverage_amount_min'),
                'coverage_amount_max': product.get('coverage_amount_max'),
                'exclusions': product.get('exclusions', []),
                'premium_min': product['premium_min'],
                'premium_max': product['premium_max'],
                'payment_period': product.get('payment_period', []),
                'coverage_period': product.get('coverage_period', []),
                'age_min': product['age_min'],
                'age_max': product['age_max'],
                'occupation_restrictions': product.get('occupation_restrictions', []),
                'health_requirements': product.get('health_requirements', []),
                'region_restrictions': product.get('region_restrictions', []),
                'features': product.get('features', []),
                'advantages': product.get('advantages', []),
                'suitable_for': product.get('suitable_for', []),
                'claim_process': product.get('claim_process'),
                'waiting_period_days': product.get('waiting_period_days', 0),
                'deductible': product.get('deductible', 0),
                'is_available': product.get('is_available', True),
                'is_featured': product.get('is_featured', False)
            }
        )
    
    print(f"Successfully seeded {len(products)} insurance products")


def downgrade() -> None:
    """
    Remove seeded insurance products
    
    This will delete all products that were inserted by this migration
    """
    conn = op.get_bind()
    
    # Delete all products with IDs matching our seed pattern
    conn.execute(sa.text("""
        DELETE FROM insurance_products 
        WHERE product_id LIKE 'CI-%' 
           OR product_id LIKE 'MED-%' 
           OR product_id LIKE 'ACC-%' 
           OR product_id LIKE 'LIFE-%'
    """))
    
    print("Removed seeded insurance products")
