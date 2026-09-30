# Design note: from toy model to the real question

**Status: proposal.** No part of the model described here is implemented. The
only *new* code on this branch is the data pipeline in `data_prep/` and the
LSOA typology in `analysis/lsoa_types.py`; the existing simulation in
`heatpump_sim/` is untouched, and the sections below that describe it describe
it as it stands on `main`. This note explains what the new code was built for
and what we now think the model should become, so the three can be reviewed
together.

Figures quoted below come from the joined LSOA table produced by
`data_prep/build_lsoa_table.py` and from `analysis/lsoa_types.py` run over all
33,755 English LSOAs. None of them come from a simulation run — no version of
the model described here has been run.

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
fraction of households gated by motivation — those for whom flipping
motivation flips the outcome and nothing else stands in the way. Adoption
needs decision right, capability, opportunity, motivation and a trigger all at
once, and word of mouth acts on motivation alone. It is computed by
`analysis/motivation_gated.py`.

There are two such populations, one in each channel where the household
decides (see Adoption channels below):

- **Social tenants in houses.** The landlord supplies capability, opportunity
  and timing, so consent is what remains. A refusal is a permanent loss.
- **Able-to-pay owner-occupiers in houses.** Every static gate is in place;
  once the trigger (boiler failure) arrives, motivation decides. The trigger
  is a matter of time rather than a barrier, so over a run motivation governs
  both whether and when they adopt. Demotivation delays rather than destroys
  here — but the output is speed of adoption, so delay is inside the effect.

| | Social tenants in houses | Able-to-pay owners in houses | Total |
|---|---|---|---|
| England | 11.8% (5.3–15.5) | 42.3% (31.6–60.1) | **54.1%** (36.9–75.6) |
| Derby | 14.7% | 41.7% | 56.4% |
| Nottingham | 18.8% | 25.8% | 44.6% |
| Social estates — houses | 32.3% | 22.4% | 54.7% |
| Social flats | 16.0% | 5.4% | 21.4% |

Percentages of households. The Census gives tenure and dwelling type
separately per LSOA and income deprivation comes from IMD, so the joint counts
are not observed: the point figures assume independence within each LSOA, and
the brackets are Fréchet bounds — the full range consistent with the margins,
no assumption made. Independence probably overstates social tenants in houses
(they are likelier than their neighbours to live in flats) and understates
able-to-pay owners (income deprivation concentrates among renters). "Able to
pay" means not income-deprived on the IMD income score, which is a generous
proxy: not being on means-tested benefits is a far lower bar than affording a
heat pump net of the grant.

So the population word of mouth can act on is **not small** — about half of
England — and the two channels matter in different ways. The social channel is
smaller but loses installs outright where the subsidy is fullest; the owner
channel is four times larger and loses time. They should be reported side by
side, not only summed.

The typology localises the diagnostic but does not contain it. Only **40%** of
England's social tenants in houses live in the **social estates — houses**
type; the rest are spread through mixed terraced (18%), owner-occupied semis
(15%) and suburban detached (14%) areas. So most of the social channel lives
outside the type the plane concentrates it in, and the type's household share
is not the bound.

## Geography: a stylised plane

Real coordinates are dropped. The model runs on a grid whose cells each carry
the characteristics of a *kind* of LSOA, and the arrangement of those cells is
swept rather than inherited from one town.

The previous design had already parameterised away most of what real geography
was supposed to buy: long-range ties came from a swept rewiring probability,
households were scattered around centroids anyway, and the between-town
difference in mean suitability was 2.7x smaller than the within-town spread.
Keeping real coordinates on top of that claimed a realism the model was not
delivering. Dropping them buys something the single town could not give:
correlated installer failure and negative word of mouth both cluster in space,
so whether quality spend pays off *should* depend on how segregated the
vulnerable population is. With one town you get one draw from that
distribution and no way to separate a property of the mechanism from a
property of Derby.

