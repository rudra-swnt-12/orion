# Runbook: Payment-DB

**ALERT:** `HighDBCPU`
* **Symptom:** The `fake_app_cpu_usage_percent` metric is over 80%.
* **Cause:** This is often caused by a bad analytics query.
* **Fix:** Find the long-running query and kill it.

**ALERT:** `DBConnectionLimit`
* **Symptom:** Logs show `FATAL: Database connection limit reached!`
* **Cause:** The `analytics-service` is not closing its connections.
* **Fix:** Restart the `analytics-service` pod immediately.