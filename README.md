# TechAtlas

An AI-driven, dynamically evolving technology mapping agent that automatically explores, organizes, and visualizes cutting-edge tech landscapes and emerging trends.

输入一个技术课题，返回一张结构化的技术全景图谱（节点 + 关系）。

---

## 快速开始

需要 Python ≥ 3.12 与 [uv](https://docs.uv.dev/)。

```bash
cd backend
cp .env.example .env          # 填入 DEEPSEEK_API_KEY
uv sync
uv run uvicorn main:app --reload
```

启动后：

- 交互式文档 <http://127.0.0.1:8000/docs>
- 就绪探针 <http://127.0.0.1:8000/ready>

> **必须从 `backend/` 目录启动**——代码以它为导入根。若要从仓库根目录启动，
> 用 `uv run uvicorn main:app --app-dir backend`。

### 跑测试

```bash
cd backend
uv run pytest -m "not live"   # 离线用例（推荐，默认跑法）
uv run pytest                 # 含 live 用例：会真实调用 DeepSeek 并计费
```

---

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 服务引导 |
| GET | `/health` | **存活探针**：只回答"进程还在不在"，不检查任何外部依赖 |
| GET | `/ready` | **就绪探针**：检查配置是否可用，配置不全返回 503 |
| GET | `/api/providers` | 已注册的 LLM 提供商，供前端渲染选择菜单 |
| POST | `/api/generate` | 生成图谱（一次性返回） |
| POST | `/api/generate/stream` | 生成图谱（SSE 流式推送进度） |

生成请求体：

```json
{ "query": "AI Agent 技术全景", "provider": "deepseek" }
```

单次生成实测约 5–6 秒。

### 流式接口的事件格式

```js
// 注意：必须用 fetch + ReadableStream，EventSource 不支持 POST
POST /api/generate/stream
  data: {"type":"stage",    "stage":"generating","label":"正在生成图谱"}
  data: {"type":"progress", "section":"nodes","received_chars":2205,"elapsed_ms":4437}
  data: {"type":"result",   "atlas":{...},"elapsed_ms":5968}
  data: {"type":"error",    "detail":"..."}
```

两条硬约定：

1. **开流之后 HTTP 状态码恒为 200**，成败只能看事件帧。鉴权失败、provider 未注册等都在开流**之前**返回真实状态码，所以 `!response.ok` 仍是有效的错误信号。
2. **进度不含百分比**——最终 JSON 有多大事先不可知，只报客观计数（已接收字符数、耗时、模型当前在写哪一段）。

---

## 环境变量

复制 `backend/.env.example` 后按需修改。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `API_TOKEN` | 空 | 生成接口的访问令牌。**留空表示关闭鉴权**，仅限本地开发 |
| `CORS_ALLOW_ORIGINS` | localhost:3000 / 5173 | 允许跨域的前端来源，逗号分隔 |
| `DEEPSEEK_API_KEY` | 空 | DeepSeek 密钥，**必填** |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名 |
| `DEEPSEEK_TIMEOUT` | `90` | 单次请求超时（秒） |

---

## 部署检查清单

上线前逐项确认：

- [ ] **设置 `API_TOKEN`**
      不设置则生成接口**完全开放**，任何调用方都会消耗你的额度。启动日志会打印告警，但告警很容易被忽略——请显式确认。
      客户端通过 `X-API-Key` 请求头携带令牌。

- [ ] **设置 `CORS_ALLOW_ORIGINS`**
      默认只放行 localhost。**前端域名不加进去，浏览器会直接拦掉请求**，且服务端日志看不出异常（CORS 是浏览器侧行为）。
      启动日志会打印生效的来源列表，前端连不上时先看这一行。

- [ ] **确认 `DEEPSEEK_API_KEY` 已配置**
      访问 `/ready`，应返回 200。若返回 503，`problems` 字段会指出具体缺什么。

- [ ] **探针接线正确**
      `/health` → 存活探针（进程挂了才重启）；`/ready` → 就绪探针（配置有问题就摘流量）。
      **不要把 `/ready` 接到存活探针上**——配置问题会导致一个本身健康的进程被反复重启。

- [ ] **从正确的工作目录启动**
      代码以 `backend/` 为导入根。用 `--app-dir backend` 或在 `backend/` 下启动。

### 部署后冒烟验证

```bash
BASE=https://your-host

curl -s $BASE/health                      # {"status":"ok"}
curl -s $BASE/ready                       # 200 且 problems 为空
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/api/generate \
  -H 'Content-Type: application/json' -d '{"query":"x","provider":"deepseek"}'
# 期望 401 —— 说明鉴权生效了。若返回 422 或 200，说明 API_TOKEN 没配上
```

---

## 项目结构

```
backend/
├── config.py              应用级配置（.env 路径锚定在此，与启动目录无关）
├── main.py                应用装配 + 系统路由
├── routers/               HTTP 层
├── schemas/               请求/响应契约
├── services/
│   ├── atlas.py           图谱领域逻辑（生成、解析、SSE 事件）
│   └── llm/               LLM 供应商基础设施
│       ├── base.py        抽象基类与统一响应结构
│       ├── factory.py     插件注册中心
│       └── deepseek.py    DeepSeek 适配器（唯一知道厂商参数的地方）
├── prompts/               提示词模板（外置为 .md，带 LRU 缓存）
└── tests/                 与源码文件一一对应
```

新增一个 LLM 厂商只需在 `services/llm/` 下加一个适配器文件，并在 `services/__init__.py` 中导入以触发注册。前端与后端公共代码均无需改动。

---

## 当前状态

后端已可作为 MVP 使用。**前端尚未接入**——`frontend/` 目前仍是 Vite 初始模板。

已知的后续工作：

- 图谱的持久化与增量演进（目前每次请求都重新生成，无缓存）
- 课题界限校验（原先的关键词方案已移除，计划交由专门的 agent 承担）
