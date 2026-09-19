# Seed sweep

Generated 2026-09-20 01:16 by `sweep.py`.

Each held-out dataset is generated from a seed the pipeline has never seen, using the organisers' own `generate.py`. A tight spread means the rules generalise rather than memorise.

```
dataset                  final   macroF1      defP     defR      e2e
--------------------------------------------------------------------  -------
supplied (seed 42)      0.9642    0.9680     1.000    0.957   0.9565  44/46

held-out seed 8801      0.9671    0.9645     1.000    0.963   0.9630  52/54
held-out seed 9137      0.9706    0.9600     1.000    0.971   0.9710  67/69
held-out seed 7420      0.9403    0.9663     1.000    0.918   0.9180  56/61
held-out seed 6655      0.9759    0.9812     1.000    0.969   0.9692  63/65
held-out seed 5309      0.9509    0.9855     1.000    0.926   0.9259  50/54

held-out mean   0.9610
held-out min    0.9403   max 0.9759
std dev         0.0132
supplied        0.9642

Generalises. Held-out is within 0.003 of the supplied set.
```
