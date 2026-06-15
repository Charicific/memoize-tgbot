import logging
from typing import Optional, Tuple
from groq import AsyncGroq
import google.generativeai as genai
from src.config import settings

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        genai.configure(api_key=settings.GEMINI_API_KEY)
        # Use gemini-2.0-flash as it is the default recommended fallback
        self.gemini_model = genai.GenerativeModel("gemini-2.0-flash")

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
        try:
            chat_completion = await self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful coding assistant."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3
            )
            content = chat_completion.choices[0].message.content
            parts = [p.strip() for p in content.split("|||")]
            if len(parts) >= 3:
                return parts[0], parts[1], parts[2]
            else:
                # Fallback if split fails
                return content, "Please think about the constraints and edge cases.", "Try implementing a brute force solution and optimizing it."
        except Exception as e:
            logger.error(f"Error in Groq generate_progressive_hints: {e}")
            return None

    async def analyze_complexity(self, code_snippet: str) -> Optional[str]:
        """
        Analyzes the time and space complexity of the code.
        """
        prompt = f"""
Analyze the time and space complexity of the following code.
Explain your analysis step-by-step and suggest if any optimizations can be made.

Code:
```python
{code_snippet}
```

Format the output clearly using Markdown, highlighting:
1. **Time Complexity**
2. **Space Complexity**
3. **Step-by-Step Rationale**
4. **Potential Optimizations**
"""
        try:
            chat_completion = await self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an expert code analyst."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.2
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in Groq analyze_complexity: {e}")
            return None

    async def generate_code_review(self, problem_title: str, problem_description: str, user_code: str) -> Optional[str]:
        """
        Deep code review highlighting correctness, edge cases, style, and algorithmic improvement using Gemini Flash 2.0.
        """
        prompt = f"""
You are an elite software engineer and algorithms tutor.
Perform a thorough, detailed code review on the user's code for this LeetCode problem.

Problem: {problem_title}
Description:
{problem_description}

User's Code:
```python
{user_code}
```

Please structure your review using the following sections in Markdown:
1. **Correctness & Edge Cases**: Are there any bugs, off-by-one errors, or inputs where this fails?
2. **Code Quality & Readability**: How clean is the code? Can variable names, structure, or style be improved?
3. **Performance Optimization**: Is there a more optimal time/space complexity approach? Explain how to implement it.
4. **Overall Score**: Rate the solution out of 10.
"""
        try:
            # Use async API of google-generativeai
            response = await self.gemini_model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error in Gemini generate_code_review: {e}")
            return None

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
        try:
            chat_completion = await self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful software visualization assistant."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.2
            )
            content = chat_completion.choices[0].message.content
            parts = [p.strip() for p in content.split("|||")]
            if len(parts) >= 2:
                # Clean up markdown code blocks if the LLM included them
                mermaid_code = parts[0]
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
            return None

ai_service = AIService()
