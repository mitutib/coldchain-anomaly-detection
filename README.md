# Cold chain anomaly detection

Detects refrigeration faults from temperature sensor readings, without raising an alarm on every scheduled defrost cycle.

The data is synthetic: four sensors in two stores, one reading every five minutes, with a defrost spike every six hours (normal) and slow temperature drifts lasting one to three hours (faults, labelled).

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m coldchain.generate     # writes data/readings.csv
python -m coldchain.evaluate     # precision / recall / F1 per detector
pytest -q
```

## Results

Per-reading metrics on 7 days of data (8,064 readings, 2.3% faulty).

| Detector | Precision | Recall | F1 |
|---|---|---|---|
| Fixed threshold (+3 °C over the setpoint) | 0.22 | 0.66 | 0.33 |
| Rolling z-score | 0.05 | 0.12 | 0.07 |
| Sustained threshold (5 consecutive readings) | 1.00 | 0.48 | 0.65 |

The fixed threshold fires on every defrost cycle. The z-score reacts to sudden jumps, so it catches defrosts and misses slow drifts.

Requiring five consecutive readings above the threshold removes every defrost false alarm (a defrost lasts four readings). Recall drops because the first part of each drift is still below the threshold.

## Roadmap

- [ ] better detectors, evaluated on a time-based split
- [ ] HTTP service, container image, CI
- [ ] Kubernetes deployment
- [ ] experiment tracking and model registry
- [ ] monitoring and drift detection
