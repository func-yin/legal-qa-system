# Neo4j 部署指南

项目支持两种 Neo4j 部署方式，任选其一即可。

## 方式 A：Neo4j AuraDB 云端免费实例（推荐，5 分钟）

1. 打开 <https://console.neo4j.io/>，用邮箱或 Google 账号注册
2. 创建 **AuraDB Free** 实例（免费版，无需信用卡）
3. 创建成功后会显示并让你保存三样东西：
   - `Connection URI`（形如 `neo4j+s://xxxx.databases.neo4j.io`）
   - 用户名（默认 `neo4j`）
   - 密码（只显示一次，务必保存；丢失可在实例页重置）
4. 在项目根目录设置环境变量后运行导入与启动命令：

```powershell
# Windows PowerShell
$env:NEO4J_URI="neo4j+s://xxxx.databases.neo4j.io"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="你的密码"

python knowledge_graph/import_neo4j.py
python -m app.main
```

## 方式 B：本地部署 Neo4j Community

1. 安装 JDK 17+（如 [Adoptium Temurin 21](https://mirrors.tuna.tsinghua.edu.cn/Adoptium/21/jdk/x64/windows/)）
2. 下载 [Neo4j Community Server](https://neo4j.com/download-center/) Windows zip 并解压
   （官网对部分地区有访问限制，必要时需通过代理下载）
3. 设置环境变量 `JAVA_HOME` 指向 JDK 目录
4. 在 Neo4j 解压目录执行：`bin\neo4j.bat console`
5. 首次访问 <http://localhost:7474>，默认账号密码均为 `neo4j`，按提示修改密码
6. 设置环境变量并导入：

```powershell
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="你设置的密码"

python knowledge_graph/import_neo4j.py
python -m app.main
```

## 验证

导入成功后：

```bash
curl http://127.0.0.1:5000/api/health   # {"model":"ok","neo4j":"ok"}
curl http://127.0.0.1:5000/api/stats    # 查看图谱节点统计
```

预期节点规模：Crime 20 · Article 31 · Law 8 · Element 80 · FAQ 30 · Topic 6