| Decision | Reason |
|---|---|
| **8x8 grid** of cells, allocated to types by national frequency | At 4x4 the social-flats type gets a single cell (6.3% x 16 = 1.0), so the arrangement of the type where negative word of mouth should bite hardest cannot be varied at all. At 8x8 it gets four. |
| Each cell is a **real LSOA sampled from its type**, not the type centroid | Types are used to *arrange* the plane, not to generate the data on it. Sampling keeps the empirical joint distribution of tenure, dwelling and income — no need to model those correlations — and keeps the within-type spread that makes capability vary between neighbours. That spread is large: social flats have sd 0.21 on a mean flat share of 0.66. Centroids would flatten exactly the local heterogeneity that makes neighbour-to-neighbour influence meaningful. |
| Arrangement set by a **target spatial autocorrelation, swept** | "Similar types adjacent" vs "scattered" as two hand-built scenarios gives two points; a continuous axis puts arrangement on the same footing as the other unmeasured quantities below. |
| Cells are **equal-area and roughly equal-population** | LSOAs are built to equal population (~650 households), so equal cells are the natural unit. Household counts still vary (roughly 400–1,200), which varies local density and hence network degree — that is a confound to state, not to hide. |
| Representativeness by **matching the England type distribution** | A stronger and cheaper claim than picking places that feel typical. |

### The LSOA typology

Produced by `analysis/lsoa_types.py`. k-means over all 33,755 English LSOAs on
six variables — and only six, because a type is meaningful here solely insofar
as it changes the joint distribution of the model's gates:

| Gate | Variables |
|---|---|
| Decision right | social rented share, private rented share (owner-occupied is the residual) |
| Capability | flats, detached, semi-detached share (terraced is the residual) |
| Opportunity | IMD 2025 income score |

Dropping one category per composition is not tidiness: keeping all of them
makes the covariance singular and silently double-weights housing mix against
income. k-means is written out in numpy rather than pulled from a library, so
the method is visible to a reader who has to be persuaded, and so the project
gains no new dependency.

| Type | % LSOAs | % h/holds | Own | Soc | Priv | Dominant dwelling | Income score | Urban |
|---|---|---|---|---|---|---|---|---|
| Suburban/rural detached | 27.6 | 27.7 | .81 | .06 | .13 | detached .53 | 0.105 | 50% |
| Urban owner-occupied semis | 21.2 | 20.0 | .77 | .10 | .13 | semi .56 | 0.159 | 85% |
| Mixed terraced, private-rented | 20.6 | 21.1 | .59 | .13 | .27 | terraced .40 | 0.245 | 91% |
| **Social estates — houses** | 15.2 | 14.5 | .46 | .39 | .15 | semi .42, terraced .33 | 0.430 | 93% |
| City-centre flats, private-rented | 9.1 | 10.1 | .37 | .15 | .48 | flats .68 | 0.238 | 99% |
| **Social flats** | 6.3 | 6.7 | .27 | .49 | .24 | flats .66 | 0.461 | 100% |

England for comparison: 62.3% owner-occupied, 17.1% social, 20.6% private
rented; 22.9% detached, 31.5% semi, 23.0% terraced, 22.2% flats.

**Why six.** Not because a fit statistic said so. Bootstrap stability — resample
LSOAs, recluster, score each cluster by how reliably it reproduces — puts
*every* k from 2 to 10 above 0.85 on Hennig's Jaccard criterion, where 0.75 is
the conventional threshold for a real cluster. At n=33,755 a bootstrap barely
moves a centroid, so a high score alone means little, and inertia falls
smoothly with no elbow. Run against a null with the same mean and covariance
but no clusters by construction (`--null-check`), the real data beats the null
clearly at k=3 (0.99 vs 0.69) and k=6 (0.97 vs 0.81) but barely at k=4 (0.99
vs 0.97) — a structureless ellipsoid also cuts stably into four. So stability
establishes that the partition reflects real structure and is not an artefact;
it does not choose the number of types.

That choice is a modelling judgement: **the smallest k that separates the
situations the model treats differently.** At k=5 the two social types merge
into one 16.4% cluster mixing flats and houses, which destroys the distinction
the research question rests on — social tenants in houses are gated by
motivation *alone*, social tenants in flats are gated by capability as well.
k=6 is the smallest k that keeps them apart, and every type it produces has a
one-line name, which is the practical test of whether a typology can be
explained.

### The real towns become the calibration point

Derby and Nottingham are not discarded; they stop being the simulation
geography and become a reference mark on the arrangement axis. Their observed
spatial autocorrelation in the gate variables says where real English
segregation sits on the swept scale, so a result reads "quality spend wins
above this level of clustering, and real towns sit here" rather than "quality
spend wins in Derby."

