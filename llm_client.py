
# """
# Minimal, provider-agnostic LLM client.

# Supported providers:
# - OpenAI
# - Google AI Studio / Gemini
# - Anthropic Claude
# - Ollama

# Install:
#     pip install openai anthropic ollama google-genai
# """

# from __future__ import annotations

# from typing import List, Dict, Iterator


# class LLMError(Exception):
#     """Raised when a provider fails to answer."""


# # ============================================================
# # OPENAI
# # ============================================================

# def ask_openai(
#     messages: List[Dict[str, str]],
#     api_key: str,
#     model: str = "gpt-4o-mini",
#     temperature: float = 0.7,
#     stream: bool = True,
# ):
#     from openai import OpenAI

#     if not api_key:
#         raise LLMError("No OpenAI API key was provided.")

#     try:
#         client = OpenAI(api_key=api_key)

#         if stream:

#             def _gen() -> Iterator[str]:
#                 response = client.chat.completions.create(
#                     model=model,
#                     messages=messages,
#                     temperature=temperature,
#                     stream=True,
#                 )

#                 for chunk in response:
#                     delta = chunk.choices[0].delta.content

#                     if delta:
#                         yield delta

#             return _gen()

#         response = client.chat.completions.create(
#             model=model,
#             messages=messages,
#             temperature=temperature,
#         )

#         return response.choices[0].message.content

#     except Exception as e:
#         raise LLMError(str(e))


# # ============================================================
# # GOOGLE AI STUDIO / GEMINI
# # ============================================================

# def ask_gemini(
#     messages: List[Dict[str, str]],
#     api_key: str,
#     model: str = "gemini-1.5-flash",
#     temperature: float = 0.7,
#     stream: bool = True,
# ):
#     """
#     Google AI Studio / Gemini API.

#     Uses the official google-genai SDK.
#     """

#     from google import genai
#     from google.genai import types
#     # import google.generativeai as genai

#     if not api_key:
#         raise LLMError("No Gemini API key was provided.")

#     try:

#         client = genai.Client(api_key=api_key)

#         # ----------------------------------------------------
#         # Convert OpenAI-style messages to Gemini format
#         # ----------------------------------------------------

#         system_prompt = ""

#         contents = []

#         for message in messages:

#             role = message.get("role", "user")
#             content = message.get("content", "")

#             if role == "system":

#                 system_prompt += content + "\n"

#             elif role == "assistant":

#                 contents.append(
#                     {
#                         "role": "model",
#                         "parts": [
#                             {
#                                 "text": content
#                             }
#                         ],
#                     }
#                 )

#             else:

#                 contents.append(
#                     {
#                         "role": "user",
#                         "parts": [
#                             {
#                                 "text": content
#                             }
#                         ],
#                     }
#                 )

#         # ----------------------------------------------------
#         # Gemini configuration
#         # ----------------------------------------------------

#         config = types.GenerateContentConfig(
#             temperature=temperature,
#             system_instruction=system_prompt if system_prompt else None,
#         )

#         # ----------------------------------------------------
#         # STREAMING RESPONSE
#         # ----------------------------------------------------

#         if stream:

#             def _gen() -> Iterator[str]:

#                 response_stream = client.models.generate_content_stream(
#                     model=model,
#                     contents=contents,
#                     config=config,
#                 )

#                 for chunk in response_stream:

#                     if chunk.text:
#                         yield chunk.text

#             return _gen()

#         # ----------------------------------------------------
#         # NORMAL RESPONSE
#         # ----------------------------------------------------

#         response = client.models.generate_content(
#             model=model,
#             contents=contents,
#             config=config,
#         )

#         return response.text

#     except Exception as e:
#         raise LLMError(str(e))


# # ============================================================
# # CLAUDE / ANTHROPIC
# # ============================================================

# def ask_claude(
#     messages: List[Dict[str, str]],
#     api_key: str,
#     model: str = "claude-sonnet-5",
#     temperature: float = 0.7,
#     stream: bool = True,
#     system: str = "",
# ):
#     """
#     Anthropic Claude via the official Messages API.
#     """

#     import anthropic

#     if not api_key:
#         raise LLMError("No Anthropic API key was provided.")

#     try:

#         client = anthropic.Anthropic(api_key=api_key)

