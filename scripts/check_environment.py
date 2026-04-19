"""
环境检查脚本
验证所有依赖是否正确安装
"""
import sys


def check_imports():
    """检查核心依赖是否可以导入"""
    required_packages = [
        ("langgraph", "LangGraph"),
        ("langchain", "LangChain"),
        ("fastapi", "FastAPI"),
        ("pydantic", "Pydantic"),
        ("psycopg2", "PostgreSQL Driver"),
        ("redis", "Redis"),
        ("faiss", "FAISS"),
        ("hypothesis", "Hypothesis"),
        ("pytest", "Pytest"),
        ("sqlalchemy", "SQLAlchemy"),
        ("alembic", "Alembic"),
    ]
    
    print("检查依赖包...")
    print("-" * 60)
    
    all_ok = True
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"✓ {name:30s} - 已安装")
        except ImportError as e:
            print(f"✗ {name:30s} - 未安装: {e}")
            all_ok = False
    
    print("-" * 60)
    
    if all_ok:
        print("\n✓ 所有依赖包已正确安装！")
        return 0
    else:
        print("\n✗ 部分依赖包未安装，请运行: uv sync")
        return 1


def check_python_version():
    """检查Python版本"""
    print(f"\nPython版本: {sys.version}")
    
    if sys.version_info < (3, 11):
        print("✗ Python版本过低，需要3.11或更高版本")
        return 1
    else:
        print("✓ Python版本符合要求")
        return 0


def check_directory_structure():
    """检查目录结构"""
    import os
    
    required_dirs = [
        "agents",
        "skills",
        "tools",
        "api",
        "models",
        "utils",
        "tests",
        "data",
        "logs",
        "scripts",
        "alembic",
    ]
    
    print("\n检查目录结构...")
    print("-" * 60)
    
    all_ok = True
    for dir_name in required_dirs:
        if os.path.isdir(dir_name):
            print(f"✓ {dir_name:30s} - 存在")
        else:
            print(f"✗ {dir_name:30s} - 不存在")
            all_ok = False
    
    print("-" * 60)
    
    if all_ok:
        print("\n✓ 目录结构完整！")
        return 0
    else:
        print("\n✗ 部分目录缺失")
        return 1


def main():
    """主函数"""
    print("=" * 60)
    print("保险智能推荐Agent系统 - 环境检查")
    print("=" * 60)
    
    exit_code = 0
    
    # 检查Python版本
    exit_code |= check_python_version()
    
    # 检查目录结构
    exit_code |= check_directory_structure()
    
    # 检查依赖包
    exit_code |= check_imports()
    
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("✓ 环境检查通过！可以开始开发。")
    else:
        print("✗ 环境检查失败，请修复上述问题。")
    print("=" * 60)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
