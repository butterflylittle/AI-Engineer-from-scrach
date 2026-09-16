"""最小 Deep Agents 示例：模型调用一个自定义工具。"""

import os
import sys
from pathlib import Path

from deepagents import create_deep_agent
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))
model = os.getenv("DEEPAGENTS_MODEL", "openai:gpt-5.5")

if model.startswith("openai:") and not os.getenv("OPENAI_API_KEY"):
    raise SystemExit("请复制 .env.example 为 .env，并填写 OPENAI_API_KEY")


def get_weather(city: str) -> str:
    """查询指定城市的天气。"""
    weather = {"北京": "晴，26°C", "上海": "多云，28°C", "深圳": "阵雨，30°C"}
    return weather.get(city, f"暂时没有 {city} 的天气数据")


agent = create_deep_agent(
    model=model,
    tools=[get_weather],
    system_prompt="你是简洁的中文助手。需要天气数据时必须调用 get_weather。",
)

question = " ".join(sys.argv[1:]) or "北京和深圳的天气如何？给我一个出行建议。"
result = agent.invoke({"messages": [{"role": "user", "content": question}]})

print(result["messages"][-1].content)
