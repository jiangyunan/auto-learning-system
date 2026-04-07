"""翻译工具模块"""

from langdetect import detect, LangDetectException

from src.llm import LLMClient


def detect_language(text: str) -> str:
    """检测文本语言

    Args:
        text: 待检测文本

    Returns:
        语言代码，如 'zh-cn', 'en', 'ja' 等
    """
    try:
        return detect(text[:1000])
    except LangDetectException:
        return "unknown"


def is_chinese(text: str) -> bool:
    """判断文本是否为中文"""
    lang = detect_language(text)
    return lang in ("zh-cn", "zh-tw", "zh")


async def translate_to_chinese(llm: LLMClient, content: str) -> str:
    """将内容翻译为中文

    Args:
        llm: LLM客户端
        content: 原文内容

    Returns:
        中文翻译结果
    """
    response = await llm.complete(
        prompt=f"将以下内容翻译为中文，保持 Markdown 格式不变：\n\n{content}",
        system_prompt="你是专业的翻译助手，请准确翻译并保持原有格式。",
    )
    return response.content


def format_bilingual(original: str, translated: str) -> str:
    """将原文和译文格式化为段落对照格式

    Args:
        original: 原文
        translated: 译文

    Returns:
        段落对照格式的文本
    """
    orig_blocks = _split_into_blocks(original)
    trans_blocks = _split_into_blocks(translated)

    result = []
    for i, (orig, trans) in enumerate(zip(orig_blocks, trans_blocks)):
        orig_stripped = orig.strip()
        trans_stripped = trans.strip()

        if not orig_stripped and not trans_stripped:
            continue

        result.append(trans_stripped)
        if orig_stripped:
            result.append("")
            result.append(f"> {orig_stripped}")
        result.append("")

    return "\n".join(result).strip()


def _split_into_blocks(text: str) -> list[str]:
    """将文本分割成块（优先按段落，其次按行）"""
    if not text:
        return []

    paras = text.split("\n\n")
    if len(paras) > 1:
        return paras

    lines = text.split("\n")
    if len(lines) > 1:
        return lines

    return [text]
