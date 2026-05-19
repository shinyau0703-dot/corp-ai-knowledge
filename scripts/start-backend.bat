@echo off
cd /d D:\Sandy\KMsystem\corp-ai-knowledge
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8200
