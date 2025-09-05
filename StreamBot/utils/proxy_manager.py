# StreamBot/utils/proxy_manager.py
import ipaddress
import logging
import re
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

class ProxyManager:
    """Generic proxy manager with security validation."""
    
    def __init__(self):
        # Private/internal IP ranges to block for security
        self.blocked_ip_ranges = [
            ipaddress.ip_network('127.0.0.0/8'),     # Localhost
            ipaddress.ip_network('10.0.0.0/8'),      # Private Class A
            ipaddress.ip_network('172.16.0.0/12'),   # Private Class B
            ipaddress.ip_network('192.168.0.0/16'),  # Private Class C
            ipaddress.ip_network('169.254.0.0/16'),  # Link-local
            ipaddress.ip_network('224.0.0.0/4'),     # Multicast
            ipaddress.ip_network('240.0.0.0/4'),     # Reserved
        ]
    
    def _validate_hostname(self, hostname: str) -> bool:
        """Validate hostname/IP for security."""
        try:
            # Check if it's an IP address
            try:
                ip = ipaddress.ip_address(hostname)
                # Block private/internal IPs
                for blocked_range in self.blocked_ip_ranges:
                    if ip in blocked_range:
                        logger.warning(f"Blocked private/internal IP: {hostname}")
                        return False
                return True
            except ValueError:
                # It's a hostname, validate format
                if not re.match(r'^[a-zA-Z0-9.-]+$', hostname):
                    logger.warning(f"Invalid hostname format: {hostname}")
                    return False
                
                # Basic hostname validation
                if len(hostname) > 253:
                    return False
                
                parts = hostname.split('.')
                if len(parts) < 2:
                    return False
                
                for part in parts:
                    if not part or len(part) > 63:
                        return False
                    if not re.match(r'^[a-zA-Z0-9-]+$', part):
                        return False
                    if part.startswith('-') or part.endswith('-'):
                        return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error validating hostname {hostname}: {e}")
            return False
    
    def _validate_port(self, port: int) -> bool:
        """Validate port number."""
        return 1 <= port <= 65535
    
    def _validate_proxy_type(self, proxy_type: str) -> bool:
        """Validate proxy type."""
        valid_types = ['http', 'https', 'socks4', 'socks5']
        return proxy_type.lower() in valid_types
    
    def get_proxy_config(self, hostname: str, port: int, proxy_type: str = 'http', 
                        username: str = None, password: str = None) -> Optional[Dict]:
        """Get validated proxy configuration for Pyrogram client."""
        
        # Input validation
        if not hostname or not isinstance(hostname, str):
            logger.warning("Invalid hostname provided")
            return None
        
        hostname = hostname.strip()
        
        if not self._validate_hostname(hostname):
            logger.warning(f"Hostname validation failed: {hostname}")
            return None
        
        if not self._validate_port(port):
            logger.warning(f"Invalid port: {port}")
            return None
        
        if not self._validate_proxy_type(proxy_type):
            logger.warning(f"Invalid proxy type: {proxy_type}")
            return None
        
        try:
            proxy_config = {
                "scheme": proxy_type.lower(),
                "hostname": hostname,
                "port": port
            }
            
            # Add authentication if provided
            if username and password:
                proxy_config["username"] = username.strip()
                proxy_config["password"] = password
            
            logger.info(f"Using proxy: {proxy_type}://{hostname}:{port} (auth: {'yes' if username else 'no'})")
            
            return proxy_config
            
        except Exception as e:
            logger.error(f"Failed to configure proxy: {e}")
            return None
    
    def validate_proxy_input(self, hostname: str, port: str, proxy_type: str = 'http') -> Tuple[bool, str]:
        """Validate proxy input and return (is_valid, error_message)."""
        
        if not hostname:
            return False, "Hostname is required"
        
        hostname = hostname.strip()
        
        if not self._validate_hostname(hostname):
            return False, "Invalid hostname or blocked IP address"
        
        try:
            port_int = int(port)
            if not self._validate_port(port_int):
                return False, "Port must be between 1 and 65535"
        except (ValueError, TypeError):
            return False, "Invalid port number"
        
        if not self._validate_proxy_type(proxy_type):
            return False, "Invalid proxy type (supported: http, https, socks4, socks5)"
        
        return True, "Valid proxy configuration"

# Global instance
proxy_manager = ProxyManager()
