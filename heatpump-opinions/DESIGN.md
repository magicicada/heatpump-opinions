# Design note: from toy model to the real question

**Status: proposal.** Nothing here is implemented. The only code on this
branch is the data pipeline in `data_prep/`; this note explains what it was
built for and what we now think the model should become, so the two can be
reviewed together.

Figures quoted below come from the joined LSOA table produced by
`data_prep/build_lsoa_table.py`. None of them come from a simulation run —
no version of the model described here has been run.

## The question

Under a fixed total budget, should government spend more per installation on
installation quality — accepting fewer installs — in order to suppress
negative word of mouth and reach faster adoption overall?

The trade-off is `n_installs = budget / (base_grant + quality_spend)`.
Quality buys a lower breakdown rate; breakdowns generate negative word of
mouth; that suppresses motivation in the surrounding neighbourhood and slows
future adoption. Whether the trade is worth making is the output.

## What the answer should be

**A boundary in parameter space, not a pound-per-install figure.** The
quality-response curve — how much breakdown rate a pound of extra spend
actually buys — is unmeasured and load-bearing. A point estimate would rest
entirely on a number nobody has. A boundary ("quality spend wins when
failures are this correlated and word of mouth decays this slowly") is
robust to not knowing it, and is more useful to a policy reader anyway.

One diagnostic is worth computing **before any dynamics are run**: the
fraction of households gated *only* by motivation. Adoption needs decision
right, capability, opportunity, motivation and a trigger all at once, and
word of mouth acts on motivation alone. So that fraction bounds the entire
effect, and it falls straight out of the joint distribution in the LSOA
table. If it is small, that is a cheap and important finding.

## Geography

| Decision | Reason |
|---|---|
| One town: **Derby** (E06000015), 152 LSOAs, 105,654 households | Its unitary boundary matches its actual built-up area. |
| **Nottingham second**, as "where the lever bites", not as a contrast | 25.5% social rented is where a fully-subsidised quality top-up would land. It is not a contrast: the between-town difference in mean suitability (0.841 vs 0.824) is 2.7x smaller than the within-town spread. |
| Long-range social ties from a **swept rewiring parameter**, not from using several towns | Shortcuts are topological — a tie does its work by shortcutting the network, not by spanning kilometres. Nottingham and Derby are ~15 miles apart, which is not structurally distinct from a cross-city tie; using them as the source of "distant" ties fixes an unobserved quantity at one arbitrary value and gives a bimodal distance distribution that is an artefact of the sampling frame. |
| Households at **LSOA population-weighted centroids, scattered within the LSOA** | Enough spatial clustering for correlated failure (one installer, one estate). The ONS Postcode Directory (~1 GB) is precision we cannot justify while the network topology is parameterised anyway. |
| Representativeness by **reweighting LSOA composition** toward the England distribution | A stronger and cheaper claim than picking more places that feel typical. |

A caution on Nottingham: **E06000018 is not the city.** It is the
administrative core — Beeston and West Bridgford sit in Broxtowe and
Rushcliffe. Its 179 LSOAs hold 124,740 households, roughly half the
Nottingham urban area, and the excluded ring is disproportionately
owner-occupied and higher income. That shows up directly as a mean income
decile of 3.50 against Derby's 4.67. The truncation runs along exactly the
axes this model is sensitive to, so if Nottingham is used as the primary
case it should be defined by built-up area or travel-to-work area rather
than by the unitary authority.

## Input data

Everything below is Open Government Licence.

| Source | Role |
|---|---|
| Census 2021 **TS041** | How many agents per LSOA |
| Census 2021 **TS054** tenure | Who is a decision-maker at all, and which funding route applies |
| Census 2021 **TS044** accommodation | Capability, varying *per household* |
| **IMD 2025** income decile | Opportunity |
| **LSOA population-weighted centroids** | Placement. Not yet downloaded — the one outstanding fetch. |

**Nesta suitability is dropped as the capability variable.** At LSOA level it
correlates -0.97 with the proportion of flats, so Census TS044 carries
essentially the same signal — on a cleaner licence, and with the decisive
advantage that it varies *within* an LSOA. Nesta gives every household in an
area the same mean score, which erases exactly the local heterogeneity that
makes neighbour-to-neighbour influence meaningful.

Open question: whether Nesta is kept at all. It is currently the only source
of grid capacity and off-gas proportion. If the Census 2021 central-heating
table covers off-gas per LSOA — **not yet verified** — Nesta can be dropped
entirely and grid capacity becomes a scalar sensitivity parameter. That
would make the whole input set OGL and remove the CC BY-NC-SA share-alike
condition from anything derived, which is worth having.

Also dropped: ONS Postcode Directory, MCS installation records (not openly
published at postcode level), ONS MSOA income (redundant with the IMD income
domain, which is itself built from benefits receipt), and any
spatially-resolved motivation.

Motivation is deliberately **not** given a spatial distribution. It is the
endogenous variable — the thing the opinion dynamics are supposed to
produce. Initialising it from spatial data would bake in the answer. It
should be drawn from a national distribution, anchored on the DESNZ Public
Attitudes Tracker and optionally conditioned on tenure, and swept.

## Model structure

**Adoption requires five gates at once:** decision right (tenure) x
capability (dwelling) x opportunity (funding) x motivation x trigger. This is
what gives `characteristic` something to do — it is currently referenced in
exactly one line of `agents.py` (the initial-owner draw) and nowhere in
`dynamics.py`.

**Motivation is the only fast-moving state.** Capability is fixed over a run,
opportunity moves slowly. That is the whole reason the dynamics and the
policy lever both live there — not because motivation is the largest
constraint, but because it is the only one with feedback.

**Trigger events should replace the `noise_std` mechanism.** Boiler
replacement on a 12-15 year cycle does the same job of breaking the
bootstrap-percolation stall described in the README, but for a mechanistic
reason rather than a numerical one, and it sets the natural timescale of the
run. The current behaviour is a deliberate modelling choice and works; this
is a proposal to replace it, not a bug report.

**Broken households need a decay parameter.** As documented in the README,
a broken-down household's opinion is forced to 0 and excluded from further
updates, while neighbours continue to read it — so it is a permanent
negative anchor. Whether negative word of mouth persists indefinitely or
decays is precisely one of the things this study wants to vary, so it needs
to be a parameter rather than fixed at "forever".

## What is data and what is swept

Data fixes the joint distribution of gates and how it clusters in space.
Everything about the word-of-mouth mechanism itself is unmeasured and
belongs on a sweep axis:

- negative/positive word-of-mouth asymmetry
- word-of-mouth decay rate
- failure correlation (shared installer, estate, batch)
- the quality-response curve `g(spend) -> breakdown_rate`
- network rewiring probability
- initial motivation distribution
- seed adoption (~1% of households, England's current penetration)

Treating these as sweep axes is the design, not a compromise for missing
data. Failure correlation is the one most worth attention: if bad installs
cluster, damage is superlinear in the failure rate, and quality spend may
work chiefly by *decorrelating* failures rather than by reducing them.

## Scope checks already done

- **Grid capacity is an edge case, not a wall.** Nesta's supportable-household
  share has a median of 14% in Derby and 22% in Nottingham, against roughly
  1% current penetration nationally. The region of interest sits below it.
  Keep it as an off-by-default scenario switch.
- **Both towns are on the gas grid** — 1.8% and 5.8% off-gas, with only 20 of
  331 LSOAs above 20%. The fully-subsidised off-gas routes barely apply. If a
  genuinely informative second case is ever wanted, it is a rural or off-gas
  district, not another midlands city.
- **Over half of Nottingham's households are not the decision-maker** (45.6%
  owner-occupied, against 59.8% in Derby).

## For review

1. Derby or Nottingham as the primary case — typical town, or the one where
   the policy lever bites hardest?
2. Drop Nesta entirely, or keep it for grid capacity and off-gas?
3. Is the boundary-in-parameter-space framing the right deliverable?
