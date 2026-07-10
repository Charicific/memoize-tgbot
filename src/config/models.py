AI_MODELS = {
    "hint": {
        "primary": {
            "provider": "groq",
            "model": "openai/gpt-oss-120b",
            "reasoning_effort": "low",
        },
        "fallback": {
            "provider": "openrouter",
            "model": "google/gemma-4-31b-it:free",
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
            "model": "google/gemma-4-31b-it:free",
        },
    },
    "review": {
        "primary": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
        },
        "fallback": {
            "provider": "openrouter",
            "model": "google/gemma-4-31b-it:free",
        },
    },
    "visualize": {
        "primary": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
        },
        "fallback": {
            "provider": "openrouter",
            "model": "google/gemma-4-31b-it:free",
        },
    },
}
