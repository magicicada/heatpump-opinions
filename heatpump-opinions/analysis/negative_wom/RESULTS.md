# Results tables

These are condensed from the report output of each script, run in early October 2026. The raw CSVs go to `results/negative_wom/`, which is gitignored, so they are not committed. Rerun the command shown to regenerate a table.

## Contents

- 1–3: experiments on the **current model**.
- 4–8: experiments on the **prototype**.

All adoption figures are % of households unless noted. "Shortfall" is the % below the matching run with no bad experiences.

## 1. Weighting bad experiences in the current model (noisy)

`nwom.py sweep` used 5 seeds.

Shortfall in adoption at step 50, by the weight `w` on broken contacts in the neighbour average:

| noise | breakdown/step | long-range share | w=1 | 2 | 3 | 5 | 10 | 20 |
|---|---|---|---|---|---|---|---|---|
| 0.05 | 0.002 | 0.1 | 7.9 | 13.3 | 18.3 | 23.3 | 29.7 | 36.0 |
| 0.05 | 0.002 | 0.5 | 12.6 | 19.6 | 22.4 | 28.5 | 35.2 | 41.8 |
| 0.05 | 0.005 | 0.1 | 23.4 | 33.2 | 39.8 | 49.2 | 57.0 | 62.4 |
| 0.10 | 0.002 | 0.1 | 1.5 | 2.8 | 4.1 | 6.7 | 11.4 | 15.6 |
| 0.10 | 0.005 | 0.1 | 4.4 | 8.1 | 11.8 | 17.6 | 26.7 | 31.6 |

- **Noise and the breakdown rate set the effect, not the network.** The `w` needed for a 10% shortfall ranges from ≤1 to about 9.
- **Without bad experiences, adoption saturates at about 89%** by about step 75 at noise 0.10, and by step 100 at noise 0.05.

## 2. Current model with the noise removed

`lownoise.py sweep` used noise 0, everyone starting neutral and 3 seeds. Adoption at step 300 (89% means full takeoff; about 5% means it never kindled):

| breakdown/step | w | local, segregated | local, random | long-range, segregated | long-range, random |
|---|---|---|---|---|---|
| 0 | 1 | 89.0 | 89.0 | 89.0 | 89.0 |
| 0.0005 | 5 | 82.3 | 82.8 | 45.4 | 31.1 |
| 0.001 | 1 | 88.2 | 88.3 | 88.3 | 88.3 |
| 0.001 | 2 | 82.9 | 12.9 | 55.2 | 55.8 |
| 0.001 | 5 | 6.2 | 5.2 | 5.1 | 5.0 |
| 0.002 | 1 | 82.6 | 6.2 | 30.8 | 6.6 |

**Adoption takes off from social influence alone, but bad experiences act as an on/off switch.** Runs end either near full adoption or near the starting level.

## 3. The cliff, first-owner placement and fading voices

`cliff.py A`, `B`, `C` used w=1 and noise 0.

**A/B: % of 20 seeds that take off** (more than 50% adoption by step 300):

| first owners | layout | 0.001/step | 0.0015/step | 0.002/step | 0.003/step |
|---|---|---|---|---|---|
| top 10% by characteristic | local, segregated | 100 | 100 | 40 | 0 |
| top 10% by characteristic | local, random | 100 | 80 | 0 | 0 |
| top 10% by characteristic | long-range, random | 100 | 65 | 0 | 0 |
| random | local, segregated | 100 | 95 | 5 | 0 |
| random | local, random | 100 | 85 | 0 | 0 |

Median step at which half of eligible households have adopted, with first owners from the top: local/segregated goes 125 → 136 → 153 → 181 as the rate rises over 0, 0.0005, 0.001, 0.0015. That is a ≥10% delay already at 0.0005.

**C: % of 10 seeds that take off, by how fast a broken owner's voice fades** (local/segregated):

| voice half-life (steps) | 0.001 | 0.002 | 0.003 | 0.005 |
|---|---|---|---|---|
| never fades | 100 | 60 | 0 | 0 |
| 50 | 100 | 100 | 90 | 0 |
| 20 | 100 | 100 | 100 | 10 |
| 10 | 100 | 100 | 100 | 100 |

## 4. Prototype, uncalibrated

`proto.py checks` used 10 seeds, a starting motivation of 0.5, a message strength of 0.03 and first owners from the top 10%.

| | 5 yr | 10 yr | 15 yr | 20 yr | 25 yr | yr-1 installs | peak installs |
|---|---|---|---|---|---|---|---|
| local ties | 9.3 | 22.4 | 37.0 | 49.7 | 59.6 | 1.2%/yr | 3.1%/yr (yr 12) |
| long-range ties (lower contact rate) | 8.3 | 19.2 | 32.1 | 44.3 | 54.7 | 1.2%/yr | 2.8%/yr (yr 14) |
| no word of mouth | 6.3 | 10.9 | 14.6 | 18.0 | 21.0 | 1.1%/yr | 1.2%/yr (yr 2) |

