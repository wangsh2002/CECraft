import json
import uuid
import math
import re
from typing import Dict, Any, List, Optional

# Constants from frontend
TEXT_ATTRS = {
    "DATA": "DATA",
    "ORIGIN_DATA": "ORIGIN_DATA",
    "LINE_HEIGHT": "LINE_HEIGHT",
    "ORDERED_LIST_LEVEL": "ORDERED_LIST_LEVEL",
    "ORDERED_LIST_START": "ORDERED_LIST_START",
    "UNORDERED_LIST_LEVEL": "UNORDERED_LIST_LEVEL",
    "DIVIDING_LINE": "DIVIDING_LINE",
    "BREAK_LINE_START": "BREAK_LINE_START",
    "SIZE": "SIZE",
    "LINK": "LINK",
    "STYLE": "STYLE",
    "COLOR": "COLOR",
    "FAMILY": "FAMILY",
    "WEIGHT": "WEIGHT",
    "UNDERLINE": "UNDERLINE",
    "BACKGROUND": "BACKGROUND",
    "STRIKE_THROUGH": "STRIKE_THROUGH",
}

def delta_to_markdown(delta_set_input: str | Dict[str, Any]) -> str:
    """
    Convert DeltaSet JSON to Markdown, supporting all frontend rich text attributes.
    """
    if isinstance(delta_set_input, str):
        try:
            delta_set = json.loads(delta_set_input)
        except json.JSONDecodeError:
            return delta_set_input
    else:
        delta_set = delta_set_input

    if not isinstance(delta_set, dict):
        return str(delta_set)

    # Check if input is a BlockKit Delta ({ "ops": [...] })
    if "ops" in delta_set and isinstance(delta_set["ops"], list):
        # Convert BlockKit Delta ops to Markdown directly
        return _ops_to_markdown(delta_set["ops"])

    text_deltas = []
    for key, delta in delta_set.items():
        if isinstance(delta, dict) and delta.get('key') == 'text':
            text_deltas.append(delta)
    
    text_deltas.sort(key=lambda d: d.get('y', 0))
    
    markdown_lines = []
    for delta in text_deltas:
        attrs = delta.get('attrs', {})
        # Try to get data from DATA or ORIGIN_DATA
        data_str = attrs.get('DATA') or attrs.get('ORIGIN_DATA')
        
        if not data_str:
            # Fallback: check if 'data' key exists directly in delta (unlikely but possible in some versions)
            data_str = delta.get('data')
            
        if not data_str:
            continue
            
        try:
            if isinstance(data_str, str):
                rich_text_lines = json.loads(data_str)
            else:
                rich_text_lines = data_str
        except json.JSONDecodeError:
            continue
            
        if not isinstance(rich_text_lines, list):
            continue

        for line in rich_text_lines:
            # Check if it's Slate format (ORIGIN_DATA) or RichTextLines (DATA)
            if "children" in line:
                # --- Slate Format Handling ---
                # Example: {"children": [{"text": "Hello", "bold": true}]}
                # We need to convert this to Markdown manually or map to our structure
                # For simplicity, let's extract text and basic styles
                
                # Block level (simplified, as Slate structure might be nested differently)
                # Assuming flat list of blocks for now based on observed ORIGIN_DATA
                prefix = ""
                # TODO: Handle block types if present in Slate data (e.g. type: 'list-item')
                
                line_md = prefix
                children = line.get("children", [])
                for child in children:
                    text = child.get("text", "")
                    if not text: continue
                    
                    # Apply styles
                    if child.get("bold") or child.get("WEIGHT") == "bold":
                        text = f"**{text}**"
                    if child.get("italic") or child.get("STYLE") == "italic":
                        text = f"*{text}*"
                    if child.get("underline") or child.get("UNDERLINE"):
                        text = f"<u>{text}</u>"
                    if child.get("strikethrough") or child.get("STRIKE_THROUGH"):
                        text = f"~~{text}~~"
                    
                    line_md += text
                
                markdown_lines.append(line_md)
                continue

            # --- RichTextLines Format Handling (DATA) ---
            line_config = line.get('config', {})
            chars = line.get('chars', [])
            
            # Handle Block Attributes
            prefix = ""
            if line_config.get(TEXT_ATTRS["DIVIDING_LINE"]):
                markdown_lines.append("---")
                continue
                
            if line_config.get(TEXT_ATTRS["ORDERED_LIST_LEVEL"]):
                level = int(line_config.get(TEXT_ATTRS["ORDERED_LIST_LEVEL"], 1))
                start = line_config.get(TEXT_ATTRS["ORDERED_LIST_START"], 1)
                indent = "   " * (level - 1)
                prefix = f"{indent}{start}. "
            elif line_config.get(TEXT_ATTRS["UNORDERED_LIST_LEVEL"]):
                level = int(line_config.get(TEXT_ATTRS["UNORDERED_LIST_LEVEL"], 1))
                indent = "   " * (level - 1)
                prefix = f"{indent}- "
            
            line_md = prefix
            current_config = {}
            
            # Group characters by config to handle links and styles efficiently
            grouped_chars = []
            if chars:
                current_group = {"text": chars[0].get('char', ''), "config": chars[0].get('config', {})}
                for i in range(1, len(chars)):
                    char_obj = chars[i]
                    config = char_obj.get('config', {})
                    # Check if config is same
                    if config == current_group['config']:
                        current_group['text'] += char_obj.get('char', '')
                    else:
                        grouped_chars.append(current_group)
                        current_group = {"text": char_obj.get('char', ''), "config": config}
                grouped_chars.append(current_group)
            
            for group in grouped_chars:
                text = group['text']
                config = group['config']
                
                # Normalize NBSP to normal space for Markdown compatibility
                # This ensures LLM sees normal spaces and can preserve them
                text = text.replace('\u00A0', ' ')
                
                # Apply styles
                # Link wrapper
                if config.get(TEXT_ATTRS["LINK"]):
                    text = f"[{text}]({config[TEXT_ATTRS['LINK']]})"
                
                # Inline styles
                if config.get(TEXT_ATTRS["WEIGHT"]) == "bold":
                    text = f"**{text}**"
                if config.get(TEXT_ATTRS["STYLE"]) == "italic":
                    text = f"*{text}*"
                if config.get(TEXT_ATTRS["UNDERLINE"]):
                    text = f"<u>{text}</u>"
                if config.get(TEXT_ATTRS["STRIKE_THROUGH"]):
                    text = f"~~{text}~~"
                if config.get(TEXT_ATTRS["COLOR"]):
                    text = f'<span style="color: {config[TEXT_ATTRS["COLOR"]]}">{text}</span>'
                if config.get(TEXT_ATTRS["BACKGROUND"]):
                    text = f'<span style="background-color: {config[TEXT_ATTRS["BACKGROUND"]]}">{text}</span>'
                if config.get(TEXT_ATTRS["FAMILY"]):
                    text = f'<span style="font-family: {config[TEXT_ATTRS["FAMILY"]]}">{text}</span>'
                if config.get(TEXT_ATTRS["SIZE"]):
                    # Only apply size if it's not a heading size implied by context (simplified)
                    text = f'<span style="font-size: {config[TEXT_ATTRS["SIZE"]]}px">{text}</span>'
                    
                line_md += text
            
            markdown_lines.append(line_md)
        
    return "\n\n".join(markdown_lines)

