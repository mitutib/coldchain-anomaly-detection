# Cold chain anomaly detection

Detects refrigeration faults from temperature sensor readings, without raising an alarm on every scheduled defrost cycle.

The data is synthetic: four sensors in two stores, one reading every five minutes, with a defrost spike every six hours (normal) and slow temperature drifts lasting one to three hours (faults, labelled).

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m coldchain.generate --days 28   # writes data/readings.csv
python -m coldchain.evaluate             # tunes on the first 70%, reports on the rest
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

Precision, recall and F1 are counted per reading. The last three columns are counted per fault: whether it was caught at all, how long after it started, and how many separate alarms did not touch any fault.

What the numbers say:

- The fixed threshold catches every fault but raises 136 false alarms in eight days, mostly on defrost cycles. Nobody keeps reading alerts at that rate.
- The z-score reacts to sudden jumps, so it fires on defrosts and misses slow drifts.
- Requiring five consecutive readings above the threshold removes every false alarm, because a defrost lasts four readings. The price is time: a fault is reported about 30 minutes after it starts.

- The defrost-aware detector tells the two apart by shape: a defrost starts with a sudden jump, a fault drifts up slowly. After a jump it holds alarms back for 30 minutes, and fires only if the temperature is still high. That halves the delay to 15 minutes at the cost of 5 false alarms in eight days.

Which of the last two is better depends on what a false alarm costs compared with 15 minutes of warm product. That is a decision for whoever answers the alerts, not something the F1 score settles.

Known limits:

- The jump size and the hold time of the defrost-aware detector were set by hand, not tuned.
- The tuned threshold sits at the edge of the search grid.
- The data is synthetic, so real sensors will be noisier than this.

## Roadmap

- [x] baseline detectors, evaluated on a time-based split
- [x] detect faults sooner: defrost-aware detector
- [ ] learned model on window features, compared against the rules
- [ ] HTTP service, container image, CI
- [ ] Kubernetes deployment
- [ ] experiment tracking and model registry
- [ ] monitoring and drift detection
