"""LLM客户端测试"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json

from src.llm import LLMClient, create_client, LLMResponse
from src.config import LLMConfig


@pytest.fixture
def mock_config():
    return LLMConfig(
        base_url="http://localhost:11434/v1",
        api_key="test-key",
        model="llama3",
        temperature=0.7,
    )


@pytest.fixture
def mock_openai_response():
    """模拟OpenAI响应"""
    mock = Mock()
    mock.choices = [Mock()]
    mock.choices[0].message.content = "Test response"
    mock.usage = Mock()
    mock.usage.model_dump.return_value = {"prompt_tokens": 10, "completion_tokens": 5}
    mock.model = "llama3"
    return mock


@pytest.mark.asyncio
async def test_complete_basic(mock_config, mock_openai_response):
    """测试基本的完成请求"""
    client = LLMClient(mock_config)

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_openai_response

        response = await client.complete("Hello")

        assert response.content == "Test response"
        assert response.model == "llama3"
        assert response.usage["prompt_tokens"] == 10

        # 验证调用参数
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args.kwargs["model"] == "llama3"
        assert call_args.kwargs["temperature"] == 0.7
        assert len(call_args.kwargs["messages"]) == 1
        assert call_args.kwargs["messages"][0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_complete_with_system_prompt(mock_config, mock_openai_response):
    """测试带系统提示的完成请求"""
    client = LLMClient(mock_config)

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_openai_response

        await client.complete("Hello", system_prompt="You are helpful")

        call_args = mock_create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful"
        assert messages[1]["role"] == "user"


@pytest.mark.asyncio
async def test_complete_with_custom_temperature(mock_config, mock_openai_response):
    """测试自定义temperature"""
    client = LLMClient(mock_config)

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_openai_response

        await client.complete("Hello", temperature=0.5)

        call_args = mock_create.call_args
        assert call_args.kwargs["temperature"] == 0.5


@pytest.mark.asyncio
async def test_stream(mock_config):
    """测试流式请求"""
    client = LLMClient(mock_config)

    # 模拟流式响应
    async def mock_stream():
        chunks = [
            Mock(choices=[Mock(delta=Mock(content="Hello "))]),
            Mock(choices=[Mock(delta=Mock(content="world"))]),
            Mock(choices=[Mock(delta=Mock(content=""))]),
        ]
        for chunk in chunks:
            yield chunk

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()

        result = ""
        async for chunk in client.stream("Hello"):
            result += chunk

        assert result == "Hello world"


@pytest.mark.asyncio
async def test_complete_json(mock_config):
    """测试JSON格式请求"""
    client = LLMClient(mock_config)

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '{"key": "value", "number": 42}'

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response

        result = await client.complete_json("Extract data")

        assert result == {"key": "value", "number": 42}

        # 验证使用了json_object响应格式
        call_args = mock_create.call_args
        assert call_args.kwargs["response_format"]["type"] == "json_object"


@pytest.mark.asyncio
async def test_complete_json_with_schema(mock_config):
    """测试带schema的JSON请求"""
    client = LLMClient(mock_config)

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '{"name": "test"}'

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response

        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        await client.complete_json("Extract", schema=schema)

        # 验证schema被添加到系统提示
        call_args = mock_create.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "JSON" in messages[0]["content"]
        assert json.dumps(schema) in messages[0]["content"]


@pytest.mark.asyncio
async def test_health_check_success(mock_config):
    """测试健康检查成功"""
    client = LLMClient(mock_config)

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "hi"

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response

        result = await client.health_check()
        assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(mock_config):
    """测试健康检查失败"""
    client = LLMClient(mock_config)

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = Exception("Connection error")

        result = await client.health_check()
        assert result is False


def test_create_client_factory(mock_config):
    """测试工厂函数"""
    client = create_client(mock_config)
    assert isinstance(client, LLMClient)
    assert client.config == mock_config
