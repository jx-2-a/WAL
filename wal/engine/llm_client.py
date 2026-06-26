"""LLM 客户端 — 支持 DeepSeek (OpenAI 兼容) + Anthropic API"""

import os
import json
from typing import Optional

import httpx
from loguru import logger


class LLMClient:
    """多后端 LLM 客户端，默认使用 DeepSeek (OpenAI 兼容协议)"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com/v1",
        provider: str = "openai",  # "openai" | "anthropic"
        timeout: int = 120,
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.provider = provider
        self.timeout = timeout
        self._client = httpx.Client(timeout=httpx.Timeout(timeout))

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
        max_tokens: int = 8192,
        stream: bool = False,
    ) -> dict:
        """发送 OpenAI 兼容请求，返回完整响应

        Args:
            messages: [{"role": "system"|"user"|"assistant"|"tool", "content": "..."}]
            tools: OpenAI 格式的 tools 定义列表
            temperature: 温度
            max_tokens: 最大生成 token 数
            stream: 是否流式

        Returns:
            {"content": "文本", "tool_calls": [...] | None}
        """
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"

        try:
            resp = self._client.post(url, headers=self._openai_headers(), json=body)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"API error: {e.response.status_code} - {e.response.text}")
            return {"content": f"[API Error: {e.response.status_code}] {e.response.text[:500]}", "tool_calls": None}
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {"content": f"[Request Error] {e}", "tool_calls": None}

        return self._parse_openai_response(data)

    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ):
        """流式请求 — 逐 token 输出"""
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"

        with self._client.stream("POST", url, headers=self._openai_headers(), json=body) as resp:
            resp.raise_for_status()

            tool_calls_acc: dict[int, dict] = {}  # index -> {id, name, arguments}
            content_parts: list[str] = []

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

                    # Content
                    if "content" in delta and delta["content"]:
                        text = delta["content"]
                        content_parts.append(text)
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
                        yield {"type": "tool_calls", "tool_calls": tool_calls}

                except json.JSONDecodeError:
                    continue

    def _parse_openai_response(self, data: dict) -> dict:
        """解析 OpenAI 格式响应"""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")

        return {"content": content, "tool_calls": tool_calls}

    # ============================================================
    #  便捷方法：方便旧的 system + user 调用方式
    # ============================================================

    def chat_simple(self, system_prompt: str, user_message: str,
                    temperature: float = 0.7, max_tokens: int = 8192) -> str:
        """简单对话：system + user → text 回复"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        result = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return result["content"]

    def chat_with_tools(self, messages: list[dict], tools: list[dict],
                        temperature: float = 0.7, max_tokens: int = 8192) -> dict:
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
