# Operations

The service retries failed downstream calls 3 times with a 30 second timeout
per attempt. Uploads above 10 MB are rejected with a 413.

Alert if the p99 latency exceeds 2 seconds.
