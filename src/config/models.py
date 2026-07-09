AI_MODELS = {
    "hint": {
        "primary": {
            "provider": "groq",
            "model": "openai/gpt-oss-120b",
            "reasoning_effort": "low",
        },
        "fallback": {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct:free",
        },
    },
    "analyze": {
        "primary": {
            "provider": "groq",
            "model": "openai/gpt-oss-120b",
            "reasoning_effort": "medium",
        },
        "fallback": {
            "provider": "openrouter",
            "model": "deepseek/deepseek-v4-flash:free",
        },
    },
    "review": {
        "primary": {
            "provider": "nvidia",
            "model": "qwen/qwen3-coder-480b-a35b-instruct",
        },
        "fallback": {
            "provider": "openrouter",
            "model": "qwen/qwen3-coder:free",
        },
    },
    "visualize": {
        "primary": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v3.2",
        },
        "fallback": {
            "provider": "openrouter",
            "model": "deepseek/deepseek-v4-flash:free",
        },
    },
}
