import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from ratelimit import RateLimiter

def create_http_client():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

class RateLimitedClient:
    def __init__(self, requests_per_minute: int = 60):
        self.session = create_http_client()
        self.rate_limit = RateLimiter(requests_per_minute)

    async def get(self, url: str, **kwargs) -> requests.Response:
        async with self.rate_limit:
            return await self.session.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> requests.Response:
        async with self.rate_limit:
            return await self.session.post(url, **kwargs)
