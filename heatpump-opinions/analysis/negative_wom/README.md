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

## Design rationale for the prototype

The prototype answers the 30 Sep meeting's conclusion that adoption has to happen without noise before negative word of mouth can be studied. It rests on four choices.

1. **Word of mouth based on experience.**
   - Only owners talk. In the current model everyone's opinion averages towards their neighbours', so non-owners "spread" opinions they have no experience of.
   - Contact rates come from DESIGN.md.
   - What a household hears fades towards its own starting motivation, so motivation needs ongoing input.
2. **Trigger → choice → lock-in.**
   - A household considers a heat pump only when its boiler fails, it moves, or similar (1/180 a month).
   - It then chooses with a logistic probability of its motivation.
   - Saying no means waiting for the next trigger. This replaces a threshold crossing that noise eventually forces, and fits the COM-B "trigger" idea.
3. **Dissatisfied owners replace breakdowns.** Three separate settings: how many (`q`), how much a complaint weighs (`w`), and for how long (`duration`).
4. **Five checks the mechanism had to pass:**

   | Check | Result |
   |---|---|
   | (i) S-curve with no dissatisfaction, driven by word of mouth | Pass |
   | (ii) Robust to seed | Pass |
   | (iii) Network effect in the expected direction | Weak; only the same-building-type option produces one |
   | (iv) Extremes span the full range | Pass |
   | (v) Can reproduce the current model | Fails by design: a different class of model. Keep the current one as a comparator |

**How robust each finding is.**
- **Robust across every variant:**
  - the cliff without noise, and fading voices removing it;
  - dissatisfaction acting as a gradual slowdown in the prototype;
  - how often owners are dissatisfied mattering more than how much a complaint weighs;
  - lagging types being hit harder.
- **Fragile:** every absolute number, since all settings are placeholders and the calibration rests on one rough install rate.
- **The network results are conditional on these assumptions:**
  - about 15 contacts each;
  - triggers spread uniformly;
  - no installers, grants, costs or landlord decisions.

## Where each finding comes from

Tables are in [RESULTS.md](RESULTS.md).

| Finding | Command | RESULTS.md |
|---|---|---|
| Current model is noise-driven; the `w` needed depends on noise | `nwom.py sweep` | 1 |
| Without noise, bad experiences act as a switch | `lownoise.py sweep` | 2 |
| Sharp cliff; first-owner placement; fading voices | `cliff.py A`, `B`, `C`, then `report` | 3 |
| Prototype S-curve, checks, extremes, silent owners | `proto.py checks` | 4 |
| Calibration; the local vs long-range difference came from contact rates | `proto2.py calib`, `fixes 0.3 0.06 A` | 5 |
| Network options compared without matching pace | `proto3.py run` | (superseded by 6) |
| Network options at the same pace; type gaps | `proto4.py calib`, then `net` | 6 |
| Dose-response; shortfall by type | `proto4.py dose` | 7, 8 |

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

**How the scripts depend on each other:**
- `common.py` provides the paths and archetypes; every script imports it.
- `nwom.py` holds the vectorised current model (`run`, `base_settings`).
  - `lownoise.py` and `cliff.py` import it and set `nwom.N_STEPS = 300` when imported.
  - `proto.py` and `proto3.py` use its `base_settings` to build the worlds.
- `proto.py` holds the prototype. `proto2.py` imports it and passes the calibration (0.3, 0.06) as arguments.
- `proto3.py` is a copy of the prototype with network options A–C, the shuffled network and type metrics added. It does not import `proto.py`. With options off and contact rates equal, it gives the same distribution of results as `proto.py`, though not identical runs (one random draw differs).
- `proto4.py` imports `proto3.py`. Run `proto4.py calib` first: it writes `results/negative_wom/proto4_calibration.json`, which `net` and `dose` read.
- Each `report` reads the CSVs its sweep wrote to `results/negative_wom/`.
