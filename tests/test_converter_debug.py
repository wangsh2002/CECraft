
import json
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.services.format_converter import delta_to_markdown, markdown_to_delta

def test_converter():
    print("--- Testing Markdown -> Delta -> Markdown ---")
    md_input = """# Title
    
- List item 1
- List item 2

**Bold text** and normal text.
"""
    print(f"Input Markdown:\n{md_input}")
    
    delta_json = markdown_to_delta(md_input)
    print(f"\nGenerated Delta JSON (Snippet): {delta_json[:200]}...")
    
    # Check ORIGIN_DATA presence
    delta_dict = json.loads(delta_json)
    first_key = list(delta_dict.keys())[0]
    origin_data = delta_dict[first_key]["attrs"].get("ORIGIN_DATA")
    if origin_data:
        print(f"\n✅ ORIGIN_DATA generated: {origin_data[:100]}...")
    else:
        print("\n❌ ORIGIN_DATA missing!")

    md_output = delta_to_markdown(delta_dict)
    print(f"\nRestored Markdown:\n{md_output}")
    
    if not md_output.strip():
        print("❌ Error: Restored Markdown is empty!")
    else:
        print("✅ Markdown restored successfully.")

    print("\n--- Testing Delta Dict Input ---")
    # Simulate frontend input structure
    frontend_delta = {
        "delta-1": {
            "key": "text",
            "x": 10, "y": 10, "width": 100, "height": 20,
            "attrs": {
                "DATA": json.dumps([
                    {"chars": [{"char": "H", "config": {}}, {"char": "i", "config": {}}], "config": {}}
                ])
            }
        }
    }
    md_output_2 = delta_to_markdown(frontend_delta)
    print(f"Restored Markdown from Dict: {md_output_2}")
    
    if md_output_2.strip() == "Hi":
        print("✅ Dict input handled correctly.")
    else:
        print(f"❌ Error: Expected 'Hi', got '{md_output_2}'")

    print("\n--- Testing BlockKit Delta Input ---")
    blockkit_delta = {
        "ops": [
            { "insert": "Hello " },
            { "insert": "World", "attributes": { "bold": True } },
            { "insert": "\n" }
        ]
    }
    md_output_3 = delta_to_markdown(blockkit_delta)
    print(f"Restored Markdown from BlockKit: {md_output_3}")
    if "**World**" in md_output_3:
        print("✅ BlockKit input handled correctly.")
    else:
        print(f"❌ Error: Expected '**World**' in output")

    print("\n--- Testing Color Parsing ---")
    color_md = 'Text with <span style="color: red">Red Color</span> and <font color="blue">Blue Color</font>.'
    delta_color = markdown_to_delta(color_md)
    print(f"Color Delta: {delta_color}")
    
    # Check if color attribute is present in delta
    if '"COLOR": "red"' in delta_color or '"color": "red"' in delta_color:
        print("✅ Red color parsed correctly.")
    else:
        print("❌ Red color parsing failed.")
        
    if '"COLOR": "blue"' in delta_color or '"color": "blue"' in delta_color:
        print("✅ Blue color parsed correctly.")
    else:
        print("❌ Blue color parsing failed.")

if __name__ == "__main__":
    test_converter()
