"""
应用配置模块：从 .env 文件读取 LLM API 配置，提供类型安全的配置访问。

新手注意：
    .env 文件不应该提交到 Git——它包含你 API Key。
    本模块读取失败时会抛出 ConfigError，不会默默返回空值。
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """配置错误：缺少必要的环境变量或配置文件。

    和普通 Exception 的区别：调用方可以单独 catch ConfigError，
    从而区分「配置没写好」和「网络挂了」两类问题。
    """


@dataclass  #修饰器，简化类的定义
class AppConfig:
    """应用配置的数据容器。

    使用 dataclass 而不是普通 dict 的好处：
    - IDE 能自动补全字段名
    - 拼错字段名会在运行前就报错（静态检查）
    - 类型明确：一眼能看出每个字段是什么类型
    """
    api_key: str
    base_url: str
    model: str

    def __repr__(self) -> str:  #内置方法，调用print()或repr()时会调用该方法，返回str
        """打印配置时隐藏 API Key，防止日志泄露。

        API Key 只在内存中存在，不打印、不入日志、不写入文件。
        """
        masked_key = self.api_key[:8] + "****" + self.api_key[-4:] if len(self.api_key) > 12 else "****"
        return (
            f"AppConfig(base_url={self.base_url!r}, "   #等同于{repr（self.base_url）}，字符串会带上引号，更清晰
            f"model={self.model!r}, "
            f"api_key={masked_key!r})"
        )


def _find_env_file() -> Path | None:
    """向上查找 .env 文件，返回第一个存在的路径。

    查找顺序：
    1. 当前工作目录
    2. 当前文件所在目录向上两级（app/config.py -> week1_llm_cli/）

    返回 None 表示没找到 .env 文件。
    """
    # 先在当前工作目录找
    cwd_env = Path.cwd() / ".env"   #返回当前工作目录下的.env文件
    if cwd_env.exists():
        return cwd_env

    # 再在项目根目录找（假设 config.py 在 app/ 下）
    project_root = Path(__file__).resolve().parent.parent   #转换为绝对路径，__file__是内置变量，表当前脚本文件路径
    project_env = project_root / ".env"
    if project_env.exists():
        return project_env

    return None


def get_config() -> AppConfig:
    """读取 .env 配置并返回 AppConfig 实例。

    调用方不需要传任何参数——这个函数自动找 .env（load_dotenv)并解析。

    Raises:
        ConfigError: 缺少 .env 文件或必要配置项时抛出。
    """
    env_path = _find_env_file()
    if env_path is None:
        raise ConfigError(
            "找不到 .env 文件。\n"
            "请在项目根目录创建 .env 文件，参考 .env.example 的格式。\n"
            "最小 .env 内容：\n"
            "  LLM_API_KEY=your-api-key\n"
            "  LLM_BASE_URL=https://api.deepseek.com\n"
            "  LLM_MODEL=deepseek-chat"
        )

    # load_dotenv 把 .env 的键值对注入 os.environ，已存在的环境变量不会被覆盖
    load_dotenv(env_path)

    api_key = os.getenv("LLM_API_KEY")  #返回键的值
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")

    # 逐一检查，给出精确的错误提示——不让用户猜哪个变量没配
    missing: list[str] = [] #变量名=list[str]，类型注解，表示missing是一个字符串列表
    if not api_key:
        missing.append("LLM_API_KEY")
    if not base_url:
        missing.append("LLM_BASE_URL")
    if not model:
        missing.append("LLM_MODEL")

    if missing:
        raise ConfigError(
            f"以下环境变量未配置：{', '.join(missing)}\n"   #列表拼接字符串，''.join(liebiao)
            f"请检查 .env 文件（路径：{env_path}）确保这些字段都已填写。"
        )

    return AppConfig(api_key=api_key, base_url=base_url, model=model)


# 你需要观察什么：
# - _find_env_file() 为什么先查 Path.cwd() 再查相对路径：因为在不同目录执行 python main.py 时，当前工作目录可能不同
# - get_config() 为什么返回 AppConfig 对象而不是 dict：dataclass 让你写 cfg.api_key 而不是 cfg["api_key"]，拼错 IDE 会标红,字典平措不会报错，程序会静默失败
# - __repr__ 为什么不直接打印 api_key：防止日志文件泄露密钥