# Cold chain anomaly detection

Detects refrigeration faults from temperature sensor readings, without raising an alarm on every scheduled defrost cycle.

The data is synthetic: four sensors in two stores, one reading every five minutes, with a defrost spike every six hours (normal) and slow temperature drifts lasting one to three hours (faults, labelled).

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m coldchain.generate --days 28   # writes data/readings.csv
python -m coldchain.evaluate             # tunes on the first 70%, reports on the rest (about 40 s)
pytest -q
```

## Results

28 days of data, split by time: parameters are chosen on the first 70% and every number below comes from the last 30% (8.4 days, 9,680 readings, 13 faults). The split is never random, because a deployed detector only ever sees the future.

| Detector | Tuned parameters | Precision | Recall | F1 | Faults caught | Median delay | False alarms |
|---|---|---|---|---|---|---|---|
| Fixed threshold | setpoint + 1.5 °C | 0.34 | 0.84 | 0.48 | 13 / 13 | 20 min | 136 |
| Rolling z-score | 2.5 standard deviations | 0.10 | 0.19 | 0.13 | 9 / 13 | 15 min | 178 |
| Sustained threshold | setpoint + 1.0 °C for 5 readings | 1.00 | 0.72 | 0.84 | 13 / 13 | 30 min | 0 |
| Defrost aware | setpoint + 1.0 °C for 2 readings | 0.98 | 0.82 | 0.89 | 13 / 13 | 15 min | 5 |
| Gradient boosting | probability above 0.5 for 2 readings | 0.98 | 0.85 | 0.91 | 13 / 13 | 20 min | 6 |

Precision, recall and F1 are counted per reading. The last three columns are counted per fault: whether it was caught at all, how long after it started, and how many separate alarms did not touch any fault.

What the numbers say:

- The fixed threshold catches every fault but raises 136 false alarms in eight days, mostly on defrost cycles. Nobody keeps reading alerts at that rate.
- The z-score reacts to sudden jumps, so it fires on defrosts and misses slow drifts.
- Requiring five consecutive readings above the threshold removes every false alarm, because a defrost lasts four readings. The price is time: a fault is reported about 30 minutes after it starts.

- The defrost-aware detector tells the two apart by shape: a defrost starts with a sudden jump, a fault drifts up slowly. After a jump it holds alarms back for 30 minutes, and fires only if the temperature is still high. That halves the delay to 15 minutes at the cost of 5 false alarms in eight days.

- The gradient boosting model is trained on nine window features per reading (offset from the setpoint, rolling mean, minimum, rise over 15, 30 and 60 minutes, largest jump, spread). It is fitted on the first 50% of the data, its alarm rule is chosen on the next 20%, and it is refitted on both before the test.

**The model does not clearly beat the hand-written rule.** Its F1 is two points higher, its delay five minutes longer, and it raises one more false alarm. With 13 faults in the test period, none of those differences is large enough to trust. On this data the defrost-aware rule is the better choice: it does the same job, anyone can read it, and it needs no training. A learned model should earn its place on real data, where faults do not all look alike.

Which of the two rules is better depends on what a false alarm costs compared with 15 minutes of warm product. That is a decision for whoever answers the alerts, not something the F1 score settles.

Known limits:

- The jump size and the hold time of the defrost-aware detector were set by hand, not tuned.
- The tuned threshold sits at the edge of the search grid.
- The test period holds 13 faults, so small differences between detectors are noise.
- The data is synthetic, so real sensors will be noisier than this.

## Experiment tracking

`python -m coldchain.track` runs the same evaluation and records it in MLflow: one run per detector with its tuned parameters and its metrics, tagged with the hash of the data file so two runs can be compared knowing they saw the same readings. The gradient boosting model is stored with its run and registered as `coldchain-fault-model`.

```bash
python -m coldchain.track                           # writes to sqlite:///mlflow.db
mlflow ui --backend-store-uri sqlite:///mlflow.db   # http://localhost:5000
```

The service still runs the defrost-aware rule. The registered model is there so the comparison can be repeated when real data arrives, not because it is in use.

## Service

The defrost-aware detector runs as a small HTTP service. It keeps one detector per sensor and answers each reading with a verdict.

```bash
docker build -t coldchain .
docker run -p 8000:8000 coldchain

curl -X POST localhost:8000/readings -H 'content-type: application/json' \
  -d '{"sensor": "dairy", "setpoint": 4.0, "temperature": 5.8}'
