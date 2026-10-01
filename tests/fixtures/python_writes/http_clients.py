"""Additional HTTP client regression fixture."""

import urllib.request
import httpx


def delete_resource(url):
    httpx.delete(url)


def mutate_with_urlopen(req):
    urllib.request.urlopen(req)
