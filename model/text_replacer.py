# %% model/text_replacer.py

import re


def find_marker_pairs(text):
    marker_pattern = r"(<-----.*?----->)"
    matches = list(re.finditer(marker_pattern, text, re.DOTALL))
    if len(matches) % 2 != 0:
        print("警告：标记数量为奇数，可能存在未配对的标记。")
        return []

    marker_pairs = []
    for i in range(0, len(matches), 2):
        start_marker = matches[i]
        end_marker = matches[i + 1]
        if start_marker.group(1) != end_marker.group(1):
            print(f"警告：标记对不匹配：{start_marker.group(1)} 和 {end_marker.group(1)}")
            continue
        start_pos = start_marker.end()
        end_pos = end_marker.start()
        content = text[start_pos:end_pos]
        marker_pairs.append(
            {
                "index": i // 2,
                "marker_type": start_marker.group(1),
                "content": content,
                "start": start_marker.start(),
                "end": end_marker.end(),
            }
        )
    return marker_pairs


def replace_contents(text, replacements=None):
    if replacements is None:
        replacements = {}
    marker_pairs = find_marker_pairs(text)
    if not marker_pairs:
        return text

    new_text = text
    offset = 0
    for pair in marker_pairs:
        index = pair["index"]
        if index in replacements:
            new_content = replacements[index]
            marker_type = pair["marker_type"]
            replacement = f"{marker_type}\n{new_content}\n{marker_type}"
            original_length = pair["end"] - pair["start"]
            new_start_pos = pair["start"] + offset
            new_end_pos = pair["end"] + offset
            new_text = new_text[:new_start_pos] + replacement + new_text[new_end_pos:]
            offset += len(replacement) - original_length
    return new_text
