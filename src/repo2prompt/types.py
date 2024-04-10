from datetime import datetime
import time
class RateLimitExceeded(Exception):
    """
    Exception raised when the rate limit is exceeded
    """
    def __init__(self):
        future_time = int(time.time()) + 60*60
        super().__init__(f"Rate limit exceeded. Please wait until {datetime.fromtimestamp(future_time)} to try again.")