def _ops_to_markdown(ops: List[Dict[str, Any]]) -> str:
    """
    Convert BlockKit Delta ops to Markdown.
    """
    markdown_text = ""
    for op in ops:
        insert = op.get("insert")
        if not isinstance(insert, str):
            continue
            
        attributes = op.get("attributes", {})
        text = insert
        
        # Apply inline styles
        if attributes.get("bold"):
            text = f"**{text}**"
        if attributes.get("italic"):
            text = f"*{text}*"
        if attributes.get("underline"):
            text = f"<u>{text}</u>"
        if attributes.get("strike"):
            text = f"~~{text}~~"
        if attributes.get("link"):
            text = f"[{text}]({attributes['link']})"
            
        # Handle block attributes (simplified)
        # BlockKit usually puts block attributes on the newline character
        if insert == "\n":
            if attributes.get("header"):
                level = attributes["header"]
                markdown_text += "#" * level + " "
            elif attributes.get("list") == "ordered":
                # This is tricky because we need to know the number. 
                # Simplified: just use 1. for now, markdown renderers usually fix it
                markdown_text = markdown_text.rstrip() + "\n1. " 
                continue # Skip appending the newline char itself if we handled it
            elif attributes.get("list") == "bullet":
                markdown_text = markdown_text.rstrip() + "\n- "
                continue
                
        markdown_text += text
        
    return markdown_text

