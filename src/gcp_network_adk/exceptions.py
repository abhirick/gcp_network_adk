class GcpNetworkAdkError(Exception):
    """Base application exception."""


class ConfigurationError(GcpNetworkAdkError):
    """Raised for invalid local configuration."""


class RecommenderApiError(GcpNetworkAdkError):
    """Raised when the Recommender API call fails."""


class InvalidScanRequestError(GcpNetworkAdkError):
    """Raised when scan request input is invalid."""