# {"sensor":"dairy","alarm":false}
```

| Endpoint | Purpose |
|---|---|
| `POST /readings` | score one reading |
| `GET /health` | liveness check |
| `GET /metrics` | Prometheus counters: readings received, alarms raised |

The threshold and the number of consecutive readings come from `COLDCHAIN_OFFSET` and `COLDCHAIN_N` (defaults 1.0 and 2, the tuned values above).

Detector state is kept in memory by default. With `COLDCHAIN_REDIS_URL` set it goes to Redis instead, so several replicas can serve the same sensor: each reading is a read-modify-write under an optimistic lock, retried if another replica got there first.

| Endpoint | Purpose |
|---|---|
| `GET /ready` | readiness check: fails while Redis is unreachable |

## Monitoring and drift

The thresholds were tuned on one kind of data. If the sensors change, the detector keeps running and quietly gets worse, so the service exports what is needed to notice:

| Metric | What it tells you |
|---|---|
| `coldchain_readings_total`, `coldchain_alarms_total` | volume, and the share of readings in alarm |
| `coldchain_alarm_starts_total` | how many separate alarms began |
| `coldchain_reading_offset_degrees` | histogram of reading minus setpoint: the input distribution |
| `coldchain_request_seconds` | time to score a reading, Redis round trip included |
| `coldchain_store_errors_total` | readings refused because Redis was down |

To see what drift does, the tuned detector was run on 28 days of data from sensors with more noise than it was tuned on. `python -m coldchain.drift reference.csv current.csv` gives the population stability index (PSI) of the input distribution.

| Sensor noise | PSI | Faults caught | False alarms | Alarm starts per day |
|---|---|---|---|---|
| as tuned | 0.00 | 30 / 30 | 34 | 2.4 |
| 1.5 times | 0.07 | 30 / 30 | 156 | 6.7 |
| 2 times | 0.22 | 30 / 30 | 314 | 12.4 |
| 3 times | 0.58 | 28 / 30 | 519 | 19.9 |

Two things stand out:

- **PSI is too slow here.** At 1.5 times the noise it reads 0.07, under the usual 0.1 "stable" line, while false alarms have already grown more than four times. Watching the input distribution alone would have missed it.
- **The detector's own output is the better signal.** Alarm starts per day nearly triple at the first step. That is why the service counts alarm starts separately from alarming readings: the count of readings in alarm moves much less, because a real fault holds many readings and a false alarm only a few.

So the alert to set is on alarm starts per sensor per day against the rate seen during tuning, with PSI kept as supporting evidence when it fires.

## Kubernetes

The Helm chart is in `deploy/helm/coldchain`. To run it on a local [kind](https://kind.sigs.k8s.io/) cluster:

```bash
kind create cluster --name coldchain
docker build -t coldchain:0.3.0 .
kind load docker-image coldchain:0.3.0 --name coldchain
helm install coldchain deploy/helm/coldchain --namespace coldchain --create-namespace --wait
kubectl -n coldchain port-forward svc/coldchain 8000:80
```

What the chart sets up:

- **Two or more replicas with state in Redis.** Sending one sensor's readings to the pods in turn gives the same alarms as a single instance.
- **Rollouts that cannot take the service down.** With `maxUnavailable: 0`, an upgrade to an image that does not exist leaves the new pod in `ErrImagePull` while the old ones keep answering; `helm rollback` cleans up.
- **Separate liveness and readiness.** When Redis goes away the pods stop being ready and leave the Service, but they are not restarted, because restarting them would not bring Redis back. `POST /readings` answers 503 meanwhile.
- **Autoscaling** between two and five replicas at 60% of the requested CPU. Under a constant stream of requests it went from two replicas to five in under a minute, and back to two about two minutes after the load stopped.

Autoscaling needs metrics-server, which kind does not ship:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deploy metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

The bundled Redis runs without persistence, so after it restarts the detectors start cold, which costs a couple of readings per sensor. To use a Redis you already run, set `redis.enabled=false` and `redis.externalUrl`.

## Roadmap

- [x] baseline detectors, evaluated on a time-based split
- [x] detect faults sooner: defrost-aware detector
- [x] learned model on window features, compared against the rules
- [x] HTTP service, container image, CI
- [x] Kubernetes deployment, two replicas with shared state in Redis
- [x] autoscaling
- [x] Helm chart
- [x] experiment tracking and model registry
- [x] drift measured, metrics exported
- [ ] Prometheus rules and a dashboard
