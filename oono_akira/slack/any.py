from typing import Mapping, Sequence

AnyObject = Mapping[str, str | int | "AnyObject" | Sequence["AnyObject"]]
