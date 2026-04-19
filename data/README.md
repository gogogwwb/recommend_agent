# 数据目录

本目录包含保险智能推荐Agent系统的种子数据和配置文件。

## 文件说明

### insurance_products.json

保险产品种子数据，包含50个测试用保险产品，覆盖4个主要类别：

| 产品类型 | 数量 | 产品ID前缀 |
|---------|------|-----------|
| 重疾险 (critical_illness) | 13 | CI- |
| 医疗险 (medical) | 12 | MED- |
| 意外险 (accident) | 12 | ACC- |
| 寿险 (life) | 13 | LIFE- |

#### 数据结构

每个产品包含以下字段：

```json
{
  "product_id": "CI-001",
  "product_name": "康健一生重大疾病保险",
  "product_type": "critical_illness",
  "provider": "平安保险",
  "coverage_scope": ["重大疾病", "轻症", "中症", "身故", "豁免保费"],
  "coverage_amount_min": 50000,
  "coverage_amount_max": 1500000,
  "exclusions": ["既往症", "等待期内确诊", "故意自伤", "酒驾", "吸毒"],
  "premium_min": 3000,
  "premium_max": 15000,
  "payment_period": ["趸交", "5年", "10年", "20年", "30年"],
  "coverage_period": ["终身", "至70岁", "至80岁"],
  "age_min": 0,
  "age_max": 60,
  "occupation_restrictions": [],
  "health_requirements": ["健康告知"],
  "region_restrictions": [],
  "features": ["重疾保障", "轻症保障", "中症保障", "保费豁免"],
  "advantages": ["保障全面", "理赔便捷"],
  "suitable_for": ["家庭经济支柱", "关注健康保障的人群"],
  "claim_process": "确诊即赔",
  "waiting_period_days": 90,
  "deductible": 0,
  "is_available": true,
  "is_featured": true
}
```

#### 使用方法

1. **生成JSON文件**：
   ```bash
   python scripts/seed_products.py --output data/insurance_products.json
   ```

2. **导入数据库**：
   ```bash
   # 使用Alembic迁移
   alembic upgrade head
   
   # 或直接运行脚本
   python scripts/seed_products.py --seed-db
   ```

## 待添加的配置文件

以下配置文件将在后续任务中创建：

- `insurance_terminology.json` - 保险术语词典
- `risk_questionnaire.json` - 风险评估问卷
- `product_matching_rules.json` - 产品匹配规则
- `compliance_rules.json` - 合规规则

## 数据更新

如需更新种子数据：

1. 修改 `scripts/seed_products.py` 中的产品模板
2. 重新生成JSON文件
3. 创建新的Alembic迁移脚本或手动更新数据库
