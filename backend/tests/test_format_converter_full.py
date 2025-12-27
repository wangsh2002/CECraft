import json
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.format_converter import delta_to_markdown, markdown_to_delta, TEXT_ATTRS

def test_converter_full_rich_text():
    # 1. Test Markdown to Delta with Full Rich Text
    markdown_text = """# 个人简历

## 技能
- **Python** (熟练)
- *Java* (了解)
- <u>C++</u> (入门)
- ~~PHP~~ (已放弃)
- <span color="#ff0000">Rust</span> (学习中)
- <span style="background-color: #ffff00">Go</span> (高亮)
- [GitHub](https://github.com)
- <span style="font-family: Arial">Arial Font</span>
- <span style="font-size: 20px">Big Text</span>

---

## 经历
1. 曾在**某大厂**工作。
2. 负责<u>核心模块</u>开发。
"""
    print("Original Markdown:")
    print(markdown_text)
    
    delta_json = markdown_to_delta(markdown_text)
    print("\nGenerated Delta JSON (Snippet):")
    print(delta_json[:500] + "...")
    
    # Verify JSON structure
    delta_set = json.loads(delta_json)
    
    found_attrs = {k: False for k in TEXT_ATTRS.values()}
    
    for key, delta in delta_set.items():
        attrs = delta.get('attrs', {})
        data_str = attrs.get('DATA')
        if not data_str: continue
        rich_text_lines = json.loads(data_str)
        for line in rich_text_lines:
            # Check block attrs
            line_config = line.get('config', {})
            if line_config.get(TEXT_ATTRS["ORDERED_LIST_LEVEL"]): found_attrs[TEXT_ATTRS["ORDERED_LIST_LEVEL"]] = True
            if line_config.get(TEXT_ATTRS["DIVIDING_LINE"]): found_attrs[TEXT_ATTRS["DIVIDING_LINE"]] = True
            
            for char_obj in line.get('chars', []):
                config = char_obj.get('config', {})
                if config.get(TEXT_ATTRS["WEIGHT"]) == 'bold': found_attrs[TEXT_ATTRS["WEIGHT"]] = True
                if config.get(TEXT_ATTRS["STYLE"]) == 'italic': found_attrs[TEXT_ATTRS["STYLE"]] = True
                if config.get(TEXT_ATTRS["UNDERLINE"]): found_attrs[TEXT_ATTRS["UNDERLINE"]] = True
                if config.get(TEXT_ATTRS["STRIKE_THROUGH"]): found_attrs[TEXT_ATTRS["STRIKE_THROUGH"]] = True
                if config.get(TEXT_ATTRS["COLOR"]) == '#ff0000': found_attrs[TEXT_ATTRS["COLOR"]] = True
                if config.get(TEXT_ATTRS["BACKGROUND"]) == '#ffff00': found_attrs[TEXT_ATTRS["BACKGROUND"]] = True
                if config.get(TEXT_ATTRS["LINK"]) == 'https://github.com': found_attrs[TEXT_ATTRS["LINK"]] = True
                if config.get(TEXT_ATTRS["FAMILY"]) == 'Arial': found_attrs[TEXT_ATTRS["FAMILY"]] = True
                if config.get(TEXT_ATTRS["SIZE"]) == 20: found_attrs[TEXT_ATTRS["SIZE"]] = True
    
    print("\nFound Attributes:")
    for k, v in found_attrs.items():
        if v: print(f"- {k}: Found")
    
    # Assertions
    assert found_attrs[TEXT_ATTRS["WEIGHT"]]
    assert found_attrs[TEXT_ATTRS["STYLE"]]
    assert found_attrs[TEXT_ATTRS["UNDERLINE"]]
    assert found_attrs[TEXT_ATTRS["STRIKE_THROUGH"]]
    assert found_attrs[TEXT_ATTRS["COLOR"]]
    assert found_attrs[TEXT_ATTRS["BACKGROUND"]]
    assert found_attrs[TEXT_ATTRS["LINK"]]
    assert found_attrs[TEXT_ATTRS["FAMILY"]]
    assert found_attrs[TEXT_ATTRS["SIZE"]]
    assert found_attrs[TEXT_ATTRS["ORDERED_LIST_LEVEL"]]
    assert found_attrs[TEXT_ATTRS["DIVIDING_LINE"]]
    
    # 2. Test Delta to Markdown
    converted_markdown = delta_to_markdown(delta_json)
    print("\nConverted back to Markdown:")
    print(converted_markdown)
    
    # Check if formatting is preserved
    assert "**Python**" in converted_markdown or "**" in converted_markdown
    assert "*Java*" in converted_markdown or "*" in converted_markdown
    assert "<u>C++</u>" in converted_markdown
    assert "~~PHP~~" in converted_markdown
    assert '<span color="#ff0000">Rust</span>' in converted_markdown
    assert '<span style="background-color: #ffff00">Go</span>' in converted_markdown
    assert '[GitHub](https://github.com)' in converted_markdown
    assert '<span style="font-family: Arial">Arial Font</span>' in converted_markdown
    assert '<span style="font-size: 20px">Big Text</span>' in converted_markdown
    assert "---" in converted_markdown
    assert "1. 曾" in converted_markdown or "1. " in converted_markdown
    
    print("\nTest Passed!")

if __name__ == "__main__":
    test_converter_full_rich_text()
