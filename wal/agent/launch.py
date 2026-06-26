"""Agent 启动入口 — 由 start.ps1 调用，或直接 python -m wal.agent.launch <project>"""

import argparse
import os
import sys

# 确保项目根目录在 path 中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def main():
    parser = argparse.ArgumentParser(description="WAL 小说写作 Agent")
    parser.add_argument("project", help="小说项目名称")
    parser.add_argument("--model", default="deepseek-chat", help="LLM 模型 (默认: deepseek-chat)")
    parser.add_argument("--base-url", default="https://api.deepseek.com/v1", help="API 地址")
    parser.add_argument("--api-key", default=None, help="API Key (默认从环境变量读取)")
    parser.add_argument("--quiet", action="store_true", default=False,
                        help="以安静模式启动（隐藏工具调用详情）")
    parser.add_argument("--mode", default="writing",
                        choices=["writing", "planning", "autonomous"],
                        help="Agent 启动模式 (默认: writing)")
    args = parser.parse_args()

    from wal.agent.repl import TerminalREPL
    from wal.agent.plan_mode import AgentMode

    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY", "")

    if not api_key:
        print("[ERROR] DEEPSEEK_API_KEY 未设置！")
        print("  请在 .env 文件或环境变量中设置 DEEPSEEK_API_KEY")
        sys.exit(1)

    mode_map = {
        "writing": AgentMode.WRITING,
        "planning": AgentMode.PLANNING,
        "autonomous": AgentMode.AUTONOMOUS,
    }

    repl = TerminalREPL(
        project_name=args.project,
        api_key=api_key,
        model=args.model,
        base_url=args.base_url,
        mode=mode_map[args.mode],
        quiet=args.quiet,
    )

    repl.run()


if __name__ == "__main__":
    main()
