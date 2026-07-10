import re
from html.parser import HTMLParser
from io import StringIO
from typing import Optional

class TelegramHTMLParser(HTMLParser):
    # Map HTML tags to Telegram-supported equivalents
    TAG_MAP = {
        "strong": "b",
        "em": "i",
        "ins": "u",
        "strike": "s",
        "del": "s",
        # Pass-through tags already supported by Telegram
        "b": "b",
        "i": "i",
        "u": "u",
        "s": "s",
        "code": "code",
        "pre": "pre",
        "a": "a",
    }

    def __init__(self, max_length: Optional[int] = None):
        super().__init__()
        self.output = StringIO()
        self.active_tags = []  # stores the *mapped* tag names
        self.max_length = max_length
        self.truncated = False

    def handle_starttag(self, tag, attrs):
        if self.truncated:
            return
        tag = tag.lower()
        if tag == "p":
            self.output.write("\n")
        elif tag == "br":
            self.output.write("\n")
        elif tag == "li":
            self.output.write("• ")
        elif tag in self.TAG_MAP:
            mapped = self.TAG_MAP[tag]
            attr_str = ""
            if mapped == "a":
                href = next((val for name, val in attrs if name == "href"), None)
                if href:
                    attr_str = f' href="{href}"'
            self.output.write(f"<{mapped}{attr_str}>")
            self.active_tags.append(mapped)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.TAG_MAP:
            mapped = self.TAG_MAP[tag]
            if mapped in self.active_tags:
                self.output.write(f"</{mapped}>")
                # Remove the last occurrence (handles nested same tags)
                idx = len(self.active_tags) - 1 - self.active_tags[::-1].index(mapped)
                self.active_tags.pop(idx)
        elif not self.truncated:
            if tag == "p":
                self.output.write("\n")
            elif tag == "li":
                self.output.write("\n")

    def handle_data(self, data):
        if self.truncated:
            return
        
        escaped_data = data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        if self.max_length and self.output.tell() + len(escaped_data) > self.max_length:
            allowed_len = self.max_length - self.output.tell()
            if allowed_len > 0:
                self.output.write(escaped_data[:allowed_len])
            self.output.write("\n\n...[Description truncated. Click the link to read more]...")
            self.truncated = True
        else:
            self.output.write(escaped_data)

    def get_result(self) -> str:
        # Close any remaining active tags in reverse order to ensure well-formed HTML
        for tag in reversed(self.active_tags):
            self.output.write(f"</{tag}>")
        self.active_tags.clear()

        text = self.output.getvalue()
        # Clean up consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

def clean_leetcode_html(html_content: str, max_length: Optional[int] = None) -> str:
    """
    Parses LeetCode description HTML and converts it to Telegram-friendly HTML.
    Strips unsupported HTML tags, handles basic lists/paragraphs, and safely truncates if needed.
    """
    if not html_content:
        return ""
    parser = TelegramHTMLParser(max_length=max_length)
    parser.feed(html_content)
    return parser.get_result()

def escape_html(text: str) -> str:
    """
    Escapes HTML special characters in plain text.
    """
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_markdown_to_html(text: str) -> str:
    """
    Safely converts basic markdown (*, **, `, ```) to Telegram-compatible HTML.
    Escapes all other HTML characters to prevent parsing errors.
    """
    if not text:
        return ""
    
    # 1. Escape all HTML special characters
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # 2. Extract and safeguard code blocks to prevent formatting inside them
    code_blocks = []
    def save_code_block(match):
        code_blocks.append(match.group(2))
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"
    
    escaped = re.sub(r'```(\w*)\n(.*?)\n?```', save_code_block, escaped, flags=re.DOTALL)
    
    # 3. Extract and safeguard inline code
    inline_codes = []
    def save_inline_code(match):
        inline_codes.append(match.group(1))
        return f"__INLINE_CODE_{len(inline_codes)-1}__"
        
    escaped = re.sub(r'`([^`\n]+)`', save_inline_code, escaped)
    
    # 4. Convert bold (**text**) safely
    escaped = re.sub(r'\*\*([^\s*](?:[^*]*[^\s*])?)\*\*', r'<b>\1</b>', escaped)
    
    # 5. Convert italic (*text*) safely
    escaped = re.sub(r'\*([^\s*](?:[^*]*[^\s*])?)\*', r'<i>\1</i>', escaped)
    
    # 6. Convert italic (_text_) safely
    escaped = re.sub(r'(?<!\w)_([^\s_](?:[^_]*[^\s_])?)_(?!\w)', r'<i>\1</i>', escaped)
    
    # 7. Restore inline code wrapped in <code>
    for i, code_content in enumerate(inline_codes):
        escaped = escaped.replace(f"__INLINE_CODE_{i}__", f"<code>{code_content}</code>")
        
    # 8. Restore code blocks wrapped in <pre><code>
    for i, code_content in enumerate(code_blocks):
        escaped = escaped.replace(f"__CODE_BLOCK_{i}__", f"<pre><code>{code_content}</code></pre>")
        
    return escaped


