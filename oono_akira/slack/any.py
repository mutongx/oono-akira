from typing import Mapping, Sequence, Union

AnyValue = Union[str, int, "AnyObject", Sequence["AnyObject"]]
AnyObject = Mapping[str, AnyValue]
