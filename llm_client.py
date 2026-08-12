

"""
Minimal, provider-agnostic LLM client.

Supported providers:
- OpenAI
- Google AI Studio / Gemini
- Anthropic Claude
- Ollama

Install:
    pip install openai anthropic ollama google-generativeai
"""

from __future__ import annotations

from typing import List, Dict, Iterator, Any, Optional


class LLMError(Exception):
    """Raised when a provider fails to answer."""


# ============================================================
# OPENAI
# ============================================================

def ask_openai(
    messages: List[Dict[str, str]],
    api_key: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    stream: bool = True,
):
    from openai import OpenAI

    if not api_key:
        raise LLMError("No OpenAI API key was provided.")

    try:
        client = OpenAI(api_key=api_key)

        if stream:

            def _gen() -> Iterator[str]:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                )

                for chunk in response:
                    delta = chunk.choices[0].delta.content

                    if delta:
                        yield delta

            return _gen()

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        return response.choices[0].message.content

    except Exception as e:
        raise LLMError(str(e))


# ============================================================
# GOOGLE AI STUDIO / GEMINI
# ============================================================

def ask_gemini(
    messages: List[Dict[str, str]],
    api_key: str,
    model: str = "gemini-3.5-flash-lite",   # current Gemini default
    temperature: float = 0.7,
    stream: bool = True,
):
    import google.generativeai as genai

    if not api_key:
        raise LLMError("No Gemini API key was provided.")

    genai.configure(api_key=api_key)

    try:
        # Convert OpenAI-style messages → single prompt string
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                prompt += f"[SYSTEM]: {content}\n"
            elif role == "assistant":
                prompt += f"[ASSISTANT]: {content}\n"
            else:
                prompt += f"[USER]: {content}\n"

        model_obj = genai.GenerativeModel(model)

        # ---------------- STREAM ----------------
        if stream:
            def _gen() -> Iterator[str]:
                response = model_obj.generate_content(
                    prompt,
                    stream=True,
                    generation_config={"temperature": temperature},
                )
                for chunk in response:
                    if chunk.text:
                        yield chunk.text

            return _gen()

        # ---------------- NORMAL ----------------
        response = model_obj.generate_content(
            prompt,
            generation_config={"temperature": temperature},
        )

        return response.text

    except Exception as e:
        raise LLMError(str(e))


# ============================================================
# CLAUDE / ANTHROPIC
# ============================================================

def ask_claude(
    messages: List[Dict[str, str]],
    api_key: str,
    model: str = "claude-sonnet-5",  # current Anthropic frontier default
    temperature: float = 0.7,
    stream: bool = True,
    system: str = "",
):
    """
    Anthropic Claude via the official Messages API.
    """
    import anthropic

    if not api_key:
        raise LLMError("No Anthropic API key was provided.")

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Strip system messages out; pass them via the dedicated system param
        chat_messages = [
            message
            for message in messages
            if message.get("role") != "system"
        ]

        if not system:
            system = next(
                (
                    message["content"]
                    for message in messages
                    if message.get("role") == "system"
                ),
                "",
            )

        # ---------------- STREAM ----------------
        if stream:
            def _gen() -> Iterator[str]:
                with client.messages.stream(
                    model=model,
                    max_tokens=1024,
                    temperature=temperature,
                    system=system,
                    messages=chat_messages,
                ) as response:
                    for text in response.text_stream:
                        yield text

            return _gen()

        # ---------------- NORMAL ----------------
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=temperature,
            system=system,
            messages=chat_messages,
        )

        return "".join(
            block.text
            for block in response.content
            if block.type == "text"
        )

    except Exception as e:
        raise LLMError(str(e))


# ============================================================
# OLLAMA
# ============================================================

def ask_ollama(
    messages: List[Dict[str, str]],
    model: str = "llama3",
    temperature: float = 0.7,
    stream: bool = True,
    host: str | None = None,
):
    import ollama

    try:
        client = ollama.Client(host=host) if host else ollama

        # ---------------- STREAM ----------------
        if stream:
            def _gen() -> Iterator[str]:
                response_stream = client.chat(
                    model=model,
                    messages=messages,
                    options={"temperature": temperature},
                    stream=True,
                )

                for chunk in response_stream:
                    piece = (
                        chunk
                        .get("message", {})
                        .get("content", "")
                    )
                    if piece:
                        yield piece

            return _gen()

        # ---------------- NORMAL ----------------
        response = client.chat(
            model=model,
            messages=messages,
            options={"temperature": temperature},
        )

        return response["message"]["content"]

    except Exception as e:
        raise LLMError(str(e))


# ============================================================
# MAIN ROUTER
# ============================================================

