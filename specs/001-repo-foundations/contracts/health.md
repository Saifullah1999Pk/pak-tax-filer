# Contract: Backend health check

`GET http://localhost:8000/health`

**Response** `200 OK`, `Content-Type: application/json`:

```json
{ "status": "ok" }
```

No authentication. No other fields. Covers spec FR-003.
