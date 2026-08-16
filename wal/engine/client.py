"""LLM 客户端 — 支持 DeepSeek (OpenAI 兼容) + Anthropic API"""

import os
import json
import time
from typing import Optional

import httpx
from loguru import logger


class LLMClient:
    """多后端 LLM 客户端，默认使用 DeepSeek (OpenAI 兼容协议)"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "deepseek-v4-pro",
        base_url: str = "https://api.deepseek.com/v1",
        provider: str = "openai",  # "openai" | "anthropic"
        timeout: int = 120,
        thinking: bool | None = None,
        reasoning_effort: str = "",
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.provider = provider
        self.timeout = timeout
        # 思考模式：默认关闭（省 token/延迟，temperature 才生效）。
        # 显式传参优先；否则读环境变量 DEEPSEEK_THINKING=1 开启。
        self.thinking = thinking if thinking is not None else (os.environ.get("DEEPSEEK_THINKING", "0") == "1")
        # 思考强度（DeepSeek: low | high | max），仅 thinking 开启时发送
        self.reasoning_effort = reasoning_effort
        self._client = self._new_client()

    def _new_client(self) -> httpx.Client:
        """创建 httpx 客户端。

        禁用 keep-alive（max_keepalive_connections=0）：DeepSeek 会掐掉长期复用的
        连接，复用时抛 SSL/EOF 错误（"peer closed connection without sending
        complete message body"）。每次请求用新连接，更稳。
        """
        return httpx.Client(
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_keepalive_connections=0),
        )

    def _reset_client(self) -> None:
        """连接出错后重建客户端（丢弃可能已死的 keep-alive 连接）。"""
        try:
            self._client.close()
        except Exception:
            pass
        self._client = self._new_client()

    # ============================================================
    #  OpenAI 兼容 API（DeepSeek 等）
    # ============================================================

    def _openai_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        stream: bool = False,
        reasoning_effort: str = "",
    ) -> dict:
        """发送 OpenAI 兼容请求，返回完整响应

        Args:
            messages: [{"role": "system"|"user"|"assistant"|"tool", "content": "..."}]
            tools: OpenAI 格式的 tools 定义列表
            temperature: 温度
            max_tokens: 最大生成 token 数
            stream: 是否流式
            reasoning_effort: 思考强度 (low|high|max)，仅 thinking 开启时发送

        Returns:
            {"content": "文本", "tool_calls": [...] | None}
        """
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "thinking": {"type": "enabled" if self.thinking else "disabled"},
        }
        effort = reasoning_effort or self.reasoning_effort
        if self.thinking and effort:
            body["reasoning_effort"] = effort
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"

        # 连接被服务端掐断（keep-alive 失效）→ 重建客户端重试，最多 2 次
        for attempt in range(3):
            try:
                resp = self._client.post(url, headers=self._openai_headers(), json=body)
                resp.raise_for_status()
                data = resp.json()
                return self._parse_openai_response(data)
            except httpx.TransportError:
                if attempt >= 2:
                    logger.error(f"Request failed after 2 retries: connection error")
                    return {"content": "[Request Error] 连接 LLM 服务失败（已重试），请稍后重试。", "tool_calls": None}
                self._reset_client()
                time.sleep(0.5 * (attempt + 1))
            except httpx.HTTPStatusError as e:
                logger.error(f"API error: {e.response.status_code} - {e.response.text}")
                return {"content": f"[API Error: {e.response.status_code}] {e.response.text[:500]}", "tool_calls": None}
            except Exception as e:
                logger.error(f"Request failed: {e}")
                return {"content": f"[Request Error] {e}", "tool_calls": None}

        return {"content": "[Request Error] 未知错误", "tool_calls": None}

    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        reasoning_effort: str = "",
    ):
        """流式请求 — 逐 token 输出"""
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "thinking": {"type": "enabled" if self.thinking else "disabled"},
        }
        effort = reasoning_effort or self.reasoning_effort
        if self.thinking and effort:
            body["reasoning_effort"] = effort
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"

        # 连接被掐断（keep-alive 失效）→ 重建客户端重试，最多 2 次。
        # 若已在流式输出中途断掉（started=True），无法干净重试（会重复内容），直接抛给上层。
        for attempt in range(3):
            started = False
            try:
                with self._client.stream("POST", url, headers=self._openai_headers(), json=body) as resp:
                    resp.raise_for_status()

                    tool_calls_acc: dict[int, dict] = {}  # index -> {id, name, arguments}
                    content_parts: list[str] = []
                    reasoning_parts: list[str] = []       # DeepSeek reasoning_content 累积

                    for line in resp.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            finish_reason = chunk.get("choices", [{}])[0].get("finish_reason")

                            # 思考链（DeepSeek reasoning_content）：增量推送 → thinking_delta
                            reasoning = delta.get("reasoning_content")
                            if reasoning:
                                reasoning_parts.append(reasoning)
                                started = True
                                yield {"type": "reasoning", "content": reasoning}

                            # Content
                            if "content" in delta and delta["content"]:
                                text = delta["content"]
                                content_parts.append(text)
                                started = True
                                yield {"type": "text", "text": text}

                            # Tool calls
                            if "tool_calls" in delta:
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls_acc:
                                        tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                                    if "id" in tc:
                                        tool_calls_acc[idx]["id"] += tc["id"]
                                    if "function" in tc:
                                        if "name" in tc["function"]:
                                            tool_calls_acc[idx]["name"] += tc["function"]["name"]
                                        if "arguments" in tc["function"]:
                                            tool_calls_acc[idx]["arguments"] += tc["function"]["arguments"]

                            if finish_reason == "tool_calls" and tool_calls_acc:
                                tool_calls = [
                                    {
                                        "id": v["id"],
                                        "type": "function",
                                        "function": {"name": v["name"], "arguments": v["arguments"]},
                                    }
                                    for v in tool_calls_acc.values()
                                ]
                                ev = {"type": "tool_calls", "tool_calls": tool_calls}
                                # DeepSeek 思考模式：多轮工具调用须回传本轮的 reasoning_content
                                reasoning_content = "".join(reasoning_parts).strip()
                                if reasoning_content:
                                    ev["reasoning_content"] = reasoning_content
                                yield ev

                        except json.JSONDecodeError:
                            continue
                return
            except httpx.TransportError:
                if attempt >= 2 or started:
                    raise
                self._reset_client()
                time.sleep(0.5 * (attempt + 1))

    def _parse_openai_response(self, data: dict) -> dict:
        """解析 OpenAI 格式响应"""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")

        result = {"content": content, "tool_calls": tool_calls}
        reasoning = message.get("reasoning_content")
        if reasoning:
            result["reasoning_content"] = reasoning
        return result

    # ============================================================
    #  便捷方法：方便旧的 system + user 调用方式
    # ============================================================

    def chat_simple(self, system_prompt: str, user_message: str,
                    temperature: float = 0.7, max_tokens: int = 16384) -> str:
        """简单对话：system + user → text 回复"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        result = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return result["content"]

    def chat_with_tools(self, messages: list[dict], tools: list[dict],
                        temperature: float = 0.7, max_tokens: int = 16384) -> dict:
        """带工具的对话"""
        return self.chat(messages, tools=tools, temperature=temperature, max_tokens=max_tokens)

    # ============================================================
    #  Token 估算
    # ============================================================

    def count_tokens(self, text: str) -> int:
        """估算 token 数（中文约1.5字符/token，英文约4字符/token）"""
        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