def parse_inline_styles(text: str, base_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse Markdown/HTML mixed text into chars with config.
    Supports: **Bold**, *Italic*, <u>Underline</u>, ~~Strike~~, [Link](url), <span> styles.
    """
    # This is a simplified parser. For production, a proper AST parser is better.
    # We will use a regex-based tokenizer.
    
    # Tokens:
    # ** -> Bold
    # * -> Italic
    # <u>, </u> -> Underline
    # ~~ -> Strike
    # <span ...>, </span> -> Span attributes
    # [text](url) -> Link (Special handling)
    
    chars_data = []
    
    # Regex for Link: \[([^\]]+)\]\(([^)]+)\)
    # We process links first as they contain other text
    
    # To avoid complex recursion, we'll process sequentially.
    # Current state
    state = {
        "bold": False,
        "italic": False,
        "underline": False,
        "strike": False,
        "color": None,
        "background": None,
        "fontSize": None,
        "fontFamily": None,
        "link": None
    }
    
    # Helper to apply state to config
    def get_config():
        cfg = base_config.copy()
        if state["bold"]: cfg[TEXT_ATTRS["WEIGHT"]] = "bold"
        if state["italic"]: cfg[TEXT_ATTRS["STYLE"]] = "italic"
        if state["underline"]: cfg[TEXT_ATTRS["UNDERLINE"]] = "true"
        if state["strike"]: cfg[TEXT_ATTRS["STRIKE_THROUGH"]] = "true"
        if state["color"]: cfg[TEXT_ATTRS["COLOR"]] = state["color"]
        if state["background"]: cfg[TEXT_ATTRS["BACKGROUND"]] = state["background"]
        if state["fontSize"]: cfg[TEXT_ATTRS["SIZE"]] = state["fontSize"]
        if state["fontFamily"]: cfg[TEXT_ATTRS["FAMILY"]] = state["fontFamily"]
        if state["link"]: cfg[TEXT_ATTRS["LINK"]] = state["link"]
        return cfg

    # Regex to split text into tokens
    # Note: This regex is greedy and might fail on nested same-tags, but works for standard LLM output.
    # Added Link regex and Font tag
    token_pattern = re.compile(
        r'(\*\*|'  # Bold
        r'\*|'     # Italic
        r'<u>|</u>|' # Underline
        r'~~|'     # Strike
        r'<span[^>]*>|</span>|' # Span
        r'<font[^>]*>|</font>|' # Font
        r'\[[^\]]+\]\([^)]+\))' # Link
    )
    
    parts = token_pattern.split(text)
    
    for part in parts:
        if not part: continue
        
        if part == '**':
            state["bold"] = not state["bold"]
        elif part == '*':
            state["italic"] = not state["italic"]
        elif part == '<u>':
            state["underline"] = True
        elif part == '</u>':
            state["underline"] = False
        elif part == '~~':
            state["strike"] = not state["strike"]
        elif part.startswith('<span'):
            # Parse attributes
            # color="..." (Non-standard but supported)
            c_m = re.search(r'color="([^"]+)"', part)
            if c_m: state["color"] = c_m.group(1)
            
            # style="..."
            s_m = re.search(r'style="([^"]+)"', part)
            if s_m:
                style_content = s_m.group(1)
                # color
                c_style_m = re.search(r'color:\s*([^;]+)', style_content)
                if c_style_m: state["color"] = c_style_m.group(1).strip()
                # background-color
                bg_m = re.search(r'background-color:\s*([^;]+)', style_content)
                if bg_m: state["background"] = bg_m.group(1).strip()
                # font-size
                fs_m = re.search(r'font-size:\s*(\d+)px', style_content)
                if fs_m: state["fontSize"] = int(fs_m.group(1))
                # font-family
                ff_m = re.search(r'font-family:\s*([^;]+)', style_content)
                if ff_m: state["fontFamily"] = ff_m.group(1).strip()
                
        elif part == '</span>':
            # Reset span attributes (Simplified: resets all span-related)
            state["color"] = None
            state["background"] = None
            state["fontSize"] = None
            state["fontFamily"] = None
            
        elif part.startswith('<font'):
            # Parse font attributes
            # color="..."
            c_m = re.search(r'color="([^"]+)"', part)
            if c_m: state["color"] = c_m.group(1)
            
        elif part == '</font>':
            state["color"] = None
            
        elif part.startswith('[') and '](' in part and part.endswith(')'):
            # Link: [text](url)
            m = re.match(r'\[([^\]]+)\]\(([^)]+)\)', part)
            if m:
                link_text = m.group(1)
                link_url = m.group(2)
                # Recursively parse the text inside the link, but with link state set
                old_link = state["link"]
                state["link"] = link_url
                # Recurse for inner styles
                # Note: parse_inline_styles returns chars with config. We need to merge current state.
                # But parse_inline_styles starts with base_config.
                # We should pass current state as base_config?
                # Yes, but base_config is dict.
                # Let's construct a temporary base config from current state
                temp_base = get_config()
                inner_chars = parse_inline_styles(link_text, temp_base)
                chars_data.extend(inner_chars)
                
                state["link"] = old_link
        else:
            # Plain text
            for char in part:
                chars_data.append({
                    "char": char,
                    "config": get_config()
                })
                
    return chars_data

def markdown_to_delta(markdown_text: str) -> str:
    """
    Convert Markdown to DeltaSet JSON.
    """
    PAGE_WIDTH = 800
    MARGIN_X = 40
    START_Y = 40
    LINE_HEIGHT = 24
    FONT_SIZE = 14
    CHARS_PER_LINE = int((PAGE_WIDTH - 2 * MARGIN_X) / FONT_SIZE * 1.5)
    
    delta_set = {}
    current_y = START_Y
    
    # Split by newline to handle lists and headings correctly
    # We treat each line as a potential separate block
    lines = markdown_text.split('\n')
    
    for p in lines:
        # Skip empty lines (but allow lines with just spaces if they are relevant? 
        # Usually empty lines in markdown are just spacing. 
        # If we want to preserve vertical spacing, we should keep them.
        # But the original code did `if not p: continue` after strip.
        # Let's stick to ignoring purely empty/whitespace lines for now to avoid excessive vertical space,
        # or we can allow them. Standard markdown ignores multiple newlines.
        if not p.strip(): 
            continue
        
        p_rstripped = p.rstrip()
        p_stripped = p.strip()
        
        # Line Config
        line_config = {}
        content = p_rstripped
        
        # Dividing Line
        if p_stripped == '---' or p_stripped == '***':
            line_config[TEXT_ATTRS["DIVIDING_LINE"]] = "true"
            content = ""
            height = 10
        else:
            # Headings
            if p_stripped.startswith('# '):
                line_config[TEXT_ATTRS["SIZE"]] = 24
                line_config[TEXT_ATTRS["WEIGHT"]] = "bold"
                content = p_stripped[2:]
            elif p_stripped.startswith('## '):
                line_config[TEXT_ATTRS["SIZE"]] = 20
                line_config[TEXT_ATTRS["WEIGHT"]] = "bold"
                content = p_stripped[3:]
            elif p_stripped.startswith('### '):
                line_config[TEXT_ATTRS["SIZE"]] = 18
                line_config[TEXT_ATTRS["WEIGHT"]] = "bold"
                content = p_stripped[4:]
            
            # Lists
            # Use p_rstripped to preserve indentation for regex matching
            else:
                m_ol = re.match(r'^(\s*)(\d+)\.\s(.*)', p_rstripped)
                m_ul = re.match(r'^(\s*)-\s(.*)', p_rstripped)
                
                if m_ol:
                    indent = m_ol.group(1)
                    start = m_ol.group(2)
                    content = m_ol.group(3)
                    level = len(indent) // 3 + 1 # Assume 3 spaces per level
                    line_config[TEXT_ATTRS["ORDERED_LIST_LEVEL"]] = str(level)
                    line_config[TEXT_ATTRS["ORDERED_LIST_START"]] = start
                elif m_ul:
                    indent = m_ul.group(1)
                    content = m_ul.group(2)
                    level = len(indent) // 3 + 1
                    line_config[TEXT_ATTRS["UNORDERED_LIST_LEVEL"]] = str(level)

            # Calculate height
            lines_count = math.ceil(len(content) / CHARS_PER_LINE) if content else 1
            if lines_count < 1: lines_count = 1
            base_height = line_config.get(TEXT_ATTRS["SIZE"], FONT_SIZE) + 10
            height = lines_count * base_height

        # Preserve consecutive spaces for frontend rendering
        # Replace double spaces with " \u00A0" (Space + No-Break Space)
        # This ensures that multiple spaces are not collapsed by HTML renderers
        if content:
            while "  " in content:
                content = content.replace("  ", " \u00A0")

        # Parse Inline Styles
        chars_data = parse_inline_styles(content, line_config)
        
        # Construct RichTextLine
        # Note: line_config goes to the line object, chars have their own config
        # But in our parser, we merged line_config into chars config for simplicity in rendering?
        # No, frontend separates them.
        # line.config has block attributes. chars.config has inline attributes.
        # We need to separate them.
        
        # Filter block attributes from char config
        block_keys = [
            TEXT_ATTRS["LINE_HEIGHT"], TEXT_ATTRS["ORDERED_LIST_LEVEL"], TEXT_ATTRS["ORDERED_LIST_START"],
            TEXT_ATTRS["UNORDERED_LIST_LEVEL"], TEXT_ATTRS["DIVIDING_LINE"], TEXT_ATTRS["BREAK_LINE_START"]
        ]
        
        final_chars = []
        for c in chars_data:
            char_cfg = c['config'].copy()
            # Remove block keys from char config if present (they shouldn't be if we did it right, but safety)
            for k in block_keys:
                if k in char_cfg: del char_cfg[k]
            final_chars.append({"char": c['char'], "config": char_cfg})
            
        rich_text_lines = [{"chars": final_chars, "config": line_config}]
        
        # --- Generate ORIGIN_DATA (Slate Format) ---
        slate_children = []
        if final_chars:
            current_leaf = {"text": final_chars[0]["char"]}
            last_config = final_chars[0]["config"]
            
            def map_config(cfg):
                attrs = {}
                if cfg.get(TEXT_ATTRS["WEIGHT"]) == "bold": attrs["bold"] = True
                if cfg.get(TEXT_ATTRS["STYLE"]) == "italic": attrs["italic"] = True
                if cfg.get(TEXT_ATTRS["UNDERLINE"]): attrs["underline"] = True
                if cfg.get(TEXT_ATTRS["STRIKE_THROUGH"]): attrs["strikethrough"] = True
                if cfg.get(TEXT_ATTRS["COLOR"]): attrs["color"] = cfg[TEXT_ATTRS["COLOR"]]
                if cfg.get(TEXT_ATTRS["BACKGROUND"]): attrs["backgroundColor"] = cfg[TEXT_ATTRS["BACKGROUND"]]
                return attrs

            current_leaf.update(map_config(last_config))
            
            for i in range(1, len(final_chars)):
                c = final_chars[i]
                cfg = c["config"]
                if cfg == last_config:
                    current_leaf["text"] += c["char"]
                else:
                    slate_children.append(current_leaf)
                    current_leaf = {"text": c["char"]}
                    current_leaf.update(map_config(cfg))
                    last_config = cfg
            slate_children.append(current_leaf)
        else:
             slate_children.append({"text": ""})

        slate_line = [{"children": slate_children}]

        delta_id = str(uuid.uuid4())
        delta = {
            "id": delta_id,
            "key": "text",
            "x": MARGIN_X,
            "y": current_y,
            "width": PAGE_WIDTH - 2 * MARGIN_X,
            "height": height,
            "attrs": {
                "DATA": json.dumps(rich_text_lines),
                "ORIGIN_DATA": json.dumps(slate_line)
            },
            "children": []
        }
        
        delta_set[delta_id] = delta
        current_y += height + 10
        
    return json.dumps(delta_set)
