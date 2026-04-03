"""LLM客户端模块 - OpenAI兼容接口"""

import json
import re
from typing import AsyncIterator, Optional
from dataclasses import dataclass

from openai import AsyncOpenAI

from src.config import LLMConfig


def _extract_json_from_text(text: str) -> str:
    """从文本中提取 JSON，支持 markdown code block"""
    # 尝试匹配 ```json ... ``` 或 ``` ... ```
    pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    matches = re.findall(pattern, text)
    if matches:
        return matches[0].strip()
    # 尝试匹配第一个 {...}
    pattern = r"(\{[\s\S]*\})"
    matches = re.findall(pattern, text)
    if matches:
        return matches[0].strip()
    return text.strip()


@dataclass
class LLMResponse:
    """LLM响应"""

    content: str
    usage: Optional[dict] = None
    model: str = ""


class LLMClient:
    """OpenAI兼容的LLM客户端"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
        )

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """单次完成请求"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens,
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            usage=response.usage.model_dump() if response.usage else None,
            model=response.model,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """流式完成请求"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        schema: Optional[dict] = None,
        max_tokens: Optional[int] = None,
    ) -> dict:
        """请求JSON格式的响应"""
        messages = []

        # 添加系统提示，要求JSON输出
        json_system_prompt = system_prompt or ""
        if schema:
            json_system_prompt += f"\n\nYou must respond with valid JSON matching this schema: {json.dumps(schema)}"
        else:
            json_system_prompt += "\n\nYou must respond with valid JSON only."

        if json_system_prompt:
            messages.append({"role": "system", "content": json_system_prompt.strip()})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"

        # JSON解析容错：先尝试直接解析，失败则尝试提取markdown code block
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            extracted = _extract_json_from_text(content)
            return json.loads(extracted)

    async def health_check(self) -> bool:
        """检查LLM服务是否可用"""
        try:
            # 尝试列出模型或做一个简单的完成请求
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return response.choices[0].message.content is not None
        except Exception:
            return False


def create_client(config: LLMConfig) -> LLMClient:
    """工厂函数：创建LLM客户端"""
    return LLMClient(config)
