@echo off
rem 启动法律智能问答系统后端（需先启动 Neo4j）
rem 启动后浏览器打开 http://127.0.0.1:5000
cd /d %~dp0\..
set NEO4J_URI=bolt://localhost:7687
set NEO4J_USER=neo4j
set NEO4J_PASSWORD=legal-qa-2025
.venv\Scripts\python.exe -m app.main
