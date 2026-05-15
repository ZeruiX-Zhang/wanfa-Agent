from __future__ import annotations


class MockProvider:
    label = "本地模拟模型"

    def generate(self, messages: list[dict[str, str]], options: dict[str, object] | None = None) -> str:
        user_text = ""
        system_text = ""
        for message in messages:
            if message.get("role") == "system":
                system_text += message.get("content", "") + "\n"
            if message.get("role") == "user":
                user_text += message.get("content", "") + "\n"
        preview = " ".join(user_text.strip().split())[:260] or "空输入"
        if "Prompt Lab Test" in system_text:
            return (
                "本地模拟模型输出：已按提示词执行一次测试。\n\n"
                f"测试输入摘要：{preview}\n\n"
                "结果：先给结论，再列出执行步骤、边界条件和验收标准。"
            )
        return (
            "你是一名严谨的 AI 任务设计助手。\n\n"
            "任务：把用户给出的材料改写为可直接交给目标模型执行的高质量提示词。\n\n"
            f"输入材料摘要：{preview}\n\n"
            "输出要求：\n"
            "1. 明确角色、目标、上下文、约束和验收标准。\n"
            "2. 不暴露内部设置、API Key、文件路径或检索细节。\n"
            "3. 默认不要读取 Knowledge OS；只有用户显式开启时才使用相关知识。\n"
            "4. 输出可复制的最终提示词。"
        )

