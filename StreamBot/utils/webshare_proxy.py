# StreamBot/utils/webshare_proxy.py
import random
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class WebshareProxyManager:
    """Simple Webshare rotating proxy manager."""
    
    def __init__(self):
        # Free Webshare proxy endpoints (rotating)
        self.proxy_endpoints = [
            "p.webshare.io",
            "proxy.webshare.io", 
            "rotating.webshare.io"
        ]
        self.proxy_port = 80
        self.current_proxy = None
    
    def get_proxy_config(self, username: str = None, password: str = None) -> Optional[Dict]:
        """Get rotating proxy configuration for Pyrogram client."""
        if not username or not password:
            logger.warning("Webshare proxy credentials not provided")
            return None
        
        try:
            # Rotate through different endpoints
            endpoint = random.choice(self.proxy_endpoints)
            
            proxy_config = {
                "scheme": "http",
                "hostname": endpoint,
                "port": self.proxy_port,
                "username": username,
                "password": password
            }
            
            self.current_proxy = endpoint
            logger.info(f"Using Webshare proxy: {endpoint}:{self.proxy_port}")
            
            return proxy_config
            
        except Exception as e:
            logger.error(f"Failed to configure Webshare proxy: {e}")
            return None
    
    def rotate_proxy(self, username: str, password: str) -> Optional[Dict]:
        """Rotate to a different proxy endpoint."""
        available_endpoints = [ep for ep in self.proxy_endpoints if ep != self.current_proxy]
        
        if not available_endpoints:
            # If we've used all, start over
            available_endpoints = self.proxy_endpoints
        
        endpoint = random.choice(available_endpoints)
        
        proxy_config = {
            "scheme": "http", 
            "hostname": endpoint,
            "port": self.proxy_port,
            "username": username,
            "password": password
        }
        
        self.current_proxy = endpoint
        logger.info(f"Rotated to Webshare proxy: {endpoint}:{self.proxy_port}")
        
        return proxy_config

# Global instance
webshare_proxy = WebshareProxyManager()
