# TechAtlas 前端

输入一个技术课题，实时看到生成进度，最终得到一张可交互的技术结构图谱。

## 开发

**后端必须先跑起来**（前端通过代理访问它）：

```bash
# 终端 1
cd backend && uv run uvicorn main:app --reload

# 终端 2
cd frontend && npm install && npm run dev
```

打开 <http://localhost:5173>。

后端地址默认 `http://127.0.0.1:8000`，需要时用环境变量覆盖：

```bash
VITE_BACKEND_URL=http://192.168.1.10:8000 npm run dev
```

> 开发时 `/api` 由 Vite 代理转发到后端，前端视角下是**同源请求**，因此完全不涉及
> CORS，也不必去改后端的 `CORS_ALLOW_ORIGINS`。

其他命令：

```bash
npm run build     # 类型检查 + 生产构建
npm run lint
```

## 结构

```
src/
├── api/
│   ├── client.ts       错误归一化（后端错误统一是 {"detail": "..."}）
│   └── atlas.ts        SSE 消费：fetch + ReadableStream
├── hooks/
│   └── useAtlasStream  把事件流变成 React state
├── components/
│   ├── TopicForm           课题输入 + 厂商选择
│   ├── GenerationProgress  阶段与进度展示
│   ├── AtlasGraph          React Flow 画布 + dagre 自动布局
│   └── AtlasNodeCard       自定义节点卡片
├── lib/
│   └── categoryTheme       category → 颜色/中文标签（唯一真源）
└── types/
    ├── atlas.ts            图谱契约（对应 backend/schemas/atlas.py）
    └── stream.ts           SSE 事件契约（必须手写，见下）
```

## 与后端的契约

### 类型来源

`types/atlas.ts` 镜像后端 schema，可以改成从 `/openapi.json` 生成以免漂移（尚未做）。

**但 `types/stream.ts` 必须手写**——SSE 对 OpenAPI 是不透明的，接口文档描述不出来。
这两类类型要分清边界，别指望一个命令解决。

### SSE 的四条约定

1. **开流之后 HTTP 状态码恒为 200**，成败只能看事件帧，不能看 `response.ok`；
2. 终止事件是 `result` 或 `error`，二选一；
3. 只有 `result` / `error` 是终止事件，`stage` / `progress` 仅表示进度；
4. **若流关闭却没收到任何终止事件，说明连接被中途掐断**，必须当作失败处理
   （`useAtlasStream` 已覆盖这一条，这是 SSE 最容易漏掉的失败模式）。

开流**之前**的错误（鉴权失败、参数校验、provider 未注册）仍是真实状态码，
由 `api/atlas.ts` 抛成异常。

### 为什么不用 EventSource

`EventSource` 只支持 GET、不能携带请求体，而生成接口是 `POST` + JSON body。
所以只能用 `fetch` + `ReadableStream` 手动解析 SSE 帧。

## 一些实现上的取舍

- **用 `type` 而非 `interface` 声明图谱类型**：React Flow 要求节点 `data` 满足
  `Record<string, unknown>`，而 TypeScript 只给类型字面量隐式索引签名。
  改成 `interface` 会编译报错。
- **用 dagre 做布局**：图谱里存在 `alternative_to`、`influences` 这类关系，
  必然有环，自己写分层算法会在环上失效。
- **`categoryTheme.ts` 用 `Record<Category, …>`**：后端新增分类时会在编译期报缺项，
  而不是让某个节点渲染成无色。
- **进度不显示百分比**：最终 JSON 有多大事先不可知，前端只展示后端给出的客观计数
  （已接收字符数、耗时、正在生成哪一段）。

## 当前状态

MVP：课题输入 → 实时进度 → 可拖拽的图谱。

尚未做：图谱的持久化与历史版本、多视图切换（时间轴/矩阵）、「本次新增」高亮
（取决于后端的增量演进能力）。