Their type composition also quantifies the earlier claim that Nottingham is
where the lever bites:

| | Social estates — houses | Social flats | Both |
|---|---|---|---|
| Derby | 22.4% | 3.9% | 26.3% |
| Nottingham | 38.0% | 8.4% | 46.4% |
| England | 15.2% | 6.3% | 21.5% |

Derby is close to England on tenure (59.8% owner-occupied against 62.3%);
Nottingham is not (45.6%). The earlier caution still holds and is now easier
to act on: **E06000018 is not the city.** It is the administrative core —
Beeston and West Bridgford sit in Broxtowe and Rushcliffe — so its 179 LSOAs
cover roughly half the urban area, and the excluded ring is disproportionately
owner-occupied and less deprived. The truncation shows in what is left: the
179 included LSOAs have a mean income decile of 3.50, against 4.67 for Derby,
so the calibration reference is drawn from the more deprived half of the
conurbation. (The ring itself is not quantified here — it falls in LADs
outside the study areas.) As a calibration reference rather than a simulation
target, that
truncation biases the reference mark rather than the whole study, which is a
much cheaper error to carry.

**What this costs.** A policy reader hears "we simulated Derby" differently
from "we simulated a stylised plane calibrated to the English LSOA
distribution". The calibration point recovers most of that, but not all of it,
and it is a fair objection to expect.

## Input data

Everything below is Open Government Licence.

| Source | Role |
|---|---|
| Census 2021 **TS041** | How many agents per LSOA |
| Census 2021 **TS054** tenure | Which adoption channel a household is in, and which funding route applies; also a clustering variable |
| Census 2021 **TS044** accommodation | Capability, varying *per household*; also a clustering variable |
| **IMD 2025** income score | Opportunity; also a clustering variable |

One further variable is used but not clustered on: the rural/urban
classification, which is what the `% Urban` column of the typology table
reports. It currently reaches the table through the **Nesta** workbook rather
than from ONS directly — see the open question below.

**Nothing further needs downloading.** LSOA population-weighted centroids were
the one outstanding fetch under the real-geography design; the stylised plane
does not need them. Every source above is already in `data/raw/`, and all of
it is national — `build_lsoa_table.build(study_areas_only=False)` returns all
33,755 English LSOAs, because the subset to the study towns was the only thing
narrowing it.

**Nesta suitability is dropped as the capability variable.** Across all 33,755
English LSOAs its ASHP score correlates -0.91 with the proportion of flats
(-0.97 within Derby and Nottingham alone), so Census TS044 carries
essentially the same signal — on a cleaner licence, and with the decisive
advantage that it varies *within* an LSOA. Nesta gives every household in an
area the same mean score, which erases exactly the local heterogeneity that
makes neighbour-to-neighbour influence meaningful.

Open question: whether Nesta is kept at all. It is currently the only source
of grid capacity, off-gas proportion and the rural/urban classification. If
the Census 2021 central-heating table covers off-gas per LSOA — **not yet
verified** — Nesta can be dropped entirely: grid capacity becomes a scalar
sensitivity parameter, and the rural/urban class is separately published by
ONS under OGL, so it is a lookup to swap in rather than a loss. That
would make the whole input set OGL and remove the CC BY-NC-SA share-alike
condition from anything derived, which is worth having.

The case for keeping it has weakened. Building the table nationally showed
that Nesta's grid capacity is **missing for 1,284 English LSOAs (3.8%)**, in
contiguous blocks — the whole of Bexley, for instance — which looks like
absent DNO coverage rather than disclosure control. Both study towns happen to
be complete, which is why this never surfaced while the build was subset to
them. A variable that is both an acknowledged edge case (below) and
systematically absent for whole regions is a thin reason to carry a
non-commercial share-alike licence through the whole project.

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
what gives `characteristic` something to do — it is currently generated and
carried through the run, but influences behaviour in exactly one place
(`agents.py:107`, the initial-owner draw) and never appears in `dynamics.py`.

### Adoption channels

Tenure does not simply switch households on and off. It puts a household into
one of three channels with different gates and different clocks: one initiating
channel and two landlord channels. Between them they account for every
household — 62.3%, 17.1% and 20.6% of England.

**Owner-occupiers** (62.3% of English households; 59.8% Derby, 45.6%
Nottingham) initiate. They must pass all five gates, and the trigger is boiler
failure, so a demotivated household *delays* rather than being lost.

