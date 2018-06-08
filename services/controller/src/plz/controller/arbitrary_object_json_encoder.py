import flask


class ArbitraryObjectJSONEncoder(flask.json.JSONEncoder):
    """
    This encoder tries very hard to encode any kind of object. It uses the
     object's ``__dict__`` property if the object itself is not encodable.
    """
    def default(self, o):
        try:
            return super().default(o)
        except TypeError:
            return o.__dict__


def dumps_arbitrary_json(o) -> str:
    return ArbitraryObjectJSONEncoder().encode(o)
