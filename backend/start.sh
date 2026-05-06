#!/bin/bash

# 1. 根據 lqsusersguide2025.2.0.pdf 第 2.2 節，載入 LQS 配置
if [ -f /etc/lqs.conf ]; then
    . /etc/lqs.conf
    echo "LQS configuration sourced successfully."
else
    echo "Warning: /etc/lqs.conf not found. Ensure LQS is installed correctly."
fi

# 2. 自動偵測 Windows 主機 IP 並設定 OLLAMA_HOST
# 在 WSL2 中，Windows 主機的 IP 通常是 nameserver 的位址
WINDOWS_HOST_IP=$(grep nameserver /etc/resolv.conf | awk '{print $2}')
export OLLAMA_HOST="http://${WINDOWS_HOST_IP}:11434"
echo "Detected Windows Host IP: ${WINDOWS_HOST_IP}, setting OLLAMA_HOST=${OLLAMA_HOST}"

# 3. 啟動虛擬環境 (如果存在 Linux 版本的 venv)
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "Virtual environment activated."
fi

# 4. 設定專案路徑並啟動後端程式
# 確保在專案根目錄執行此腳本
export PYTHONPATH=$PYTHONPATH:.
echo "Starting Altair Knowledge Hub API on Linux..."
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000