# ingest-service

Ingests activity files and writes normalised records.

## Limits

- Upload size limit: **10 MB**
- Request timeout: **30 seconds**
- Retry attempts: 3

## Running

```bash
docker build -t ingest .
docker run -p 8000:8000 ingest
```
