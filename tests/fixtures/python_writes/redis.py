"""Redis regression fixture."""


def cache_value(r, key, value):
    r.set(key, value)


def delete_cache(r, key):
    r.delete(key)
