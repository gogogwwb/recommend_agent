"""
保险产品种子数据脚本

生成测试用保险产品数据，包含重疾险、医疗险、意外险、寿险四类
至少50个产品，用于测试和开发环境
"""
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.db_models import (
    InsuranceProduct, MaritalStatusEnum, IncomeRangeEnum, 
    RiskPreferenceEnum, HealthStatusEnum
)
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()


# 重疾险产品模板
CRITICAL_ILLNESS_TEMPLATES = [
    {"name": "康健一生重大疾病保险", "provider": "平安保险", "premium_min": 3000, "premium_max": 15000, "age_min": 0, "age_max": 60, "featured": True},
    {"name": "守护健康重疾险", "provider": "中国人寿", "premium_min": 2500, "premium_max": 12000, "age_min": 18, "age_max": 55, "featured": False},
    {"name": "无忧人生重大疾病保险", "provider": "太平洋保险", "premium_min": 4000, "premium_max": 18000, "age_min": 0, "age_max": 65, "featured": True},
    {"name": "健康守护重疾险", "provider": "新华保险", "premium_min": 2800, "premium_max": 10000, "age_min": 18, "age_max": 50, "featured": False},
    {"name": "安心保重大疾病保险", "provider": "泰康保险", "premium_min": 2000, "premium_max": 8000, "age_min": 0, "age_max": 60, "featured": False},
    {"name": "金盾重疾保障计划", "provider": "人保寿险", "premium_min": 3500, "premium_max": 20000, "age_min": 18, "age_max": 55, "featured": False},
    {"name": "康瑞重大疾病保险", "provider": "太平人寿", "premium_min": 3200, "premium_max": 14000, "age_min": 0, "age_max": 65, "featured": False},
    {"name": "爱健康重疾险", "provider": "阳光保险", "premium_min": 1800, "premium_max": 7000, "age_min": 18, "age_max": 50, "featured": False},
    {"name": "福满人生重疾险", "provider": "友邦保险", "premium_min": 5000, "premium_max": 30000, "age_min": 0, "age_max": 60, "featured": True},
    {"name": "康乐重疾保障计划", "provider": "华夏保险", "premium_min": 2500, "premium_max": 10000, "age_min": 18, "age_max": 55, "featured": False},
    {"name": "少儿安康重疾险", "provider": "平安保险", "premium_min": 1500, "premium_max": 6000, "age_min": 0, "age_max": 17, "featured": True},
    {"name": "女性关爱重疾险", "provider": "中国人寿", "premium_min": 2200, "premium_max": 9000, "age_min": 18, "age_max": 50, "featured": False},
    {"name": "老年安康重疾险", "provider": "太平洋保险", "premium_min": 3000, "premium_max": 10000, "age_min": 50, "age_max": 75, "featured": False},
]

# 医疗险产品模板
MEDICAL_TEMPLATES = [
    {"name": "百万医疗险", "provider": "平安保险", "premium_min": 200, "premium_max": 2000, "age_min": 0, "age_max": 65, "featured": True},
    {"name": "好医保长期医疗", "provider": "中国人保", "premium_min": 150, "premium_max": 1500, "age_min": 0, "age_max": 60, "featured": True},
    {"name": "尊享e生百万医疗", "provider": "众安保险", "premium_min": 136, "premium_max": 1800, "age_min": 0, "age_max": 70, "featured": False},
    {"name": "普惠e保百万医疗", "provider": "太平洋保险", "premium_min": 100, "premium_max": 1000, "age_min": 0, "age_max": 65, "featured": False},
    {"name": "少儿门诊医疗险", "provider": "平安保险", "premium_min": 500, "premium_max": 1500, "age_min": 0, "age_max": 17, "featured": False},
    {"name": "中端医疗险", "provider": "复星联合健康", "premium_min": 3000, "premium_max": 15000, "age_min": 0, "age_max": 64, "featured": False},
    {"name": "高端医疗险", "provider": "招商信诺", "premium_min": 10000, "premium_max": 100000, "age_min": 0, "age_max": 70, "featured": False},
    {"name": "防癌医疗险", "provider": "平安保险", "premium_min": 100, "premium_max": 1500, "age_min": 0, "age_max": 80, "featured": False},
    {"name": "惠民保", "provider": "各地政府指导", "premium_min": 69, "premium_max": 200, "age_min": 0, "age_max": 120, "featured": False},
    {"name": "海外医疗险", "provider": "友邦保险", "premium_min": 5000, "premium_max": 30000, "age_min": 0, "age_max": 70, "featured": False},
    {"name": "门诊医疗险", "provider": "众安保险", "premium_min": 300, "premium_max": 1000, "age_min": 18, "age_max": 60, "featured": False},
    {"name": "孕产医疗险", "provider": "复星联合健康", "premium_min": 5000, "premium_max": 20000, "age_min": 20, "age_max": 45, "featured": False},
]

