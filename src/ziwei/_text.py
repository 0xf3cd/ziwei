"""出生文字与 JSON 记录共用的字符保全边界。"""

import re


def _check_json_text(value: str) -> None:
  """拒绝 JSON 解码会合并的相邻高低代理码点，其他字符原样保留。"""
  if re.search("[\ud800-\udbff][\udc00-\udfff]", value):
    raise ValueError("文字不得包含相邻的高低代理码点对")
