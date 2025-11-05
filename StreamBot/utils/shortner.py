"""
StreamBot/utils/shortner.py
URL shortener utility using direct HTTP requests to GPLinks API.
"""
import logging
import asyncio
import urllib.parse
import aiohttp

logger = logging.getLogger(__name__)

class URLShortener:
    """
    URL Shortener using direct HTTP requests to GPLinks API.
    """

    def __init__(self, adlinkfly_url=None):
        """
        Initialize the URL shortener by parsing the adlinkfly URL.

        Args:
            adlinkfly_url (str, optional): Full API URL with API key, defaults to value from config.
        """
        from StreamBot.config import Var

        self.adlinkfly_url = adlinkfly_url or Var.ADLINKFLY_URL
        self.api_key = None
        self.base_url = None
        self._session = None

        self._parse_adlinkfly_url()

    def _parse_adlinkfly_url(self):
        """Parse the adlinkfly URL to extract API key and base URL."""
        try:
            # Strip any leading/trailing whitespace from the URL
            clean_url = self.adlinkfly_url.strip()
            
            parsed_url = urllib.parse.urlparse(clean_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)

            # Extract API key from query parameters
            self.api_key = query_params.get('api', [None])[0]

            # Build the base URL for API requests
            self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"

            if not self.api_key:
                logger.warning("No API key found in ADLINKFLY_URL. URL shortening will be disabled.")
                return

            logger.info(f"URL Shortener initialized successfully")
            logger.info(f"Base URL: {self.base_url}")
            logger.info(f"API Key: {self.api_key[:8]}...")

        except Exception as e:
            logger.error(f"Failed to parse ADLINKFLY_URL: {e}")
            self.api_key = None

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def shorten_url(self, long_url, alias=None):
        """
        Shortens a given URL using the GPLinks API.

        Args:
            long_url (str): The original URL to be shortened.
            alias (str, optional): Custom alias for the shortened URL.

        Returns:
            str or None: The shortened URL if successful, None otherwise.
        """
        if not self.api_key or not self.base_url:
            logger.warning("URL shortening is disabled due to missing API key or base URL.")
            return None

        try:
            session = await self._get_session()

            # Build the request parameters
            params = {
                'api': self.api_key,
                'url': long_url
            }

            # Add alias if provided
            if alias:
                params['alias'] = alias

            logger.debug(f"Shortening URL: {long_url}")

            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    if data.get("status") == "success":
                        shortened_url = data.get("shortenedUrl")
                        if shortened_url:
                            logger.info(f"URL shortened successfully: {long_url} -> {shortened_url}")
                            return shortened_url
                        else:
                            logger.error("GPLinks API returned success but no shortenedUrl")
                            return None
                    else:
                        logger.error(f"GPLinks API error: {data.get('message', 'Unknown error')}")
                        return None
                else:
                    logger.error(f"GPLinks API HTTP error: {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Error shortening URL: {e}", exc_info=True)
            return None
    
    async def should_use_short_url(self, file_size):
        """
        Determines if a file should use a shortened URL based on its size.

        Args:
            file_size (int): Size of the file in bytes.

        Returns:
            bool: True if the file size exceeds the threshold, False otherwise.
        """
        from StreamBot.config import Var

        # Check if URL shortening is enabled
        if not self.api_key or not self.base_url:
            return False

        # Check if file size exceeds threshold
        return file_size > Var.FILE_SIZE_THRESHOLD

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

# Create a global instance
url_shortener = URLShortener()
