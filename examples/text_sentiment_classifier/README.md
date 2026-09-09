# Text example: review classifier

Monitors a toy text classifier with NextPhase's `TextProfiler`. Simulates
production traffic shifting topic entirely — from coffee-shop reviews (the
reference set) to unrelated customer-support tickets — and computes
embedding-centroid distance, sampled MMD, length shift, and vocabulary
(Jensen-Shannon / OOV) drift.

```bash
pip install -e "../..[text]"
python monitor.py
```

The default embedder is `sentence-transformers` (`all-MiniLM-L6-v2`),
downloaded on first run. Expect every drift metric to fire — this is a
maximally obvious topic shift by design; real deployments will show more
graduated drift.
