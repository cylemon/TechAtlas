from functools import lru_cache
from pathlib import Path

# 获取 prompts 目录的绝对路径
PROMPTS_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=16)
def load_prompt(filename: str) -> str:
    """读取指定 Prompt 文件内容（带 LRU 缓存）"""
    file_path = PROMPTS_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt 模板文件未找到: {file_path}")

    return file_path.read_text(encoding="utf-8")


def load_atlas_system_prompt() -> str:
    """获取 TechAtlas Agent 的 System Prompt"""
    return load_prompt("atlas_system_prompt.md")