# 意外险产品模板
ACCIDENT_TEMPLATES = [
    {"name": "综合意外险", "provider": "平安保险", "premium_min": 100, "premium_max": 500, "age_min": 0, "age_max": 65, "featured": True},
    {"name": "百万意外险", "provider": "中国人寿", "premium_min": 200, "premium_max": 1000, "age_min": 18, "age_max": 60, "featured": False},
    {"name": "少儿意外险", "provider": "平安保险", "premium_min": 60, "premium_max": 200, "age_min": 0, "age_max": 17, "featured": False},
    {"name": "老年意外险", "provider": "太平洋保险", "premium_min": 100, "premium_max": 500, "age_min": 50, "age_max": 85, "featured": False},
    {"name": "交通意外险", "provider": "中国人寿", "premium_min": 50, "premium_max": 300, "age_min": 0, "age_max": 70, "featured": False},
    {"name": "航空意外险", "provider": "平安保险", "premium_min": 20, "premium_max": 100, "age_min": 0, "age_max": 80, "featured": False},
    {"name": "旅游意外险", "provider": "太平洋保险", "premium_min": 30, "premium_max": 200, "age_min": 0, "age_max": 80, "featured": False},
    {"name": "高危职业意外险", "provider": "泰康保险", "premium_min": 300, "premium_max": 1500, "age_min": 18, "age_max": 60, "featured": False},
    {"name": "运动意外险", "provider": "众安保险", "premium_min": 50, "premium_max": 300, "age_min": 0, "age_max": 65, "featured": False},
    {"name": "猝死保障险", "provider": "平安保险", "premium_min": 100, "premium_max": 500, "age_min": 18, "age_max": 60, "featured": False},
    {"name": "学生意外险", "provider": "中国人寿", "premium_min": 50, "premium_max": 150, "age_min": 3, "age_max": 25, "featured": False},
    {"name": "驾乘意外险", "provider": "太平洋保险", "premium_min": 100, "premium_max": 500, "age_min": 18, "age_max": 70, "featured": False},
]

# 寿险产品模板
LIFE_TEMPLATES = [
    {"name": "定期寿险", "provider": "平安保险", "premium_min": 500, "premium_max": 5000, "age_min": 18, "age_max": 60, "featured": True},
    {"name": "终身寿险", "provider": "中国人寿", "premium_min": 3000, "premium_max": 30000, "age_min": 0, "age_max": 70, "featured": True},
    {"name": "增额终身寿险", "provider": "太平洋保险", "premium_min": 5000, "premium_max": 100000, "age_min": 0, "age_max": 70, "featured": True},
    {"name": "定期寿险（高保额）", "provider": "华贵人寿", "premium_min": 300, "premium_max": 3000, "age_min": 18, "age_max": 60, "featured": False},
    {"name": "减额定期寿险", "provider": "阳光保险", "premium_min": 200, "premium_max": 2000, "age_min": 18, "age_max": 55, "featured": False},
    {"name": "两全保险", "provider": "泰康保险", "premium_min": 2000, "premium_max": 20000, "age_min": 0, "age_max": 60, "featured": False},
    {"name": "年金保险", "provider": "中国人寿", "premium_min": 5000, "premium_max": 100000, "age_min": 0, "age_max": 65, "featured": False},
    {"name": "养老年金保险", "provider": "平安保险", "premium_min": 3000, "premium_max": 50000, "age_min": 18, "age_max": 60, "featured": False},
    {"name": "教育年金保险", "provider": "太平洋保险", "premium_min": 2000, "premium_max": 30000, "age_min": 0, "age_max": 12, "featured": False},
    {"name": "万能型终身寿险", "provider": "友邦保险", "premium_min": 10000, "premium_max": 200000, "age_min": 0, "age_max": 70, "featured": False},
    {"name": "分红型终身寿险", "provider": "新华保险", "premium_min": 5000, "premium_max": 50000, "age_min": 0, "age_max": 65, "featured": False},
    {"name": "投资连结保险", "provider": "平安保险", "premium_min": 10000, "premium_max": 500000, "age_min": 18, "age_max": 60, "featured": False},
    {"name": "家庭收入保障险", "provider": "中国人寿", "premium_min": 1000, "premium_max": 10000, "age_min": 20, "age_max": 50, "featured": False},
]


