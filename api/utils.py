import hashlib
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status

def generate_cache_key(prefix: str, request) -> str:
    """
    Generates a deterministic and safe cache key based on prefix and sorted query parameters.
    """
    sorted_params = sorted(request.GET.items())
    params_str = "&".join([f"{k}={v}" for k, v in sorted_params])
    params_hash = hashlib.md5(params_str.encode('utf-8')).hexdigest()
    return f"{prefix}:{params_hash}"

def get_cached_response(cache_key: str):
    """
    Helper to fetch cached response data dict and return a DRF Response if found.
    """
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return Response(cached_data, status=status.HTTP_200_OK)
    return None

def set_cached_response(cache_key: str, data, timeout=86400):
    """
    Helper to save response data dict to the cache.
    """
    cache.set(cache_key, data, timeout=timeout)
