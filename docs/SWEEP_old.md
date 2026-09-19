# Seed sweep

Generated 2026-09-20 01:13 by `sweep.py`.

Each held-out dataset is generated from a seed the pipeline has never seen, using the organisers' own `generate.py`. A tight spread means the rules generalise rather than memorise.

```
dataset                  final   macroF1      defP     defR      e2e
--------------------------------------------------------------------  -------
supplied (seed 42)      0.9642    0.9680     1.000    0.957   0.9565  44/46

held-out seed 101       0.9540    0.9957     1.000    0.926   0.9259  25/27
held-out seed 202       0.9807    0.9356     1.000    1.000   1.0000  18/18
held-out seed 303       0.9903    0.9675     1.000    1.000   1.0000  16/16
held-out seed 404       0.9865    0.9550     1.000    1.000   1.0000  23/23
held-out seed 505       0.9521    0.9275     1.000    0.957   0.9565  22/23

held-out mean   0.9727
held-out min    0.9521   max 0.9903
std dev         0.0164
supplied        0.9642

Generalises. Held-out is within 0.008 of the supplied set.
```