def generate_product_data(
    product_type: str,
    templates: List[Dict[str, Any]],
    type_specific_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """根据模板生成产品数据"""
    products = []
    
    for i, template in enumerate(templates, 1):
        product_id = f"{type_specific_data['id_prefix']}-{i:03d}"
        
        product = {
            "product_id": product_id,
            "product_name": template["name"],
            "product_type": product_type,
            "provider": template["provider"],
            "coverage_scope": type_specific_data["coverage_scope"],
            "coverage_amount_min": type_specific_data["coverage_amount_min"],
            "coverage_amount_max": type_specific_data["coverage_amount_max"],
            "exclusions": type_specific_data["exclusions"],
            "premium_min": template["premium_min"],
            "premium_max": template["premium_max"],
            "payment_period": type_specific_data["payment_period"],
            "coverage_period": type_specific_data["coverage_period"],
            "age_min": template["age_min"],
            "age_max": template["age_max"],
            "occupation_restrictions": type_specific_data.get("occupation_restrictions", []),
            "health_requirements": type_specific_data.get("health_requirements", []),
            "region_restrictions": type_specific_data.get("region_restrictions", []),
            "features": type_specific_data["features"],
            "advantages": type_specific_data["advantages"],
            "suitable_for": type_specific_data["suitable_for"],
            "claim_process": type_specific_data["claim_process"],
            "waiting_period_days": type_specific_data["waiting_period_days"],
            "deductible": type_specific_data["deductible"],
            "is_available": True,
            "is_featured": template.get("featured", False)
        }
        products.append(product)
    
    return products


def generate_all_products() -> List[Dict[str, Any]]:
    """生成所有产品数据"""
    all_products = []
    
    # 重疾险配置
    critical_illness_config = {
        "id_prefix": "CI",
        "coverage_scope": ["重大疾病", "轻症", "中症", "身故", "豁免保费"],
        "coverage_amount_min": 50000,
        "coverage_amount_max": 1500000,
        "exclusions": ["既往症", "等待期内确诊", "故意自伤", "酒驾", "吸毒"],
        "payment_period": ["趸交", "5年", "10年", "20年", "30年"],
        "coverage_period": ["终身", "至70岁", "至80岁"],
        "health_requirements": ["健康告知"],
        "features": ["重疾保障", "轻症保障", "中症保障", "保费豁免"],
        "advantages": ["保障全面", "理赔便捷"],
        "suitable_for": ["家庭经济支柱", "关注健康保障的人群"],
        "claim_process": "确诊即赔",
        "waiting_period_days": 90,
        "deductible": 0
    }
    
    # 医疗险配置
    medical_config = {
        "id_prefix": "MED",
        "coverage_scope": ["住院医疗", "门诊手术", "特殊门诊", "重疾医疗"],
        "coverage_amount_min": 10000,
        "coverage_amount_max": 6000000,
        "exclusions": ["既往症", "整形美容", "牙科治疗", "体检"],
        "payment_period": ["一年一交"],
        "coverage_period": ["一年", "保证续保20年"],
        "health_requirements": ["健康告知"],
        "features": ["住院报销", "门诊报销", "重疾医疗"],
        "advantages": ["保额高", "保障全面", "价格低"],
        "suitable_for": ["所有人群", "医保补充"],
        "claim_process": "住院后提交材料报销",
        "waiting_period_days": 30,
        "deductible": 10000
    }
    
    # 意外险配置
    accident_config = {
        "id_prefix": "ACC",
        "coverage_scope": ["意外身故", "意外伤残", "意外医疗", "意外住院津贴"],
        "coverage_amount_min": 10000,
        "coverage_amount_max": 5000000,
        "exclusions": ["故意行为", "犯罪行为", "酒驾", "高风险运动"],
        "payment_period": ["一年一交"],
        "coverage_period": ["一年"],
        "occupation_restrictions": ["高危职业除外"],
        "features": ["意外身故伤残", "意外医疗", "住院津贴"],
        "advantages": ["保障全面", "价格低", "投保年龄宽"],
        "suitable_for": ["所有人群", "基础意外保障"],
        "claim_process": "提交材料理赔",
        "waiting_period_days": 0,
        "deductible": 100
    }
    
    # 寿险配置
    life_config = {
        "id_prefix": "LIFE",
        "coverage_scope": ["身故", "全残", "生存金", "祝寿金"],
        "coverage_amount_min": 100000,
        "coverage_amount_max": 10000000,
        "exclusions": ["故意行为", "犯罪行为", "两年内自杀"],
        "payment_period": ["趸交", "5年", "10年", "20年", "30年"],
        "coverage_period": ["定期", "终身"],
        "health_requirements": ["健康告知"],
        "features": ["身故保障", "全残保障", "现金价值"],
        "advantages": ["保障稳定", "资产传承"],
        "suitable_for": ["家庭经济支柱", "有家庭责任的人群"],
        "claim_process": "提交材料理赔",
        "waiting_period_days": 0,
        "deductible": 0
    }
    
    # 生成各类产品
    all_products.extend(generate_product_data("critical_illness", CRITICAL_ILLNESS_TEMPLATES, critical_illness_config))
    all_products.extend(generate_product_data("medical", MEDICAL_TEMPLATES, medical_config))
    all_products.extend(generate_product_data("accident", ACCIDENT_TEMPLATES, accident_config))
    all_products.extend(generate_product_data("life", LIFE_TEMPLATES, life_config))
    
    return all_products


def save_to_json(products: List[Dict[str, Any]], output_path: str = "data/insurance_products.json"):
    """保存产品数据到JSON文件"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    data = {
        "generated_at": datetime.now().isoformat(),
        "total_count": len(products),
        "by_type": {
            "critical_illness": len([p for p in products if p["product_type"] == "critical_illness"]),
            "medical": len([p for p in products if p["product_type"] == "medical"]),
            "accident": len([p for p in products if p["product_type"] == "accident"]),
            "life": len([p for p in products if p["product_type"] == "life"])
        },
        "products": products
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"已生成 {len(products)} 个产品数据，保存到 {output_path}")
    print(f"  - 重疾险: {data['by_type']['critical_illness']} 个")
    print(f"  - 医疗险: {data['by_type']['medical']} 个")
    print(f"  - 意外险: {data['by_type']['accident']} 个")
    print(f"  - 寿险: {data['by_type']['life']} 个")


def seed_to_database(products: List[Dict[str, Any]], db_url: str = None):
    """将产品数据导入数据库"""
    if db_url is None:
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "insurance_agent")
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    engine = create_engine(db_url)
    
    with Session(engine) as session:
        # 检查是否已有产品数据
        existing_count = session.query(InsuranceProduct).count()
        if existing_count > 0:
            print(f"数据库中已有 {existing_count} 个产品，跳过导入")
            return
        
        # 导入产品数据
        for product_data in products:
            product = InsuranceProduct(
                product_id=product_data["product_id"],
                product_name=product_data["product_name"],
                product_type=product_data["product_type"],
                provider=product_data["provider"],
                coverage_scope=product_data["coverage_scope"],
                coverage_amount_min=product_data["coverage_amount_min"],
                coverage_amount_max=product_data["coverage_amount_max"],
                exclusions=product_data["exclusions"],
                premium_min=product_data["premium_min"],
                premium_max=product_data["premium_max"],
                payment_period=product_data["payment_period"],
                coverage_period=product_data["coverage_period"],
                age_min=product_data["age_min"],
                age_max=product_data["age_max"],
                occupation_restrictions=product_data.get("occupation_restrictions", []),
                health_requirements=product_data.get("health_requirements", []),
                region_restrictions=product_data.get("region_restrictions", []),
                features=product_data["features"],
                advantages=product_data["advantages"],
                suitable_for=product_data["suitable_for"],
                claim_process=product_data["claim_process"],
                waiting_period_days=product_data["waiting_period_days"],
                deductible=product_data["deductible"],
                is_available=product_data["is_available"],
                is_featured=product_data["is_featured"]
            )
            session.add(product)
        
        session.commit()
        print(f"已成功导入 {len(products)} 个产品到数据库")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="保险产品种子数据生成工具")
    parser.add_argument("--output", "-o", default="data/insurance_products.json", help="输出JSON文件路径")
    parser.add_argument("--seed-db", action="store_true", help="将数据导入数据库")
    parser.add_argument("--db-url", help="数据库连接URL")
    
    args = parser.parse_args()
    
    # 生成产品数据
    products = generate_all_products()
    
    # 保存到JSON
    save_to_json(products, args.output)
    
    # 可选：导入数据库
    if args.seed_db:
        seed_to_database(products, args.db_url)


if __name__ == "__main__":
    main()
