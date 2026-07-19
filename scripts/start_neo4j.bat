@echo off
rem 启动本地 Neo4j（法律智能问答系统依赖）
rem 首次使用请先执行 bin\neo4j-admin.bat dbms set-initial-password legal-qa-2025
set JAVA_HOME=D:\AI\kimi\workfile\runtime\jdk\jdk-21.0.11+10
D:\AI\kimi\workfile\runtime\neo4j-community-5.26.3\bin\neo4j.bat console
