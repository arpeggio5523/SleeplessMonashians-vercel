# Evaluation — rules vs rules + Gemini

Generated 2026-09-20 01:43 by `compare.py`.

The final score is a weighted sum of three metrics:

    final = 0.30 x stage1_macro_f1
          + 0.20 x stage3_defect_f1
          + 0.50 x end_to_end_rate

Everything else below is diagnostic — it explains those three but does
not contribute to the score.

## Results

| dataset | rules | + Gemini | change | macro-F1 | defect-F1 | end-to-end |
|---|---|---|---|---|---|---|
| seed42 (supplied) | 0.9904 | 0.9995 | +0.0091 | 0.9982 | 1.0000 | 1.0000 |
| seed7001 (held-out) | 0.9917 | 0.9995 | +0.0077 | 0.9982 | 1.0000 | 1.0000 |
| seed7002 (held-out) | 0.9912 | 0.9989 | +0.0077 | 0.9965 | 1.0000 | 1.0000 |
| seed7003 (held-out) | 0.9866 | 0.9984 | +0.0118 | 0.9947 | 1.0000 | 1.0000 |
| seed7004 (held-out) | 0.9977 | 0.9989 | +0.0013 | 0.9965 | 1.0000 | 1.0000 |
| seed7005 (held-out) | 0.9917 | 0.9995 | +0.0077 | 0.9982 | 1.0000 | 1.0000 |

Held-out mean **0.9990** across 5 datasets generated with seeds the pipeline had never seen (range 0.9984–0.9995, spread 0.0011).

## Full report

