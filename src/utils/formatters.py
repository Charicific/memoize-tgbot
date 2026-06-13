import re
from html.parser import HTMLParser
from io import StringIO

class TelegramHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.output = StringIO()
        self.supported_tags = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a"}
        self.active_tags = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "p":
            self.output.write("\n")
        elif tag == "br":
            self.output.write("\n")
        elif tag == "li":
            self.output.write("• ")
        elif tag in self.supported_tags:
            # Reconstruct tag with attributes if any (like href for <a>)
            attr_str = ""
            if tag == "a":
                href = next((val for name, val in attrs if name == "href"), None)
                if href:
                    attr_str = f' href="{href}"'
            self.output.write(f"<{tag}{attr_str}>")
            self.active_tags.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.supported_tags and tag in self.active_tags:
            self.output.write(f"</{tag}>")
            self.active_tags.remove(tag)
        elif tag == "p":
            self.output.write("\n")
        elif tag == "li":
            self.output.write("\n")

    def handle_data(self, data):
        # Escape HTML special characters inside raw text, but only if they are not already tags
        escaped_data = data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.output.write(escaped_data)

    def get_result(self) -> str:
        text = self.output.getvalue()
        # Clean up consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

def clean_leetcode_html(html_content: str) -> str:
    """
    Parses LeetCode description HTML and converts it to Telegram-friendly HTML.
    Strips unsupported HTML tags and handles basic lists and paragraphs.
    """
    if not html_content:
        return ""
    parser = TelegramHTMLParser()
    parser.feed(html_content)
    return parser.get_result()

def escape_html(text: str) -> str:
    """
    Escapes HTML special characters in plain text.
    """
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