**Social tenants** (17.1% of English households; 25.5% in Nottingham) do not
initiate, but they can
refuse — which reflects the real situation, since social landlords need
tenant consent for major works in occupied homes. The landlord funds the
install, handles suitability and sets the timing, so capability, opportunity
and trigger all fall away and **motivation becomes the dominant remaining
gate** — dominant rather than sole, because refusal also turns on disruption,
cylinder space and trust in the landlord (below). This makes social housing
the sharpest test of the research question rather than inert background: it is
where word of mouth acts most directly on the outcome, it is concentrated on
estates where both negative word of mouth and correlated installer failure
cluster hardest, and it is where a fully-subsidised quality top-up would land.

The asymmetry matters. In the social channel a refusal is pure loss — budget
committed, offer made, declined — so negative word of mouth destroys installs
one for one, exactly where the subsidy is fullest. In the owner-occupier
channel it only postpones them. The social channel is also the cleaner policy
test bed, because install volume is centrally decided rather than emergent.

Refusal is therefore not driven by motivation alone; disruption, cylinder
space and trust in the landlord all feed in, and belong in the refusal
probability as parameters. Word of mouth moves the motivation term; the others
set how much a given shift in motivation is worth.

The typology splits this channel in two, and the split is load-bearing.
**Social estates — houses** is where the non-motivation gates come closest to
falling away entirely. **Social flats** carries a comparable social-rented share
(0.49 against 0.39) but two thirds of the dwellings are flats, so capability
binds as well and most of its tenants fall outside the motivation-gated count. Treating "social
housing" as one population would average across that distinction and overstate
the reachable effect.

**Private renters** (20.6% of English households; 28.9% in Nottingham) are the
third channel: the same landlord structure and the same tenant veto, but a
different landlord incentive — the split-incentive problem means the landlord
rarely initiates at all. Modelling them as a low-rate landlord channel is the
obvious first cut. They are a fifth of England and cannot be left out of a
model whose outcome is the speed of national adoption.

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

## The influence graph

Nothing above has said how households are connected to each other, and the
current `network.py` offers Barabasi-Albert (the default), Erdos-Renyi and
Watts-Strogatz — none of which makes any reference to coordinates. That is
incompatible with the rest of this note. If the influence
graph is spatially blind then clustering failures in space does nothing
whatsoever to the dynamics — a failed household's neighbours are a uniformly
random sample of the population regardless of where the failure happened — and
the correlated-failure axis, which is the one the study exists to vary, is
inert.

So the graph has to be spatial. The point of this section is that most of its
parameters are not free choices: there is evidence for them, and using it turns
the largest sweep axes into calibrated ones.

### Parameters and their sources

| Parameter | Central | Sweep | Source | Status |
|---|---|---|---|---|
| Distance kernel | exponential, lambda = 210 m | 100–500 m | Barton-Henry, Wenz & Levermann (2021), *Sci Rep* — every solar panel in Fresno from satellite imagery, exponential fit, half-distance ~145 m | Measured, but US suburban and roof-visible |
| Mean degree | 15 | 5–20 | Dunbar sympathy group: alters contacted at least monthly | Analogue. Nobody has measured "people whose heating you hear about" |
| Long-range tie fraction | 0.30 | 0.1–0.5 | Liben-Nowell et al. (2005), *PNAS* — about a third of friendships are independent of geography; remainder decay as rank^-1 | Measured, but friendship rather than heating talk |
| Local contact rate | 0.72 / month | 0.69–0.78 across the deprivation and urban/rural gradients | Community Life Survey: 72% of adults in England chat to neighbours at least monthly | Measured, England, direct |
| Long-tie contact rate | 0.25 / month | 0.1–0.5 | none found | Assumed |
| Installer batch size | 30 installs / year | 10–100 | MCS: 57,918 certified installations in 2024 against ~1,935 certified heat pump businesses | Measured, but the mean of a heavily skewed distribution |
| SES homophily beyond geography | 0 | 0–0.3 | UK Social Capital Atlas (6bn friendships): below-median-SES people hold 47% of their friendships with above-median-SES people, against 50% under random mixing | Measured; most of the observed sorting is residential, not friending |

Verification status: the Fresno figure and the heat pump null below are taken
from abstracts and press summaries — both full texts were paywalled at the time
of writing. Neither should be treated as load-bearing until read properly.

