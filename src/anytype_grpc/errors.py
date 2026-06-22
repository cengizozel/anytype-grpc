"""Error types for anytype-grpc."""


class AnytypeError(Exception):
    """Base error for this library (bad arguments, unknown method, and so on)."""


class RpcError(AnytypeError):
    """Raised when an Anytype RPC returns a non-NULL error code.

    Most Anytype responses carry an ``error`` field with a ``code`` enum where
    ``0`` means success. When ``check=True`` (the default), the client raises
    this with the method name, the numeric code, and the server description.

    Attributes:
        method: the RPC method name that failed (for example "BlockCreate").
        code: the numeric error code from the response.
        description: the human-readable description from the server.
    """

    def __init__(self, method, code, description):
        self.method = method
        self.code = code
        self.description = description
        super().__init__(f"{method} failed (code {code}): {description}")
