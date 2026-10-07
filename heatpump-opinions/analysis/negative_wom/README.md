# Negative word of mouth: exploration (Oct 2026)

Exploratory work since `main` at `a9f6116`, which uses the spatial_kernel network and 694 households per cell. Nothing in `heatpump_sim/` or `settings.yaml` is changed: the scripts here wrap or replace the dynamics outside the model code. All parameter values are placeholders. This is for discussion, not a proposal to merge model changes.

## What we tried

1. **Weighting bad experiences in the current model** (`nwom.py`).
   - Broken owners count `w` times in their neighbours' average opinion.
   - At `w = 1` it reproduces the committed model exactly (`python nwom.py check`).
2. **The current model with the noise removed** (`lownoise.py`, `cliff.py`).
   - No opinion noise, everyone starting neutral, 300 steps.
   - Tested a range of breakdown rates with 20 seeds.
   - Placed early adopters at random rather than among the top 10% by characteristic.
   - Let broken owners' voices fade over time.
3. **A prototype of an alternative mechanism** (`proto.py`, `proto2.py`). Each step is one month.
   - Only owners talk, at DESIGN.md contact rates.
   - Households consider a heat pump only when a trigger happens (e.g. the boiler fails), then choose with a logistic probability.
   - Dissatisfied owners are described by their share `q`, their complaint weight `w` and how long they keep complaining.
   - It is calibrated to roughly today's UK install rate (about 0.3% of homes a year; a rough figure, not checked against a source).
4. **Network options in the prototype** (`proto3.py`, `proto4.py`).
   - Options:
     - complex contagion;
     - credibility from owners with the same building type;
     - a sparse discussion network.
   - Each is matched to the same adoption pace and compared against a shuffled network that keeps everyone's number of contacts.
5. **Negative word-of-mouth dose-response in the prototype** (`proto4.py`), measured on total adoption and on the gaps between LSOA types.

## Key findings

- **The current model is driven by noise.** Adoption is absorbing, so noise eventually pushes everyone over the threshold. Network, segregation and opinion dynamics barely matter.
- **Without noise, bad experiences act as a cliff.**
  - Every run takes off at ≤0.001 breakdowns per step; almost none take off at 0.002.
  - A ≥10% slowdown already appears at 0.0005.
  - Letting complaints fade turns the cliff into a slowdown.
- **The apparent benefit of segregation came from early adopters starting together,** not from segregation itself.
- **The prototype gives a believable S-curve without noise.** Adoption reaches about 13% at 10 years and 55% at 25 years. Without word of mouth it reaches 5%. Results are stable across seeds (SD about 1 point).
- **In the prototype, negative word of mouth slows adoption gradually.**
  - About 10% slower adoption at 10 years needs roughly 5–10% of new owners to be dissatisfied.
  - How often owners are dissatisfied matters more than how much a complaint weighs.
  - How long complaints last decides most of the long-run effect.
  - Even dissatisfied owners who say nothing slow adoption, because they are lost as positive voices.
- **Network structure barely changes overall pace.**
  - Local vs long-range ties make at most about 1–2 points of difference.
  - Credibility from owners in similar homes is the only option that makes structure matter (about +3 points at 10 years).
  - The network does not change how much negative word of mouth matters.
- **Structure and negative word of mouth matter most for gaps between household types.**
  - Segregation plus clustered early adopters roughly double the gaps in adoption between types.
  - Negative word of mouth hits the types already behind 2–3× harder. At 25 years, with 10% of owners dissatisfied, social flats lose about 22–37% of adoption against about 8–15% for detached homes.

## Possible next steps

1. Decide whether to adopt the trigger and owner-word-of-mouth mechanism, keeping the current model as a switchable comparator.
2. Find evidence for the dissatisfied share and for how long complaints last, e.g. satisfaction surveys and complaint data.
3. Calibrate against data, for example:
   - the install rate over time;
   - whether heat pumps cluster by building type beyond distance alone, in EPC or MCS data.
4. Report the gaps between household types alongside total adoption as a headline outcome.
5. Check that the pattern across types is not an artefact of how the capability gate and the household characteristic are assigned to LSOA types.

## Running the scripts

Run from the project folder (`heatpump-opinions/`) with the project venv, e.g.

```
.venv\Scripts\python.exe analysis\negative_wom\proto.py probe
```

- **Outputs:** world files and CSVs go to `results/negative_wom/`, which is gitignored. Nothing under tracked `results/` files is touched.
- **Archetypes:** `archetypes.json` holds the six LSOA-type archetypes, so the national LSOA data isn't needed. `python common.py derive` rebuilds it from that data.
- **Run times:** each run builds an 11,104-household world. A single prototype run takes under a second once the network is cached. The full sweeps below take from about 10 minutes to about 45 minutes each.

| Script | Entry points | Produces |
|---|---|---|
| `nwom.py` | `check`, `time`, `sweep` | `w` weighting in the current (noisy) model |
| `lownoise.py` | `probe`, `sweep` | Current model, noise removed |
| `cliff.py` | `A`, `B`, `C`, then `report` | Takeoff probability; random first owners; fading voices |
| `proto.py` | `probe`, `checks`, `report` | Prototype mechanism, uncalibrated |
| `proto2.py` | `calib`; `fixes 0.3 0.06 A`, `fixes 0.3 0.06 B`; `report` | Calibration, equal contact rates, dose-response |
| `proto3.py` | `run 1,2,3 tag`, `report` | Network options and the shuffled-network comparison |
| `proto4.py` | `calib`, then `net <seeds> <tag>`, `dose <seeds> <tag>`, `report` | Options matched to the same pace, dose-response and type gaps |

The `cliff`, `proto3` and `proto4` sweeps can be split across processes by part or by seeds, as above.
