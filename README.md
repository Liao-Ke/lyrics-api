# 歌词API

基于 1647 首华语流行乐 LRC 歌词的半开放查询 API，支持元数据搜索、歌词全文检索、卡拉OK 时间轴定位。

数据来源：`lrc/` 目录下 1647 个 `.lrc` 文件，经 `clean_lrc.py` 清洗为结构化 JSON 后导入 sqlite。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 导入歌词数据（首次运行）
python scripts/import_songs.py

# 启动服务
python -m app.main

# 访问 Swagger 文档
open http://localhost:8000/docs
```

## 容器部署

```bash
podman compose up -d
```

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 健康检查 |
| GET | `/api/v1/songs` | 歌曲列表，分页 + 过滤（?title= & ?artist= & ?writer=） |
| GET | `/api/v1/songs/{id}` | 单首元数据 + 歌词全文 |
| GET | `/api/v1/search?q=` | 统一搜索（标题 / 艺术家 / 作词人 / 歌词正文） |
| GET | `/api/v1/songs/{id}/lyrics?time=xx.xx` | 卡拉OK 模式，当前时间点附近的行 |

## 技术栈

- **框架**：FastAPI + Pydantic
- **数据库**：SQLite3（FTS5 trigram 全文索引）
- **配置**：pydantic-settings + .env
- **日志**：loguru
- **部署**：Podman 容器 / 裸跑

## 开发

```bash
# 运行测试
pytest --cov --cov-fail-under=80

# 代码检查
ruff check .
```

## 文档

- [产品需求](docs/prd/)
- [架构设计](docs/arch/)
- [接口文档](docs/api/)（Swagger UI 同步）
- [数据库设计](docs/db/)
- [部署方案](docs/deploy/)