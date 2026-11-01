# Gnani response fixtures

- `*.docs.json`: example bodies copied from docs.gnani.ai (checked 2026-11-01).
- `*.recorded.json`: real responses saved by `make smoke-voice FILE=... ARGS=--record`.
  `request_id` is kept, and nothing secret is ever stored (the API key never appears in a response).

Unit tests replay these through `respx`. They never hit the network.
