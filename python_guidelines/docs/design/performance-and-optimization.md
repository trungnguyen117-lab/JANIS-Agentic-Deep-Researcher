# Performance & Optimization

- Prefer built-ins and stdlib algorithms (e.g., `sum`, `any`, `collections.Counter`) over manual loops.
- Use comprehensions for clarity and speed; switch to generators for large data to save memory.
- Avoid redundant work; cache results when inputs repeat (`functools.lru_cache`).
- Profile before optimizing (`python -m cProfile`, `py-spy`, `perf`); fix hotspots, not guesses.
- For big data, stream and iterate; avoid loading everything into memory.

### Examples
```python
from functools import lru_cache

@lru_cache(maxsize=1024)
def geo_lookup(ip: str) -> GeoData:
    ...

# Generators to avoid memory blowups
def read_lines(path: str):
    with open(path) as f:
        for line in f:
            yield line.rstrip("\n")
```

- Consider `itertools` for iterator pipelines; `enumerate`/`zip` over manual counters.
- If CPU-bound and critical, look at vectorized libs (numpy/pandas) or C extensions/numba.

