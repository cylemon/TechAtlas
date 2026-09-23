import json
import logging
import time
from collections.abc import AsyncGenerator

from fastapi import HTTPException, status
from prompts import load_atlas_system_prompt
from pydantic import ValidationError
from schemas.atlas import AtlasEdge, AtlasNode, AtlasResponse

from services.llm.base import BaseLLMService, LLMTruncatedError, LLMUpstreamError

logger = logging.getLogger(__name__)

# 图谱是长文本任务，必须给足输出预算，否则 JSON 会被中途截断
_MAX_TOKENS = 4000
# 低温度让 JSON 结构更稳定
_TEMPERATURE = 0.2
# 进度事件的推送间隔，避免逐 token 刷屏
_PROGRESS_INTERVAL_MS = 300
# prompt 固定了顶层字段的书写顺序，据此判断模型当前写到哪一段
_SECTION_KEYS = ("topic", "summary", "nodes", "edges", "cross_domain_ideas")


def _detect_section(partial: str) -> str | None:
    """部分 JSON 中最后出现的顶层 key，即模型当前正在书写的字段"""
    latest_key, latest_pos = None, -1
    for key in _SECTION_KEYS:
        pos = partial.rfind(f'"{key}"')
        if pos > latest_pos:
            latest_key, latest_pos = key, pos
    return latest_key


def _drain_objects(buffer: str, cursor: int) -> tuple[list[dict], int]:
    """
    从 cursor 位置起，取出 buffer 中所有已经完整的 JSON 对象。

    用标准库的 raw_decode 逐段试解析，而不是手写括号计数——它背后是真正的
    JSON 解析器，能正确处理字符串内的花括号与转义（描述里出现一个 `}` 就会
    让手写的计数器崩掉）。解析失败即意味着"从这里开始还不完整"，把游标停在
    原处，等下一片数据到达再试。

    前提：最外层对象的花括号已被跳过（见 generate_stream 里 scan 的初始化）。
    prompt 固定了字段顺序，nodes/edges 又都是扁平对象，所以此后的每个 `{`
    必定对应一个节点或一条边。
    """
    decoder = json.JSONDecoder()
    found: list[dict] = []
    pos = cursor

    while True:
        start = buffer.find("{", pos)
        if start == -1:
            return found, pos

        try:
            obj, end = decoder.raw_decode(buffer, start)
        except json.JSONDecodeError:
            return found, start  # 从这里起还不完整，下次再来

        if isinstance(obj, dict):
            found.append(obj)
        pos = end


def _to_incremental_event(obj: dict, known_node_ids: set[str]) -> dict | None:
    """
    把一个刚解析完整的对象转成 node / edge 事件；不合规或尚不可渲染的返回 None。

    这里对每个节点单独走一遍 Pydantic 校验，是为了不破坏既有约定：
    前端只接触已验证的数据（category 枚举、relation 蛇形约束）。
    """
    if "id" in obj:
        try:
            node = AtlasNode(**obj)
        except ValidationError:
            return None
        known_node_ids.add(node.id)
        return {"type": "node", "node": node.model_dump()}

    if "source" in obj and "target" in obj:
        try:
            edge = AtlasEdge(**obj)
        except ValidationError:
            return None
        # 与最终结果里的悬空边剪除保持一致：两端节点都还没出现过就跳过
        if edge.source not in known_node_ids or edge.target not in known_node_ids:
            return None
        return {"type": "edge", "edge": edge.model_dump()}

    return None


def _build_user_prompt(query: str) -> str:
    return f"请为技术课题『{query}』生成完整的技术全景逻辑框架图谱。"


def _strip_code_fences(raw: str) -> str:
    """兜底剥掉 Markdown 代码围栏（开启 JSON 模式后本不应出现）"""
    text = raw.strip()
    if text.startswith("```json"):
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif text.startswith("```"):
        text = text.split("```", 1)[1].split("```", 1)[0]
    return text.strip()


def _prune_dangling_edges(atlas: AtlasResponse) -> AtlasResponse:
    """丢弃指向不存在节点的边，避免前端图库因悬空边渲染失败"""
    node_ids = {node.id for node in atlas.nodes}
    atlas.edges = [
        edge
        for edge in atlas.edges
        if edge.source in node_ids and edge.target in node_ids
    ]
    return atlas


def _parse_atlas(raw_content: str) -> AtlasResponse:
    """把 LLM 返回的文本解析并校验为图谱；任何失败都抛 502"""
    if not raw_content or not raw_content.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM 返回了空内容，无法解析图谱",
        )

    try:
        raw_json = json.loads(_strip_code_fences(raw_content))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM 返回的内容不是合法 JSON: {e}",
        ) from e

    try:
        atlas = AtlasResponse(**raw_json)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM 返回的图谱结构不符合约定: {e}",
        ) from e

    return _prune_dangling_edges(atlas)


