# Seed sweep

Generated 2026-09-20 01:15 by `sweep.py`.

Each held-out dataset is generated from a seed the pipeline has never seen, using the organisers' own `generate.py`. A tight spread means the rules generalise rather than memorise.

```
dataset                  final   macroF1      defP     defR      e2e
--------------------------------------------------------------------  -------
supplied (seed 42)      0.9642    0.9680     1.000    0.957   0.9565  44/46

held-out seed 1337      0.9598    0.9820     1.000    0.942   0.9423  49/52
held-out seed 2468      0.9524    0.9725     1.000    0.935   0.9348  43/46
held-out seed 3691      0.9421    0.9507     1.000    0.929   0.9286  52/56
held-out seed 4812      0.9371    0.9554     1.000    0.918   0.9180  56/61
held-out seed 5926      0.9386    0.9923     1.000    0.902   0.9024  37/41

held-out mean   0.9460
held-out min    0.9371   max 0.9598
std dev         0.0087
supplied        0.9642

Generalises. Held-out is within 0.018 of the supplied set.
```