### Construction

Edge probability follows the kernel `w(d) = exp(-d / lambda)`, normalised so
that the realised mean degree hits its target. A fraction `p` of edges is then
rewired to uniformly-chosen long-range targets, degree-preserving.

Normalising the kernel to a target degree is what removes the choice between a
*k*-nearest-neighbour graph and a fixed-radius geometric one. It does **not**
remove the density confound noted in the geography table above. The
normalisation is a single global scalar chosen so the population mean degree
hits its target; a household in a denser cell still has more neighbours inside
210 m than one in a sparser cell, and so still ends up with higher degree. Only
a per-household normalisation would break that link, and that is *k*-nearest
neighbours in disguise — the very choice the normalisation is there to avoid.
So the confound stands and has to be declared: cells vary in household count
(roughly 400–1,200), and degree varies with it.

Rank-based rather than uniform long-range targets would be closer to
Liben-Nowell, but across a single 8x8 plane the two are indistinguishable, so
uniform is assumed.

### Three consequences worth stating before anything is run

**The arrangement sweep is not inert — checked.** The worry was that a 210 m
decay radius would keep nearly all influence inside a cell. The share of edges
crossing a cell boundary is computable from the kernel and the cell geometry
alone, with no dynamics, and `analysis/edge_crossing.py` computes it.

Cell size comes from the data: LSOA areas (households divided by Nesta's
property density, which sum to England's 130,311 km²) give a median urban cell
side of **~600 m** (interquartile 490–800 m; social flats ~450 m). The kernel's
mean edge length at lambda = 210 m is ~400 m — comparable to a cell, not small
against it. At the central values (600 m cells, lambda 210 m, long-range
fraction 0.30), **58% of local edges cross into another cell**, almost all into
an adjacent one.

Which edges can feel the arrangement needs stating carefully, because an
earlier draft of this note had it backwards. Long-range edges go to uniformly
random targets, so the type they land in follows the plane's overall mix
*whatever the arrangement* — they are blind to it. Only local edges that cross
into a neighbouring cell connect a household to a neighbour whose type the
arrangement sets. The **arrangement-sensitive share** is therefore
`(1 - p) x local crossing share`: **41%** at the central values, and 13–78%
across the swept ranges (23% even at lambda = 100 m). The sweep axis is live.

Simplifications behind those figures: households are spread uniformly, cells
are square and equal-area, and the plane has hard edges. Density comes from
the Nesta workbook; ONS LSOA boundaries (OGL) would give the same areas.

Had the check come back small, the plane would still have earned its place,
but on a narrower claim, and the note should have said so rather than quietly
kept the wider one. Two of the three things the plane buys survive an inert arrangement axis:
sampling real LSOAs preserves the empirical joint distribution of tenure,
dwelling and income without anyone having to model those correlations, and
failure correlation still clusters *within* cells, which is the mechanism the
study exists to vary. What would not survive is the specific argument in the
geography section that dropping real coordinates buys a segregation axis. In
that case the honest response is to report the edge-crossing share, drop the
arrangement sweep to a two-point check rather than a continuous axis, and
retire the segregation claim — not to widen the kernel until the axis moves,
which would be choosing lambda to get a result.

**The contact-rate gradient runs against the estates argument.** This note
argues that social estates are where word of mouth bites hardest, on the grounds
that both negative word of mouth and correlated installer failure cluster there.
But neighbour contact is *lowest* in the most deprived areas — 69% against 76%
in the least deprived, and 71% urban against 78% rural — and the social estate
types sit at the deprived end (income score 0.43 and 0.46 against 0.11 for
suburban detached). The mechanism is therefore a tug-of-war between two measured
quantities rather than a one-way argument. It does not overturn the case, since
the tenure and failure-clustering effects are large, but it should be stated
rather than discovered by a referee.

**Heat pumps show no measurable neighbour effect in the best available UK
data.** Cambridge EPRG (CWPE 2566) covers 1.4 million solar PV systems in
England and Wales, 2010–2024: positive spatial-neighbour effects in 2010–2015
(an additional system in a local authority is associated with 0.128 additional
installations three months later), negative thereafter as the adopter pool
saturates, and no such effect for heat pumps at all. At local-authority
resolution and ~1% penetration this is a low-powered test, and a 210 m decay
radius would be invisible at that scale almost by construction. It is
nonetheless the most directly relevant UK evidence in existence, and it gives
this project two things: a **validation target** — the model, run at current
penetration and aggregated to local-authority level, should also show no
detectable neighbour effect — and a further argument for the boundary framing,
since the effect being modelled currently sits below the detection threshold of
the best data available. The PV result is the stronger target: 0.128 per system
per three months, pre-saturation, is a number the influence graph could be asked
to reproduce.

Preferential attachment is kept only as a deliberately unrealistic comparator.
At `m=3` it produces hubs with degree in the hundreds; a single hub failure then
poisons a large fraction of the population and the results become hub results.

## What is data and what is swept

Data fixes the joint distribution of gates and how it clusters in space.
Everything about the word-of-mouth mechanism itself is unmeasured and
belongs on a sweep axis:

- negative/positive word-of-mouth asymmetry
- word-of-mouth decay rate
- failure correlation (shared installer, estate, batch)
- the quality-response curve `g(spend) -> breakdown_rate`
- long-range tie fraction — swept, but around an anchor of 0.30 rather than
  across the whole unit interval (see the influence graph section above)
- **spatial arrangement of LSOA types on the plane** (target autocorrelation,
  from fully mixed to strongly segregated)
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
- **Over half of Nottingham's households do not initiate** (45.6%
  owner-occupied, against 59.8% in Derby, 62.3% in England) — but under the
  channel model above they can still refuse, so they are active in the
  dynamics rather than passive recipients.
