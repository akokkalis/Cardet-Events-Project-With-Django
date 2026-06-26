# Performance Report

This performance test was executed using **Locust** to evaluate how the system behaves under simulated high‑load conditions.

## Test Configuration

- **Tool Used:** Locust  
- **Total Users:** 100 simulated users  
- **Ramp‑up Time:** 1 second  
- **Test Scenario:**  
  - An existing event with **public registration enabled** and **no participant limit** was used.  
  - Each simulated user:  
    1. Opened the public registration link  
    2. Entered **Full Name**, **Email**, and **Phone Number**  
    3. Submitted the registration form  

## Observed Behavior

During the test execution, the system showed noticeable **slowdowns** as reflected in the attached Locust performance report.  
The report contains detailed metrics, including:

- Response time distribution  
- Number of requests per second  
- Failure rates (if any)  
- Throughput and peak load behavior  

## Summary

The system handled the load but experienced **performance degradation**, especially under the rapid ramp‑up of 100 simultaneous users submitting registration forms. The provided report should be used to analyze specific bottlenecks and identify areas for optimization in the registration workflow and backend processing.

## Detailed Results & Analysis

Below is a summary of the most important performance findings extracted from the Locust HTML report.

---

## Key Metrics

**Test Duration:** 4 minutes 31 seconds  
**Target Host:** `https://qrscanner.innovedu.com`  
**Users Simulated:** 100  
**Ramp‑Up Time:** 1 second  

### High‑Level Observations
- System performance **degraded severely** as user load approached 100.
- **Average response times escalated** from under 500 ms to more than **27 seconds**.
- **95th percentile response times** exceeded **90 seconds**.
- Large numbers of **HTTP 500, 502, and 504** errors occurred due to backend overload.

### Response Time Metrics
- **Median Response Time (P50):** Up to **63,000 ms (63s)**  
- **95th Percentile:** Up to **96,000 ms (96s)**  
- **Peak Average Response Time:** ~**27,591 ms**  
- **Peak Requests Per Second:** **14.7 RPS**  
- **Peak Failures Per Second:** **9.6 failures/sec**  

---

## Failure Summary

During the load test, the registration flow experienced major backend errors indicating instability under pressure.

### Most Common Failures

| Error Type | Method | Occurrences |
|-----------|--------|-------------|
| **500 – OperationalError** | POST `/register/{uuid}/` | 14 |
| **500 – Failed to GET registration page** | GET `/register/{uuid}/` | 80 |
| **502 – Bad Gateway** | POST `/register/{uuid}/` | 25 |
| **502 – Bad Gateway** | GET `/register/{uuid}/` | 8 |
| **500 – ReadTimeout** | POST `/register/{uuid}/` | 30 |
| **500 – HTTPStatusError** | POST `/register/{uuid}/` | 78 |
| **504 – Gateway Timeout** | GET `/register/{uuid}/` | 50 |

**Interpretation:**  
These errors indicate:
- Server resource exhaustion  
- Long‑running synchronous calls and/or DB bottlenecks  
- Request queue overflow  
- Nginx/Gateway timeout due to backend unresponsiveness  

---

## Performance Degradation Pattern

- At **3–20 users**, the system is stable (avg ~400 ms).
- At **40+ users**, response times grow to **4–6 seconds**.
- At **60–80 users**, average latency increases to **6–27 seconds**.
- At **100 users**, response times peak at **30+ seconds**, with **major failure spikes**.

A clear **non‑linear degradation** was observed, showing the system is not scaled for 100 concurrent submissions.

---

## Summary

The system **does not currently scale** to 100 concurrent registrations. Severe slowdowns and frequent server errors were recorded.  
This suggests several required improvements:

### Recommended Next Steps
- Add **APM monitoring** to identify bottlenecks (CPU, DB locks, external calls).  
- Scale backend workers (e.g., Gunicorn/Uvicorn concurrency).  
- Optimize the **registration database writes** and any external API calls.  
- Add caching where appropriate.  
- Increase Nginx/Load Balancer timeout thresholds.  
- Re‑run load tests after backend optimization.

---

This summary is based directly on the attached Locust performance report.  