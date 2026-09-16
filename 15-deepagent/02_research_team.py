"""进阶示例：主 Agent 委派子 Agent，并把报告写入受限工作区。"""

import os
import sys
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "workspace"
WORKSPACE.mkdir(exist_ok=True)

load_dotenv(ROOT / ".env")
model = os.getenv("DEEPAGENTS_MODEL", "openai:gpt-5.5")

if model.startswith("openai:") and not os.getenv("OPENAI_API_KEY"):
    raise SystemExit("请复制 .env.example 为 .env，并填写 OPENAI_API_KEY")


def read_course_notes(section: str) -> str:
    """读取课程资料；section 可传 architecture、filesystem 或 subagents。"""
    notes = {
        "architecture": (
            "Deep Agents 是构建在 LangChain create_agent 之上的 opinionated agent harness，"
            "底层使用 LangGraph runtime。"
        ),
        "filesystem": (
            "它通过可插拔 backend 提供 ls、read_file、write_file、edit_file、glob、grep 等工具；"
            "本地 FilesystemBackend 应设置 virtual_mode=True 限制路径逃逸。"
        ),
        "subagents": (
            "主 Agent 可用 task 工具把复杂子任务交给隔离上下文中的子 Agent；"
            "子 Agent 只向主 Agent 返回最终结果，适合控制上下文膨胀。"
        ),
    }
    return notes.get(section, "未知章节，请选择 architecture、filesystem 或 subagents。")


subagents = [
    {
        "name": "researcher",
        "description": "查阅课程资料并整理准确事实。",
        "system_prompt": (
            "你是资料研究员。调用 read_course_notes 查阅相关章节，"
            "只返回有依据的事实和建议引用的章节名。"
        ),
        "tools": [read_course_notes],
    },
    {
        "name": "reviewer",
        "description": "审阅报告的准确性、结构和初学者可读性。",
        "system_prompt": (
            "你是严格的技术编辑。阅读工作区中的草稿，指出事实错误、遗漏和晦涩表达，"
            "不要直接重写全文。"
        ),
        "tools": [],
    },
]

agent = create_deep_agent(
    model=model,
    tools=[read_course_notes],
    subagents=subagents,
    backend=FilesystemBackend(root_dir=str(WORKSPACE), virtual_mode=True),
    system_prompt=(
        "你是主编。先委派 researcher 收集事实，写出 /report.md 草稿；"
        "再委派 reviewer 审阅草稿；最后根据意见修订 /report.md。"
        "报告必须是中文 Markdown，并在最终回复中说明文件位置。"
    ),
)

task = " ".join(sys.argv[1:]) or (
    "写一份给 Python 初学者的 Deep Agents 简介，解释它与 LangChain、LangGraph 的关系，"
    "并说明文件系统和子 Agent 的价值。控制在 500 字以内。"
)
result = agent.invoke({"messages": [{"role": "user", "content": task}]})

print(result["messages"][-1].content)
report = WORKSPACE / "report.md"
if report.exists():
    print(f"\n报告已生成：{report}")
