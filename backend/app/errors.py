class NoMaterialError(Exception):
    """Raised when an agent needs course material but the course has none yet."""

    def __init__(self, message: str = "Upload course material before using this feature."):
        super().__init__(message)
        self.message = message
