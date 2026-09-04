# Tabular example: fraud detector

Monitors a toy fraud-detection model (any callable — here a plain function
stands in for an sklearn/PyTorch model) with DriftWatch. Simulates 200
inference calls where `income` drifts sharply upward relative to the
reference distribution, then computes drift metrics (PSI, KS-test,
Wasserstein distance, missing-rate delta, schema drift) for the elapsed
time window.

```bash
pip install -e ../..
python train_and_monitor.py
```

Expect `income` to show up as drifted (PSI > 0.2, low KS p-value) while
`age` (unchanged) does not.
