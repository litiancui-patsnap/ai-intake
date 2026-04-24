"""配置加载工具"""

import os
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .logger import get_logger

logger = get_logger("utils.config")


class Config:
    """配置管理器"""

    def __init__(self, config_dir: str = None):
        """初始化配置管理器

        Args:
            config_dir: 配置文件目录路径，默认为项目根目录
        """
        if config_dir is None:
            # 默认配置目录为项目根目录
            self.config_dir = Path(__file__).parent.parent.parent
        else:
            self.config_dir = Path(config_dir)

        self.sources: List[Dict[str, Any]] = []
        self.topics: List[Dict[str, Any]] = []
        self.rules: Dict[str, Any] = {}

        self._load_all()

    def _load_yaml(self, filename: str) -> Any:
        """加载YAML文件

        Args:
            filename: 文件名

        Returns:
            解析后的YAML数据
        """
        filepath = self.config_dir / filename
        if not filepath.exists():
            logger.error(f"配置文件不存在: {filepath}")
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            logger.debug(f"已加载配置文件: {filename}")
            return data
        except Exception as e:
            logger.error(f"加载配置文件失败 {filename}: {e}")
            return None

    def _load_all(self):
        """加载所有配置文件"""
        # 加载sources.yaml
        sources_data = self._load_yaml("sources.yaml")
        if sources_data:
            # 展平所有分类
            for category, sources in sources_data.items():
                if isinstance(sources, list):
                    for source in sources:
                        source["category"] = category
                    self.sources.extend(sources)
            logger.info(f"已加载 {len(self.sources)} 个信息源")

        # 加载topics.yaml
        topics_data = self._load_yaml("topics.yaml")
        if topics_data:
            # 展平所有主题
            for category, topics in topics_data.items():
                if isinstance(topics, list):
                    for topic in topics:
                        topic["category"] = category
                    self.topics.extend(topics)
            logger.info(f"已加载 {len(self.topics)} 个主题")

        # 加载rules.yaml
        self.rules = self._load_yaml("rules.yaml") or {}
        logger.info("已加载评分与过滤规则")

    def get_enabled_sources(self) -> List[Dict[str, Any]]:
        """获取已启用的信息源

        Returns:
            已启用的信息源列表
        """
        return [s for s in self.sources if s.get("enabled", True)]

    def get_source_by_name(self, name: str) -> Dict[str, Any]:
        """根据名称获取信息源

        Args:
            name: 信息源名称

        Returns:
            信息源配置，如果不存在返回None
        """
        for source in self.sources:
            if source.get("name") == name:
                return source
        return None

    def get_topics_by_category(self, category: str) -> List[Dict[str, Any]]:
        """获取指定分类的主题

        Args:
            category: 分类名称

        Returns:
            主题列表
        """
        return [t for t in self.topics if t.get("category") == category]

    def get_scoring_config(self) -> Dict[str, Any]:
        """获取评分配置

        Returns:
            评分配置字典
        """
        return self.rules.get("scoring", {})

    def get_must_read_rules(self) -> List[Dict[str, str]]:
        """获取必读规则

        Returns:
            必读规则列表
        """
        return self.rules.get("must_read_rules", [])

    def get_filter_rules(self) -> List[Dict[str, str]]:
        """获取过滤规则

        Returns:
            过滤规则列表
        """
        return self.rules.get("filter_rules", [])

    def get_output_config(self, report_type: str = "daily") -> Dict[str, Any]:
        """获取输出配置

        Args:
            report_type: 报告类型 ('daily' 或 'weekly')

        Returns:
            输出配置字典
        """
        output = self.rules.get("output", {})
        report_config = dict(output.get(report_type, {}))
        markdown_config = output.get("markdown", {})
        if markdown_config:
            report_config["markdown"] = markdown_config
        return report_config

    def get_preferences(self) -> Dict[str, Any]:
        """获取个人偏好配置

        Returns:
            偏好配置字典
        """
        return self.rules.get("preferences", {})

    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置

        Returns:
            LLM配置字典
        """
        llm_config = dict(self.rules.get("llm", {}))

        env_provider = os.getenv("AI_INTAKE_LLM_PROVIDER")
        env_model = os.getenv("AI_INTAKE_LLM_MODEL")
        if env_provider:
            llm_config["provider"] = env_provider
        if env_model:
            llm_config["model"] = env_model

        provider = llm_config.get("provider")

        # 从环境变量读取API密钥 / 地址
        if provider in {"openai", "openai_compatible"}:
            if not llm_config.get("model"):
                openai_model = os.getenv("OPENAI_MODEL")
                if openai_model:
                    llm_config["model"] = openai_model
            llm_config["api_key"] = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL")
            temperature = os.getenv("OPENAI_TEMPERATURE")
            max_tokens = os.getenv("OPENAI_MODEL_TOKENS")
            if base_url:
                llm_config["base_url"] = base_url
            if temperature:
                llm_config["temperature"] = float(temperature)
            if max_tokens:
                llm_config["max_tokens"] = int(max_tokens)
        elif provider == "anthropic":
            llm_config["api_key"] = os.getenv("ANTHROPIC_API_KEY")
        elif provider == "ollama":
            llm_config["api_key"] = os.getenv("OLLAMA_API_KEY", "")
            base_url = os.getenv("OLLAMA_BASE_URL")
            model = os.getenv("OLLAMA_MODEL")
            temperature = os.getenv("OLLAMA_TEMPERATURE")
            max_tokens = os.getenv("OLLAMA_MODEL_TOKENS")
            if base_url:
                llm_config["base_url"] = base_url
            if model:
                llm_config["model"] = model
            if temperature:
                llm_config["temperature"] = float(temperature)
            if max_tokens:
                llm_config["max_tokens"] = int(max_tokens)
        return llm_config

    def get_dedup_config(self) -> Dict[str, Any]:
        """获取去重配置

        Returns:
            去重配置字典
        """
        return self.rules.get("dedup", {})

    def get_network_config(self) -> Dict[str, Any]:
        """获取网络配置

        Returns:
            网络配置字典
        """
        return self.rules.get("network", {})

    def get_locale_config(self) -> Dict[str, Any]:
        """获取时区与语言配置

        Returns:
            时区语言配置字典
        """
        return self.rules.get("locale", {})

    def get_notify_config(self) -> Dict[str, Any]:
        """获取通知配置

        Returns:
            通知配置字典
        """
        return self.rules.get("notify", {})