async def generate(query: str, llm_service: BaseLLMService) -> AtlasResponse:
    """非流式：一次调用拿回完整图谱"""
    started = time.monotonic()

    try:
        response = await llm_service.generate(
            prompt=_build_user_prompt(query),
            system_prompt=load_atlas_system_prompt(),
            temperature=_TEMPERATURE,
            json_mode=True,
            max_tokens=_MAX_TOKENS,
        )
    except LLMTruncatedError as e:
        logger.warning("图谱生成被截断 query=%r: %s", query, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"图谱内容超出模型输出上限被截断: {e}",
        ) from e
    except LLMUpstreamError as e:
        logger.warning("上游模型服务报错 query=%r: %s", query, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"上游模型服务报错: {e}",
        ) from e
    except Exception as e:
        logger.exception("图谱生成失败 query=%r", query)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM 调用失败: {e}",
        ) from e

    try:
        atlas = _parse_atlas(response.content)
    except HTTPException as e:
        logger.warning("图谱解析失败 query=%r: %s", query, e.detail)
        raise

    logger.info(
        "图谱生成完成 query=%r model=%s nodes=%d edges=%d 耗时=%.2fs",
        query,
        response.model_name,
        len(atlas.nodes),
        len(atlas.edges),
        time.monotonic() - started,
    )
    return atlas


async def generate_stream(
    query: str, llm_service: BaseLLMService
) -> AsyncGenerator[dict, None]:
    """
    流式生成图谱，以事件字典的形式产出进度，由路由层封装为 SSE 帧。

    事件类型：
      {"type": "stage",    "stage": str, "label": str}
      {"type": "progress", "section": str | None, "received_chars": int, "elapsed_ms": int}
      {"type": "node",     "node": dict}
      {"type": "edge",     "edge": dict}
      {"type": "result",   "atlas": dict, "elapsed_ms": int}
      {"type": "error",    "detail": str}

    node / edge 是**增量**事件：模型每写完一个节点就立刻推送，前端因此可以边生成
    边画图，而不必等到最后。它们已经逐个通过 Pydantic 校验，前端拿到的仍是
    已验证的数据；最后那条 result 仍然会发，供前端做最终校准。

    进度只报事实（已接收字符数、已耗时、模型当前在写哪一段），不报百分比——
    最终 JSON 有多大事先不可知，任何百分比都是猜测。
    错误统一用 detail 字段，与 HTTP 错误响应体保持一致，前端只需认一个字段名。
    """
    started = time.monotonic()
    buffer = ""
    received = 0
    last_emit_ms = 0
    # 增量提取的游标与已知节点集合
    scan_cursor = 0
    scan_started = False
    known_node_ids: set[str] = set()

    def elapsed_ms() -> int:
        return int((time.monotonic() - started) * 1000)

    yield {"type": "stage", "stage": "generating", "label": "正在生成图谱"}

    try:
        async for delta in llm_service.generate_stream(
            prompt=_build_user_prompt(query),
            system_prompt=load_atlas_system_prompt(),
            temperature=_TEMPERATURE,
            json_mode=True,
            max_tokens=_MAX_TOKENS,
        ):
            buffer += delta
            received += len(delta)

            # 跳过最外层对象的花括号：它要等整份 JSON 写完才能解析成功，
            # 若从它开始扫描，游标会永远卡在 0，后面的节点一个也取不出来。
            if not scan_started:
                outer = buffer.find("{")
                if outer != -1:
                    scan_cursor = outer + 1
                    scan_started = True

            if scan_started:
                objects, scan_cursor = _drain_objects(buffer, scan_cursor)
                for obj in objects:
                    event = _to_incremental_event(obj, known_node_ids)
                    if event is not None:
                        yield event

            now_ms = elapsed_ms()
            if now_ms - last_emit_ms >= _PROGRESS_INTERVAL_MS:
                last_emit_ms = now_ms
                yield {
                    "type": "progress",
                    "section": _detect_section(buffer),
                    "received_chars": received,
                    "elapsed_ms": now_ms,
                }
    except LLMTruncatedError as e:
        logger.warning("图谱生成被截断 query=%r: %s", query, e)
        yield {"type": "error", "detail": f"图谱内容超出模型输出上限被截断: {e}"}
        return
    except LLMUpstreamError as e:
        logger.warning("上游模型服务报错 query=%r: %s", query, e)
        yield {"type": "error", "detail": f"上游模型服务报错: {e}"}
        return
    except Exception as e:
        logger.exception("流式图谱生成失败 query=%r", query)
        yield {"type": "error", "detail": f"LLM 调用失败: {e}"}
        return

    yield {"type": "stage", "stage": "parsing", "label": "正在解析并校验图谱"}

    try:
        atlas = _parse_atlas(buffer)
    except HTTPException as e:
        logger.warning("图谱解析失败 query=%r: %s", query, e.detail)
        yield {"type": "error", "detail": str(e.detail)}
        return

    logger.info(
        "图谱流式生成完成 query=%r nodes=%d edges=%d 耗时=%.2fs",
        query,
        len(atlas.nodes),
        len(atlas.edges),
        time.monotonic() - started,
    )
    yield {
        "type": "result",
        "atlas": atlas.model_dump(),
        "elapsed_ms": elapsed_ms(),
    }