#         # Extract system message
#         chat_messages = [
#             message
#             for message in messages
#             if message.get("role") != "system"
#         ]

#         if not system:

#             system = next(
#                 (
#                     message["content"]
#                     for message in messages
#                     if message.get("role") == "system"
#                 ),
#                 "",
#             )

#         # ----------------------------------------------------
#         # STREAMING
#         # ----------------------------------------------------

#         if stream:

#             def _gen() -> Iterator[str]:

#                 with client.messages.stream(
#                     model=model,
#                     max_tokens=1024,
#                     temperature=temperature,
#                     system=system,
#                     messages=chat_messages,
#                 ) as response:

#                     for text in response.text_stream:
#                         yield text

#             return _gen()

#         # ----------------------------------------------------
#         # NORMAL RESPONSE
#         # ----------------------------------------------------

#         response = client.messages.create(
#             model=model,
#             max_tokens=1024,
#             temperature=temperature,
#             system=system,
#             messages=chat_messages,
#         )

#         return "".join(
#             block.text
#             for block in response.content
#             if block.type == "text"
#         )

#     except Exception as e:
#         raise LLMError(str(e))


# # ============================================================
# # OLLAMA
# # ============================================================

# def ask_ollama(
#     messages: List[Dict[str, str]],
#     model: str = "llama3",
#     temperature: float = 0.7,
#     stream: bool = True,
#     host: str | None = None,
# ):
#     import ollama

#     try:

#         client = ollama.Client(host=host) if host else ollama

#         # ----------------------------------------------------
#         # STREAMING
#         # ----------------------------------------------------

#         if stream:

#             def _gen() -> Iterator[str]:

#                 response_stream = client.chat(
#                     model=model,
#                     messages=messages,
#                     options={
#                         "temperature": temperature
#                     },
#                     stream=True,
#                 )

#                 for chunk in response_stream:

#                     piece = (
#                         chunk
#                         .get("message", {})
#                         .get("content", "")
#                     )

#                     if piece:
#                         yield piece

#             return _gen()

#         # ----------------------------------------------------
#         # NORMAL RESPONSE
#         # ----------------------------------------------------

#         response = client.chat(
#             model=model,
#             messages=messages,
#             options={
#                 "temperature": temperature
#             },
#         )

#         return response["message"]["content"]

#     except Exception as e:
#         raise LLMError(str(e))


# # ============================================================
# # MAIN ROUTER
# # ============================================================

# def ask(
#     provider: str,
#     messages: List[Dict[str, str]],
#     *,
#     api_key: str = "",
#     model: str = "",
#     temperature: float = 0.7,
#     stream: bool = True,
#     ollama_host: str | None = None,
# ):
#     """
#     Route a request to the selected LLM provider.
#     """

#     if provider == "OpenAI":

#         return ask_openai(
#             messages=messages,
#             api_key=api_key,
#             model=model or "gpt-4o-mini",
#             temperature=temperature,
#             stream=stream,
#         )

#     elif provider == "Gemini":

#         return ask_gemini(
#             messages=messages,
#             api_key=api_key,
#             model=model or "gemini-3.5-flash",
#             temperature=temperature,
#             stream=stream,
#         )

#     elif provider == "Claude (Anthropic)":

#         return ask_claude(
#             messages=messages,
#             api_key=api_key,
#             model=model or "claude-sonnet-5",
#             temperature=temperature,
#             stream=stream,
#         )

#     elif provider == "Ollama (local)":

#         return ask_ollama(
#             messages=messages,
#             model=model or "llama3",
#             temperature=temperature,
#             stream=stream,
#             host=ollama_host,
#         )

#     else:

#         raise LLMError(
#             f"Unknown provider: {provider}"
#         )









































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

from typing import List, Dict, Iterator


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
    model: str = "gemini-2.0-flash",   # ← was "gemini-1.5-flash" (deprecated)
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
    model: str = "claude-sonnet-4-6",  # ← was "claude-sonnet-5" (invalid)
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
            model=model or "gemini-2.0-flash",  # ← was "gemini-3.5-flash" (doesn't exist)
            temperature=temperature,
            stream=stream,
        )

    elif provider == "Claude (Anthropic)":
        return ask_claude(
            messages=messages,
            api_key=api_key,
            model=model or "claude-sonnet-4-6",  # ← was "claude-sonnet-5" (invalid)
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