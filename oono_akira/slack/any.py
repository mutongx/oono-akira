from typing import Mapping, List

AnyObject = Mapping[str, str | int | "AnyObject" | List["AnyObject"]]
