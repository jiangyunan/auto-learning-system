"""配置管理模块"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field

import yaml


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    model: str = "llama3"
    temperature: float = 0.7
    max_tokens: int = 4000  # LLM 输出最大 token 数，防止截断
    timeout: int = 300  # 请求超时时间（秒），本地模型处理慢需要较长时间


@dataclass
class OutputConfig:
    format: str = "obsidian"  # markdown | obsidian
    path: str = "./vault/"
    filename_template: str = "{title}.md"


@dataclass
class FeaturesConfig:
    chinese_notes: bool = True


@dataclass
class ChunkerConfig:
    target_tokens: int = 1500
    overlap_chars: int = 200


@dataclass
class CacheConfig:
    enabled: bool = True
    db_path: str = "./data/cache.db"


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    chunker: ChunkerConfig = field(default_factory=ChunkerConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)


def _expand_env_vars(value: str) -> str:
    """展开字符串中的环境变量 ${VAR} 或 $VAR"""
    pattern = re.compile(r"\$\{(\w+)\}|\$(\w+)")

    def replace_var(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, match.group(0))

    return pattern.sub(replace_var, value)


def _process_dict(data: dict) -> dict:
    """递归处理字典，展开所有字符串值中的环境变量"""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = _expand_env_vars(value)
        elif isinstance(value, dict):
            result[key] = _process_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _expand_env_vars(v) if isinstance(v, str) else v for v in value
            ]
        else:
            result[key] = value
    return result


def load_config(config_path: str = "config.yaml") -> Config:
    """从YAML文件加载配置"""
    path = Path(config_path)

    if not path.exists():
        # 使用默认配置
        return Config()

    with open(path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f) or {}

    # 展开环境变量
    data = _process_dict(raw_data)

    # 构建配置对象
    llm_data = data.get("llm", {})
    output_data = data.get("output", {})
    features_data = data.get("features", {})
    chunker_data = data.get("chunker", {})
    cache_data = data.get("cache", {})

    return Config(
        llm=LLMConfig(**llm_data),
        output=OutputConfig(**output_data),
        features=FeaturesConfig(**features_data),
        chunker=ChunkerConfig(**chunker_data),
        cache=CacheConfig(**cache_data),
    )
