from typing import Mapping, Sequence, Union

AnyObject = Mapping[str, Union[str, int, 'AnyObject', Sequence['AnyObject']]]
