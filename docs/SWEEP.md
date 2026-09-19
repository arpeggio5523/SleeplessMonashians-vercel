# Seed sweep

Generated 2026-09-20 01:32 by `sweep.py`.

Each held-out dataset is generated from a seed the pipeline has never seen, using the organisers' own `generate.py`. A tight spread means the rules generalise rather than memorise.

```
dataset                  final   macroF1      defP     defR      e2e
--------------------------------------------------------------------  -------
supplied (seed 42)      0.9904    0.9680     1.000    1.000   1.0000  46/46

held-out seed 1337      0.9946    0.9820     1.000    1.000   1.0000  52/52
held-out seed 2468      0.9917    0.9725     1.000    1.000   1.0000  46/46
held-out seed 3691      0.9852    0.9507     1.000    1.000   1.0000  56/56
held-out seed 4812      0.9866    0.9554     1.000    1.000   1.0000  61/61
held-out seed 5926      0.9977    0.9923     1.000    1.000   1.0000  41/41

held-out mean   0.9912
held-out min    0.9852   max 0.9977
std dev         0.0047
supplied        0.9904

Generalises. Held-out is within 0.001 of the supplied set.
```
