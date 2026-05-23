"""
QMT Gateway 部署打包脚本

在本地 Mac 上运行，将更新后的文件打包为 zip，
然后通过 RDP 远程桌面复制到 Windows 服务器。

用法:
    cd /Users/apple/Desktop/ai_huahua/qmt_gateway
    python pack_deploy.py
"""

import os
import shutil
import zipfile
from datetime import datetime

QMT_GATEWAY_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_FILES = [
    "app.py",
    "miniqmt_trader.py",
    "run_server.py",
    "test_qmt_cloud_local.py",
    "requirements.txt",
]
OUTPUT_DIR = os.path.join(QMT_GATEWAY_DIR, "dist")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"qmt_gateway_deploy_{timestamp}.zip"
    zip_path = os.path.join(OUTPUT_DIR, zip_name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in DEPLOY_FILES:
            fpath = os.path.join(QMT_GATEWAY_DIR, fname)
            if os.path.exists(fpath):
                zf.write(fpath, fname)
                print(f"  已添加: {fname}")
            else:
                print(f"  警告: {fname} 不存在，跳过")

        deploy_script = os.path.join(QMT_GATEWAY_DIR, "deploy_on_windows.bat")
        if os.path.exists(deploy_script):
            zf.write(deploy_script, "deploy_on_windows.bat")
            print(f"  已添加: deploy_on_windows.bat")

    size_kb = os.path.getsize(zip_path) / 1024
    print()
    print(f"打包完成: {zip_path}")
    print(f"文件大小: {size_kb:.1f} KB")
    print()
    print("下一步操作:")
    print("  1. 通过 RDP 远程桌面连接到腾讯云 Windows 服务器")
    print(f"  2. 将 {zip_name} 复制到服务器桌面或任意目录")
    print("  3. 解压 zip 文件")
    print("  4. 右键以管理员身份运行 deploy_on_windows.bat")
    print("  脚本将自动完成: 停止服务 -> 备份 -> 部署 -> 启动 -> 测试")


if __name__ == "__main__":
    main()