- **The typology is stable but the number of types is a judgement.** Every k
  from 2 to 10 clears the conventional stability threshold, so the argument
  for six rests on which distinctions the model needs, not on a statistic.
  Stated plainly above rather than dressed up as model selection.

## Points resolved before circulating

An internal consistency pass over this note found several places where it
argued both sides of a question. Those are now settled one way, and the
choices are recorded here so a reviewer can reopen them knowingly rather than
discover them as contradictions.

| Question | Settled as |
|---|---|
| Does the kernel's normalisation remove the density-degree confound? | **No.** A global normalisation sets the population *mean* degree; it does not stop a household in a denser cell having more neighbours within 210 m. Only per-household normalisation would, and that is *k*-NN in disguise. The confound is declared, not dissolved. |
| Two adoption channels or three? | **Three.** Private renters are a fifth of England; a two-channel framing left them unaccounted for. |
| Is motivation the *only* gate for social tenants? | **Dominant, not sole.** Disruption, cylinder space and trust in the landlord sit in the refusal probability alongside it. |
| Which households are gated by motivation? | **Both** social tenants in houses **and** able-to-pay owners in houses — one population per channel where the household decides. Reported separately, because one loses installs and the other loses time. |
| What if the arrangement sweep turns out inert? | Report the edge-crossing share, reduce the sweep to a two-point check, and retire the segregation claim. Do not widen lambda until the axis moves. (Checked: it is not inert — 41% of edges are arrangement-sensitive at central values.) |

Two figures were also corrected: the Nesta-flats correlation is -0.91 across
England (-0.97 was Derby and Nottingham only), and the 3.50 mean income decile
describes Nottingham's included LSOAs, not the excluded suburban ring.

## For review

1. Stylised plane instead of a real town — is trading the "we simulated
   Derby" framing for arrangement-as-a-swept-variable the right trade? The
   edge-crossing check it was contingent on has come back in its favour.
2. Six types, or is the social houses/flats split worth more resolution
   (k=8 separates further but the real-vs-null stability gap narrows to
   +0.07, against +0.16 at k=6)?
3. 8x8 grid, or larger? 8x8 is the smallest that gives the rarest
   policy-relevant type more than one cell.
4. Drop Nesta entirely, or keep it for grid capacity and off-gas — given
   grid capacity is missing for 3.8% of England in contiguous blocks?
5. Is the boundary-in-parameter-space framing the right deliverable?
6. The influence graph parameters are anchored on solar PV and on friendship
   data rather than on anything about heating. Is that borrowing defensible, or
   does it need saying more loudly than a status column in a table?
7. Given that heat pumps show no measurable neighbour effect in the England and
   Wales data, is "no detectable local-authority-level effect at current
   penetration" the right validation target — and if the model fails it, which
   of the two do we disbelieve?