def ask(
    provider: str,
    messages: List[Dict[str, str]],
    *,
    api_key: str = "",
    model: str = "",
    temperature: float = 0.7,
    stream: bool = True,
    ollama_host: str | None = None,
):
    """
    Route a request to the selected LLM provider.
    """

    if provider == "OpenAI":
        return ask_openai(
            messages=messages,
            api_key=api_key,
            model=model or "gpt-4o-mini",
            temperature=temperature,
            stream=stream,
        )

    elif provider == "Gemini":
        return ask_gemini(
            messages=messages,
            api_key=api_key,
            model=model or "gemini-3.5-flash-lite",  # current Gemini default
            temperature=temperature,
            stream=stream,
        )

    elif provider == "Claude (Anthropic)":
        return ask_claude(
            messages=messages,
            api_key=api_key,
            model=model or "claude-sonnet-5",  # current Anthropic frontier default
            temperature=temperature,
            stream=stream,
        )

    elif provider == "Ollama (local)":
        return ask_ollama(
            messages=messages,
            model=model or "llama3",
            temperature=temperature,
            stream=stream,
            host=ollama_host,
        )

    else:
        raise LLMError(f"Unknown provider: {provider}")


# ============================================================
# CLAUDE TOOL-USE LOOP (Phase 1)
# ============================================================
# This is a sibling of ask_claude() that returns a structured dict so
# the caller can drive a tool loop instead of one chat call. It runs
# the full agent loop: calls Anthropic, walks response.content, hands
# tool_use blocks to an executor, appends tool_result blocks, loops.
# Capped at `max_iterations` to prevent runaway loops.

def ask_claude_with_tools(
    messages: List[Dict[str, str]],
    api_key: str,
    model: str,
    tools: list,
    executor,                        # ToolExecutor instance
    temperature: float = 0.7,
    max_iterations: int = 5,
):
    """Run a Claude tool-use loop and return a structured result.

    Returns
    -------
    dict
        {"text": str_or_None,
         "tool_calls": [list of {tool_name, tool_input, result}],
         "stop_reason": str,
         "needs_confirmation": bool,
         "envelope": dict_or_None}
    """
    import anthropic

    if not api_key:
        raise LLMError("No Anthropic API key was provided.")

    client = anthropic.Anthropic(api_key=api_key)

    # Strip the system message out of `messages` and pass it on `system=`.
    chat_messages = []
    system_prompt = ""
    for message in messages:
        if message.get("role") == "system":
            system_prompt += (message.get("content") or "") + "\n"
        else:
            chat_messages.append(message)

    tool_calls: List[Dict[str, Any]] = []
    final_text: Optional[str] = None
    stop_reason: Optional[str] = None

    for iteration in range(max_iterations):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                temperature=temperature,
                system=system_prompt or "",
                tools=tools,
                tool_choice={"type": "auto"},
                messages=chat_messages,
            )
        except Exception as e:
            raise LLMError(str(e))

        stop_reason = getattr(response, "stop_reason", None)

        # Walk response.content. Tool-use blocks go to the executor;
        # text blocks accumulate into final_text.
        text_parts: List[str] = []
        tool_use_blocks = []

        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", "") or "")
            elif block_type == "tool_use":
                tool_use_blocks.append(block)

        if tool_use_blocks:
            results, envelope = executor.execute_many(tool_use_blocks)

            # If any tool needs confirmation, bail out with the envelope.
            if envelope is not None:
                # Record what we got back so far.
                for block in tool_use_blocks:
                    tool_calls.append({
                        "tool_name": getattr(block, "name", ""),
                        "tool_input": getattr(block, "input", {}) or {},
                        "result": "(awaiting confirmation)",
                    })
                return {
                    "text": "\n".join(text_parts) or None,
                    "tool_calls": tool_calls,
                    "stop_reason": stop_reason,
                    "needs_confirmation": True,
                    "envelope": envelope,
                }

            # Append the assistant turn (the tool_use blocks) plus the
            # tool_result blocks so Anthropic sees them on the next call.
            chat_messages.append({
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "input": getattr(block, "input", {}) or {},
                    }
                    for block in tool_use_blocks
                ],
            })
            chat_messages.append({"role": "user", "content": results})

            for block, result in zip(tool_use_blocks, results):
                tool_calls.append({
                    "tool_name": getattr(block, "name", ""),
                    "tool_input": getattr(block, "input", {}) or {},
                    "result": result.get("content", ""),
                })

            # If the model also emitted text alongside tool_use, keep
            # it for the final response (most calls won't, but be safe).
            if text_parts:
                final_text = "\n".join(text_parts)
            continue

        # No tool_use blocks: this is the final answer.
        final_text = "\n".join(text_parts)
        break

    if final_text is None:
        final_text = "(Jaguar stopped after 5 tool steps.)"

    return {
        "text": final_text,
        "tool_calls": tool_calls,
        "stop_reason": stop_reason,
        "needs_confirmation": False,
        "envelope": None,
    }