- **Seed SD is ≤0.8 points.**
- **Extremes** at 25 years: no dissatisfied owners gives 59.6%; half dissatisfied gives 23.0% (w=1) or 17.6% (w=5); all dissatisfied gives 10.8%.
- **The local vs long-range difference here is a confound.** It comes entirely from the lower contact rate on long ties (see table 5).

## 5. Prototype, calibrated, with equal contact rates

`proto2.py calib`, then `fixes 0.3 0.06 A|B`. Settings: starting motivation 0.3, message strength 0.06, 10 seeds.

- **Calibration:** year-1 installs are about 0.25–0.3% of homes a year. Adoption is about 13–14% at 10 years and about 55% at 25 years, with installs peaking at about 3.3%/yr around year 15.
- **Without word of mouth:** 4.8% at 25 years.
- **Equal contact rates remove the layout effect.** Adoption at 10 years:

| contact rate on long ties | local, segregated | local, random | long-range, segregated | long-range, random |
|---|---|---|---|---|
| 0.25 (DESIGN.md) | 13.1 | 12.0 | 8.5 | 8.1 |
| 0.72 (equal) | 14.3 | 13.4 | 13.4 | 13.3 |

## 6. Network options at the same pace

`proto4.py calib`, then `net`. 10 seeds, with first owners from the top. Each option's message strength is tuned to the base's pace: 0.097 for A, 0.091 for B 0.5, 0.239 for B 0.9, and 0.855 for A+B. The A+B value is implausibly strong.

Effect of structure on adoption at 10 years (points), comparing the real local/segregated network against variants:

| option | vs long-range | vs random layout | vs shuffled network |
|---|---|---|---|
| base | 0.9 | 0.6 | 1.3 |
| A: complex contagion (β=2) | 1.0 | 0.9 | 1.3 |
| B: same-building-type credibility (0.5) | 0.6 | 1.0 | 1.4 |
| B: same-building-type credibility (0.9) | 1.1 | 1.3 | **2.9** |
| A + B 0.9 | 1.8 | 1.9 | **3.5** |

- **Seed SD is ≤1 point.** Option C (sparse discussion network, uncalibrated, `proto3.py`) *reduced* structure effects.
- **Clustering of owners** at 5% adoption: owners have about 2–3× more owner neighbours than a random scatter would give on the real network, against about 1.1–1.3× on the shuffled one. This holds under every option.

**Range of adoption across LSOA types** (eligible households, points), base option:

| | 10 yr, top first owners | 10 yr, random first owners | 25 yr, top first owners |
|---|---|---|---|
| local, segregated | 21.4 | 12.8 | 35.8 |
| long-range, random | 10.9 | 7.9 | 14.0 |
| shuffled network | 9.4 | 7.3 | 9.0 |

## 7. Dose-response for negative word of mouth

`proto4.py dose`. 10 seeds, averaged over both first-owner placements. Shortfall for the base option on local/segregated. Other options and layouts are within about ±2–4 points.

| complaints last | w | 10 yr, q=0.05 | 10 yr, q=0.1 | 10 yr, q=0.2 | 25 yr, q=0.05 | 25 yr, q=0.1 | 25 yr, q=0.2 |
|---|---|---|---|---|---|---|---|
| 12 months | 1 | 8.3 | 14.8 | 25.7 | 3.3 | 6.1 | 14.5 |
| 12 months | 3 | 9.8 | 15.0 | 28.3 | 4.4 | 8.2 | 18.0 |
| forever | 1 | 10.6 | 18.9 | 36.2 | 8.7 | 17.6 | 36.6 |
| forever | 3 | 13.1 | 22.1 | 38.5 | 16.8 | 30.0 | 49.8 |

- **The one exception is complex contagion,** which weakens the long-run effect of permanent complaints: 40.9% against 49.8% at q=0.2, w=3.
- **Silent dissatisfied owners** (w=0, `proto.py` setting, uncalibrated) account for about a third of the effect. At q=0.1 the 10-year shortfall is 4.5 for w=0, 13.1 for w=1 and 19.0 for w=3.

## 8. Shortfall by LSOA type

`proto4.py dose`: shortfall at 25 years with q=0.1, w=1, permanent complaints, local/segregated and first owners from the top. Ranges are across the five options.

| t0 mixed terraced | t1 city-centre flats | t2 suburban/rural detached | t3 social flats | t4 social estates | t5 urban owner-occupied semis |
|---|---|---|---|---|---|
| 16–21 | 15–22 | **8–15** | **22–37** | 20–28 | 11–17 |

- **Baseline adoption at 25 years for comparison:** about 70% for t2 against about 29–39% for t3.
- **The 10-year version of this table is too noisy to use.** Types t3 and t4 have only about 3–7% adoption at 10 years.
