from typing import Any, Dict, Optional, List, Self
from dataclasses import dataclass, field

AnyObject = Dict[str, Any]


@dataclass
class RichTextStyle:
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    strike: Optional[bool] = None
    code: Optional[bool] = None


@dataclass
class RichTextSpan:
    type: str
    text: Optional[str] = None
    style: Optional[RichTextStyle] = None
    name: Optional[str] = None
    unicode: Optional[str] = None
    skin_tone: Optional[int] = None


@dataclass
class RichTextElement:
    type: str
    elements: "List[RichTextSpan | RichTextElement]" = field(
        metadata={
            ("type", "rich_text_section"): RichTextSpan,
            ("type", "rich_text_quote"): RichTextSpan,
            ("type", "rich_text_preformatted"): RichTextSpan,
            ("type", "rich_text_list"): Self,
        }
    )
    style: Optional[str] = None
    indent: Optional[int] = None
    border: Optional[int] = None


@dataclass
class Block:
    type: str
    elements: Optional[List[RichTextElement]] = field(
        default=None,
        metadata={
            ("type", "rich_text"): RichTextElement,
        },
    )
    block_id: Optional[str] = None
