import pytest
import tempfile
import os
from pathlib import Path
from src.config import Config, load_config


def test_load_config_from_file():
    """测试从YAML文件加载配置"""
    config_content = """
llm:
  base_url: http://localhost:11434/v1
  api_key: test-key
  model: llama3
  temperature: 0.5

output:
  format: markdown
  path: ./output/
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config.llm.base_url == "http://localhost:11434/v1"
        assert config.llm.api_key == "test-key"
        assert config.llm.model == "llama3"
        assert config.llm.temperature == 0.5
        assert config.output.format == "markdown"
        assert config.output.path == "./output/"
    finally:
        os.unlink(config_path)


def test_config_with_env_override(monkeypatch):
    """测试环境变量覆盖配置"""
    monkeypatch.setenv("LLM_API_KEY", "env-api-key")

    config_content = """
llm:
  base_url: http://localhost:11434/v1
  api_key: ${LLM_API_KEY}
  model: llama3
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config.llm.api_key == "env-api-key"
    finally:
        os.unlink(config_path)


def test_default_values():
    """测试默认值"""
    config_content = """
llm:
  model: test-model
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config.llm.base_url == "http://localhost:11434/v1"
        assert config.llm.temperature == 0.7
        assert config.features.chinese_notes == True
        assert config.chunker.target_tokens == 1500
    finally:
        os.unlink(config_path)
