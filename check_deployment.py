#!/usr/bin/env python3
"""
部署前检查脚本
验证所有必需的文件和配置是否正确
"""

import os
import sys
import json
import importlib.util
from pathlib import Path

def print_status(message, status="INFO"):
    """打印状态消息"""
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m", 
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m"
    }
    reset = "\033[0m"
    print(f"{colors.get(status, '')}[{status}]{reset} {message}")

def check_required_files():
    """检查必需文件是否存在"""
    print_status("检查必需文件...")
    
    required_files = [
        "bot.py",
        "auto_sync_outline.py", 
        "requirements.txt",
        "role_mapping.json",
        ".env",
        "credentials.json"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print_status(f"缺少以下必需文件: {', '.join(missing_files)}", "ERROR")
        return False
    
    print_status("所有必需文件都存在", "SUCCESS")
    return True

def check_env_file():
    """检查 .env 文件配置"""
    print_status("检查环境变量配置...")
    
    if not os.path.exists(".env"):
        print_status(".env 文件不存在", "ERROR")
        return False
    
    # 读取 .env 文件
    env_vars = {}
    try:
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except Exception as e:
        print_status(f"读取 .env 文件失败: {e}", "ERROR")
        return False
    
    # 检查必需的环境变量
    required_vars = [
        "DISCORD_TOKEN",
        "GOOGLE_SHEETS_ID", 
        "WORKSHEET_NAME",
        "OUTLINE_API_URL",
        "OUTLINE_API_TOKEN"
    ]
    
    missing_vars = []
    for var in required_vars:
        if var not in env_vars or not env_vars[var]:
            missing_vars.append(var)
    
    if missing_vars:
        print_status(f"缺少以下环境变量: {', '.join(missing_vars)}", "ERROR")
        return False
    
    print_status("环境变量配置正确", "SUCCESS")
    return True

def check_role_mapping():
    """检查角色映射文件"""
    print_status("检查角色映射配置...")
    
    try:
        with open("role_mapping.json", "r", encoding="utf-8") as f:
            mapping = json.load(f)
        
        if not isinstance(mapping, dict):
            print_status("role_mapping.json 格式错误，应为对象", "ERROR")
            return False
        
        if not mapping:
            print_status("role_mapping.json 为空", "WARNING")
        else:
            print_status(f"找到 {len(mapping)} 个角色映射", "SUCCESS")
        
        return True
    except json.JSONDecodeError as e:
        print_status(f"role_mapping.json JSON 格式错误: {e}", "ERROR")
        return False
    except Exception as e:
        print_status(f"读取 role_mapping.json 失败: {e}", "ERROR")
        return False

def check_credentials():
    """检查 Google 凭证文件"""
    print_status("检查 Google 凭证文件...")
    
    try:
        with open("credentials.json", "r") as f:
            creds = json.load(f)
        
        # 检查基本结构
        if "type" not in creds:
            print_status("credentials.json 缺少 type 字段", "ERROR")
            return False
        
        if creds.get("type") != "service_account":
            print_status("credentials.json 应为 service_account 类型", "ERROR")
            return False
        
        required_fields = ["project_id", "private_key_id", "private_key", "client_email"]
        missing_fields = [field for field in required_fields if field not in creds]
        
        if missing_fields:
            print_status(f"credentials.json 缺少字段: {', '.join(missing_fields)}", "ERROR")
            return False
        
        print_status("Google 凭证文件格式正确", "SUCCESS")
        return True
    except json.JSONDecodeError as e:
        print_status(f"credentials.json JSON 格式错误: {e}", "ERROR")
        return False
    except Exception as e:
        print_status(f"读取 credentials.json 失败: {e}", "ERROR")
        return False

def check_python_syntax():
    """检查 Python 文件语法"""
    print_status("检查 Python 文件语法...")
    
    python_files = ["bot.py", "auto_sync_outline.py"]
    
    for file in python_files:
        try:
            spec = importlib.util.spec_from_file_location("module", file)
            if spec is None:
                print_status(f"{file} 无法加载", "ERROR")
                return False
            
            # 尝试编译文件
            with open(file, 'r', encoding='utf-8') as f:
                compile(f.read(), file, 'exec')
            
            print_status(f"{file} 语法检查通过", "SUCCESS")
        except SyntaxError as e:
            print_status(f"{file} 语法错误: {e}", "ERROR")
            return False
        except Exception as e:
            print_status(f"检查 {file} 时出错: {e}", "ERROR")
            return False
    
    return True

def check_requirements():
    """检查依赖文件"""
    print_status("检查依赖文件...")
    
    try:
        with open("requirements.txt", "r") as f:
            requirements = f.read().strip()
        
        if not requirements:
            print_status("requirements.txt 为空", "WARNING")
            return True
        
        lines = [line.strip() for line in requirements.split('\n') if line.strip()]
        print_status(f"找到 {len(lines)} 个依赖包", "SUCCESS")
        
        # 检查关键依赖
        key_packages = ["discord.py", "aiohttp", "gspread", "python-dotenv"]
        found_packages = []
        
        for line in lines:
            package_name = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
            if package_name in key_packages:
                found_packages.append(package_name)
        
        missing_packages = [pkg for pkg in key_packages if pkg not in found_packages]
        if missing_packages:
            print_status(f"可能缺少关键依赖: {', '.join(missing_packages)}", "WARNING")
        
        return True
    except Exception as e:
        print_status(f"读取 requirements.txt 失败: {e}", "ERROR")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("    Discord Bot 部署前检查")
    print("=" * 50)
    print()
    
    checks = [
        ("文件检查", check_required_files),
        ("环境变量检查", check_env_file),
        ("角色映射检查", check_role_mapping),
        ("Google 凭证检查", check_credentials),
        ("Python 语法检查", check_python_syntax),
        ("依赖文件检查", check_requirements)
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        print(f"\n--- {check_name} ---")
        if not check_func():
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print_status("🎉 所有检查都通过！可以开始部署", "SUCCESS")
        print_status("运行部署脚本: chmod +x deploy.sh && ./deploy.sh", "INFO")
    else:
        print_status("❌ 部分检查未通过，请修复后再部署", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()