```

┌────────────────────────────────────────────────────────────────────────┐
│ SUPPLIED DATASET  ·  seed 42  ·  520 emails                            │
└────────────────────────────────────────────────────────────────────────┘

  SCORED  — these three, weighted, are the final score
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 macro-F1           0.9680     0.9982  +0.0302  x0.30  ↑
    stage3 defect-F1          1.0000     1.0000        —  x0.20
    end-to-end rate           1.0000     1.0000        —  x0.50
  ──────────────────────────────────────────────────────────────────────
    FINAL SCORE               0.9904     0.9995  +0.0091         ↑

  DIAGNOSTIC — explains the above, not scored directly
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 accuracy           0.9846     0.9981  +0.0135         ↑
    defect precision          1.0000     1.0000        —       
    defect recall             1.0000     1.0000        —       
    escalation recall         0.9500     0.9500        —       
    escalation precision      1.0000     1.0000        —       
    e2e emails                            46/46    exact defect-field match required

  HEADROOM — points still available, by stage
  ──────────────────────────────────────────────────────────────────────
    stage1 macro-F1         0.0005 pts  100.0%  █████████████████████████
    stage3 defect-F1        0.0000 pts    0.0%  
    end-to-end              0.0000 pts    0.0%  
  ──────────────────────────────────────────────────────────────────────
    to a perfect 1.0000     0.0005 pts

  CLASSIFICATION CHANGES
  ──────────────────────────────────────────────────────────────────────
    fixed  (7):
      email_226  gold SPAM           GENERAL → SPAM
      email_345  gold SPAM           GENERAL → SPAM
      email_363  gold SPAM           GENERAL → SPAM
      email_382  gold SPAM           GENERAL → SPAM
      email_390  gold SPAM           GENERAL → SPAM
      email_417  gold SPAM           GENERAL → SPAM
      email_455  gold SPAM           GENERAL → SPAM

┌────────────────────────────────────────────────────────────────────────┐
│ HELD-OUT  ·  seed 7001  ·  never seen before                           │
└────────────────────────────────────────────────────────────────────────┘

  SCORED  — these three, weighted, are the final score
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 macro-F1           0.9725     0.9982  +0.0257  x0.30  ↑
    stage3 defect-F1          1.0000     1.0000        —  x0.20
    end-to-end rate           1.0000     1.0000        —  x0.50
  ──────────────────────────────────────────────────────────────────────
    FINAL SCORE               0.9917     0.9995  +0.0077         ↑

  DIAGNOSTIC — explains the above, not scored directly
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 accuracy           0.9865     0.9981  +0.0115         ↑
    defect precision          1.0000     1.0000        —       
    defect recall             1.0000     1.0000        —       
    escalation recall         0.9500     0.9500        —       
    escalation precision      1.0000     1.0000        —       
    e2e emails                            61/61    exact defect-field match required

  HEADROOM — points still available, by stage
  ──────────────────────────────────────────────────────────────────────
    stage1 macro-F1         0.0005 pts  100.0%  █████████████████████████
    stage3 defect-F1        0.0000 pts    0.0%  
    end-to-end              0.0000 pts    0.0%  
  ──────────────────────────────────────────────────────────────────────
    to a perfect 1.0000     0.0005 pts

┌────────────────────────────────────────────────────────────────────────┐
│ HELD-OUT  ·  seed 7002  ·  never seen before                           │
└────────────────────────────────────────────────────────────────────────┘

  SCORED  — these three, weighted, are the final score
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 macro-F1           0.9707     0.9965  +0.0257  x0.30  ↑
    stage3 defect-F1          1.0000     1.0000        —  x0.20
    end-to-end rate           1.0000     1.0000        —  x0.50
  ──────────────────────────────────────────────────────────────────────
    FINAL SCORE               0.9912     0.9989  +0.0077         ↑

  DIAGNOSTIC — explains the above, not scored directly
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 accuracy           0.9846     0.9962  +0.0115         ↑
    defect precision          1.0000     1.0000        —       
    defect recall             1.0000     1.0000        —       
    escalation recall         0.9000     0.9000        —       
    escalation precision      1.0000     1.0000        —       
    e2e emails                            52/52    exact defect-field match required

  HEADROOM — points still available, by stage
  ──────────────────────────────────────────────────────────────────────
    stage1 macro-F1         0.0011 pts  100.0%  █████████████████████████
    stage3 defect-F1        0.0000 pts    0.0%  
    end-to-end              0.0000 pts    0.0%  
  ──────────────────────────────────────────────────────────────────────
    to a perfect 1.0000     0.0011 pts

┌────────────────────────────────────────────────────────────────────────┐
│ HELD-OUT  ·  seed 7003  ·  never seen before                           │
└────────────────────────────────────────────────────────────────────────┘

  SCORED  — these three, weighted, are the final score
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 macro-F1           0.9554     0.9947  +0.0393  x0.30  ↑
    stage3 defect-F1          1.0000     1.0000        —  x0.20
    end-to-end rate           1.0000     1.0000        —  x0.50
  ──────────────────────────────────────────────────────────────────────
    FINAL SCORE               0.9866     0.9984  +0.0118         ↑

  DIAGNOSTIC — explains the above, not scored directly
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 accuracy           0.9769     0.9942  +0.0173         ↑
    defect precision          1.0000     1.0000        —       
    defect recall             1.0000     1.0000        —       
    escalation recall         0.8500     0.8500        —       
    escalation precision      1.0000     1.0000        —       
    e2e emails                            45/45    exact defect-field match required

  HEADROOM — points still available, by stage
  ──────────────────────────────────────────────────────────────────────
    stage1 macro-F1         0.0016 pts  100.0%  █████████████████████████
    stage3 defect-F1        0.0000 pts    0.0%  
    end-to-end              0.0000 pts    0.0%  
  ──────────────────────────────────────────────────────────────────────
    to a perfect 1.0000     0.0016 pts

┌────────────────────────────────────────────────────────────────────────┐
│ HELD-OUT  ·  seed 7004  ·  never seen before                           │
└────────────────────────────────────────────────────────────────────────┘

  SCORED  — these three, weighted, are the final score
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 macro-F1           0.9923     0.9965  +0.0042  x0.30  ↑
    stage3 defect-F1          1.0000     1.0000        —  x0.20
    end-to-end rate           1.0000     1.0000        —  x0.50
  ──────────────────────────────────────────────────────────────────────
    FINAL SCORE               0.9977     0.9989  +0.0013         ↑

  DIAGNOSTIC — explains the above, not scored directly
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 accuracy           0.9942     0.9962  +0.0019         ↑
    defect precision          1.0000     1.0000        —       
    defect recall             1.0000     1.0000        —       
    escalation recall         0.9000     0.9000        —       
    escalation precision      1.0000     1.0000        —       
    e2e emails                            59/59    exact defect-field match required

  HEADROOM — points still available, by stage
  ──────────────────────────────────────────────────────────────────────
    stage1 macro-F1         0.0011 pts  100.0%  █████████████████████████
    stage3 defect-F1        0.0000 pts    0.0%  
    end-to-end              0.0000 pts    0.0%  
  ──────────────────────────────────────────────────────────────────────
    to a perfect 1.0000     0.0011 pts

┌────────────────────────────────────────────────────────────────────────┐
│ HELD-OUT  ·  seed 7005  ·  never seen before                           │
└────────────────────────────────────────────────────────────────────────┘

  SCORED  — these three, weighted, are the final score
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 macro-F1           0.9725     0.9982  +0.0257  x0.30  ↑
    stage3 defect-F1          1.0000     1.0000        —  x0.20
    end-to-end rate           1.0000     1.0000        —  x0.50
  ──────────────────────────────────────────────────────────────────────
    FINAL SCORE               0.9917     0.9995  +0.0077         ↑

  DIAGNOSTIC — explains the above, not scored directly
  ──────────────────────────────────────────────────────────────────────
                               rules   + Gemini   change  weight
    stage1 accuracy           0.9865     0.9981  +0.0115         ↑
    defect precision          1.0000     1.0000        —       
    defect recall             1.0000     1.0000        —       
    escalation recall         0.9500     0.9500        —       
    escalation precision      1.0000     1.0000        —       
    e2e emails                            49/49    exact defect-field match required

  HEADROOM — points still available, by stage
  ──────────────────────────────────────────────────────────────────────
    stage1 macro-F1         0.0005 pts  100.0%  █████████████████████████
    stage3 defect-F1        0.0000 pts    0.0%  
    end-to-end              0.0000 pts    0.0%  
  ──────────────────────────────────────────────────────────────────────
    to a perfect 1.0000     0.0005 pts

┌────────────────────────────────────────────────────────────────────────┐
│ SUMMARY                                                                │
└────────────────────────────────────────────────────────────────────────┘
    dataset                   rules   + Gemini   change   macroF1      e2e
  ──────────────────────────────────────────────────────────────────────
    seed42 (supplied)        0.9904     0.9995  +0.0091    0.9982   1.0000
    seed7001 (held-out)      0.9917     0.9995  +0.0077    0.9982   1.0000
    seed7002 (held-out)      0.9912     0.9989  +0.0077    0.9965   1.0000
    seed7003 (held-out)      0.9866     0.9984  +0.0118    0.9947   1.0000
    seed7004 (held-out)      0.9977     0.9989  +0.0013    0.9965   1.0000
    seed7005 (held-out)      0.9917     0.9995  +0.0077    0.9982   1.0000
  ──────────────────────────────────────────────────────────────────────
    held-out mean 0.9990   range 0.9984–0.9995   spread 0.0011
    vs supplied 0.9995  →  generalises

    LLM usage: {'cache_hits': 162, 'calls': 11, 'failures': 0, 'throttled_s': 7.5949999999429565}
    appended to compare_deep.csv
```
