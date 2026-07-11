import logging
import re
from typing import Optional, Tuple
import httpx
from src.config import settings

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        # Initialize httpx AsyncClient for calling OpenAI-compatible completions endpoints
        self.http_client = httpx.AsyncClient(http2=True, timeout=30.0)

    async def call_model(self, command: str, messages: list) -> str:
        """
        Calls the primary provider/model for the command, falling back to a secondary provider if needed.
        Handles rate limits (429) and timeout errors.
        """
        from src.config.models import AI_MODELS
        if command not in AI_MODELS:
            raise ValueError(f"Unknown command: {command}")

        config = AI_MODELS[command]

        # Define the attempts order: primary first, fallback second
        attempts = [("primary", config["primary"])]
        if "fallback" in config:
            attempts.append(("fallback", config["fallback"]))

        last_error = None
        for attempt_name, model_conf in attempts:
            provider = model_conf["provider"]
            model = model_conf["model"]
            reasoning_effort = model_conf.get("reasoning_effort")

            # Check if key is available and get credentials
            base_url = None
            api_key = None

            if provider == "groq":
                base_url = "https://api.groq.com/openai/v1"
                api_key = settings.GROQ_API_KEY
            elif provider == "nvidia":
                base_url = "https://integrate.api.nvidia.com/v1"
                api_key = settings.NVIDIA_API_KEY
            elif provider == "openrouter":
                # Check for API key presence before attempting fallback (Gap 1)
                if not settings.OPENROUTER_API_KEY:
                    logger.warning("OpenRouter API key is missing. Skipping fallback attempt.")
                    last_error = "OpenRouter API key not configured"
                    continue
                base_url = "https://openrouter.ai/api/v1"
                api_key = settings.OPENROUTER_API_KEY
            else:
                logger.error(f"Unsupported provider configured: {provider}")
                last_error = f"Unsupported provider {provider}"
                continue

            if not api_key:
                logger.warning(f"API key for {provider} is not configured. Skipping this provider.")
                last_error = f"API key for {provider} not configured"
                continue

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": model,
                "messages": messages,
            }

            # Only add reasoning_effort parameter if specified in the model config
            if reasoning_effort:
                payload["reasoning_effort"] = reasoning_effort

            if provider == "openrouter":
                headers["HTTP-Referer"] = "https://github.com/Charicific/memoize-tgbot"
                headers["X-Title"] = "Memoize Telegram Bot"

            url = f"{base_url.rstrip('/')}/chat/completions"
            logger.info(f"Attempting {attempt_name} call to {provider} ({model}) for command '{command}'...")

            try:
                response = await self.http_client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )

                # Step 7: Check rate limit headers
                self._check_rate_limit_headers(provider, response.headers)

                if response.status_code == 429:
                    logger.warning(f"Rate limit (429) hit for {provider} ({model}) during {attempt_name} attempt.")
                    last_error = f"Rate limit (429) hit for {provider}"
                    continue

                response.raise_for_status()

                # Parse and normalize content (Gap 2)
                return self._normalize_and_extract_content(provider, response.json())

            except (httpx.HTTPError, httpx.TimeoutException, Exception) as e:
                logger.warning(f"Error calling {provider} ({model}) on {attempt_name} attempt: {e}")
                last_error = str(e)
                # Loop will retry with fallback if available

        # Both primary and fallback failed (or primary failed and fallback was skipped)
        raise RuntimeError("AI service temporarily unavailable, please try again in a moment")

    def _normalize_and_extract_content(self, provider: str, data: dict) -> str:
        """
        Extracts content from standard completions response shape and normalizes it
        by stripping out reasoning blocks like <think>...</think> tags.
        """
        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"Invalid completions response from {provider}: choices list is empty.")

        message = choices[0].get("message", {})
        content = message.get("content")
        if content is None:
            raise ValueError(f"Invalid completions response from {provider}: message content is missing.")

        # Strip any <think>...</think> blocks case-insensitively and multiline (Gap 2)
        normalized = re.sub(r'(?is)<think>.*?</think>', '', content)
        return normalized.strip()

    def _check_rate_limit_headers(self, provider: str, headers: httpx.Headers):
        """
        Logs a warning if any rate limit headers indicate that the remaining quota is low.
        """
        for key, val in headers.items():
            if "ratelimit-remaining" in key.lower():
                try:
                    remaining = int(val)
                    if remaining < 5:
                        logger.warning(
                            f"[Rate Limit Warning] Provider '{provider}' reports low remaining quota: {key}={val}"
                        )
                except ValueError:
                    pass

    async def generate_progressive_hints(self, problem_title: str, problem_description: str, code_templates: str) -> Optional[Tuple[str, str, str]]:
        """
        Generates 3 levels of hints: conceptual, strategic, and detailed pseudo-code.
        Returns a tuple of (hint_1, hint_2, hint_3) or None.
        """
        prompt = f"""
You are an expert algorithms coach teaching a student how to solve LeetCode problems.
Your goal is to guide the student towards the solution WITHOUT directly giving away the full code.

Problem Title: {problem_title}
Problem Description:
{problem_description}

Code Template:
{code_templates}

Generate three distinct progressive hints:
HINT 1: Conceptual Hint (High-level idea, intuition, data structures to use, but no implementation details).
HINT 2: Strategic Hint (Intermediate logic, traversal details, how to handle basic transitions/cases).
HINT 3: Detailed Logic/Pseudo-code Hint (Step-by-step logic, pseudo-code, but do not write the final Python/C++ code).

Format your output EXACTLY as follows with the custom delimiter "|||":
[HINT 1 CONTENT]
|||
[HINT 2 CONTENT]
|||
[HINT 3 CONTENT]
"""
        messages = [
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": prompt}
        ]
        try:
            content = await self.call_model("hint", messages)
            parts = [p.strip() for p in content.split("|||")]
            if len(parts) >= 3:
                return parts[0], parts[1], parts[2]
            else:
                return content, "Please think about the constraints and edge cases.", "Try implementing a brute force solution and optimizing it."
        except Exception as e:
            logger.error(f"Error in generate_progressive_hints: {e}")
            raise

    async def analyze_complexity(self, code_snippet: str) -> Optional[str]:
        """
        Analyzes the time and space complexity of the code.
        """
        prompt = f"""
Analyze the time and space complexity of the following code. The code can be in any programming language (e.g., C++, Python, Java, JavaScript, Go, etc.). Please identify the language of the code snippet, analyze its complexity, and explain your rationale accordingly.
Explain your analysis step-by-step and suggest if any optimizations can be made.

Code:
```
{code_snippet}
```

Format the output clearly using Markdown, highlighting:
1. **Time Complexity**
2. **Space Complexity**
3. **Step-by-Step Rationale**
4. **Potential Optimizations**
"""
        messages = [
            {"role": "system", "content": "You are an expert code analyst."},
            {"role": "user", "content": prompt}
        ]
        try:
            return await self.call_model("analyze", messages)
        except Exception as e:
            logger.error(f"Error in analyze_complexity: {e}")
            raise

    async def generate_code_review(self, problem_title: str, problem_description: str, user_code: str) -> Optional[str]:
        """
        Deep code review highlighting correctness, edge cases, style, and algorithmic improvement.
        """
        prompt = f"""
You are an elite software engineer and algorithms tutor.
Perform a thorough, detailed code review on the user's code for this LeetCode problem. The user's code can be written in any programming language (e.g., C++, Python, Java, JavaScript, Go, etc.). Please review the code in its respective programming language, and do not assume or enforce Python coding style or conventions unless the code is actually written in Python.

Problem: {problem_title}
Description:
{problem_description}

User's Code:
```
{user_code}
```

Please structure your review using the following sections in Markdown:
1. **Correctness & Edge Cases**: Are there any bugs, off-by-one errors, or inputs where this fails?
2. **Code Quality & Readability**: How clean is the code? Can variable names, structure, or style be improved?
3. **Performance Optimization**: Is there a more optimal time/space complexity approach? Explain how to implement it.
4. **Overall Score**: Rate the solution out of 10.
"""
        messages = [
            {"role": "system", "content": "You are an elite software engineer and algorithms tutor."},
            {"role": "user", "content": prompt}
        ]
        try:
            return await self.call_model("review", messages)
        except Exception as e:
            logger.error(f"Error in generate_code_review: {e}")
            raise

    async def generate_flowchart_mermaid(self, code_snippet: str) -> Optional[Tuple[str, str]]:
        """
        Generates a Mermaid flowchart diagram and step-by-step execution trace.
        Returns a tuple of (mermaid_code, execution_trace) or None.
        """
        prompt = f"""
You are an expert algorithms and compiler visualizer.
Your goal is to parse and trace the execution flow of the following code snippet and return:
1. A valid, clean Mermaid flowchart representing its control flow or recursion tree.
2. A step-by-step execution trace with variable values for a sample input.

Code:
{code_snippet}

Instructions for Mermaid:
- Start with `graph TD` or `flowchart TD`.
- Do not use HTML tags in node labels. Quote labels with double quotes.
- Keep the flowchart clear and structured.

Format your output EXACTLY as follows with the custom delimiter "|||":
[ONLY VALID MERMAID GRAPH CODE]
|||
[STEP-BY-STEP TRACE EXPLANATION IN TELEGRAM-COMPATIBLE HTML FORMAT (use only <b>, <i>, <code>, <pre>, and <u> tags; DO NOT use <p>, <br>, <ul>, or <li> tags. Use standard newlines for lists and spacing.)]
"""
        messages = [
            {"role": "system", "content": "You are a helpful software visualization assistant."},
            {"role": "user", "content": prompt}
        ]
        try:
            content = await self.call_model("visualize", messages)
            parts = [p.strip() for p in content.split("|||")]
            if len(parts) >= 2:
                mermaid_code = parts[0]
                # Clean up markdown code blocks if the LLM included them
                if mermaid_code.startswith("```"):
                    mermaid_lines = mermaid_code.splitlines()
                    if len(mermaid_lines) >= 2:
                        if mermaid_lines[0].startswith("```"):
                            mermaid_lines = mermaid_lines[1:]
                        if mermaid_lines[-1].startswith("```"):
                            mermaid_lines = mermaid_lines[:-1]
                        mermaid_code = "\n".join(mermaid_lines).strip()
                return mermaid_code, parts[1]
            return None
        except Exception as e:
            logger.error(f"Error in generate_flowchart_mermaid: {e}")
            raise

ai_service = AIService()
