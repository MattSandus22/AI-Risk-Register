# Risk methodology

This document explains how the register scores, treats and reviews AI risks, and how the framework mappings work. The defaults live in each register's `config.yaml` and can be changed to match an organization's existing enterprise risk methodology.

## 1. Scope: what goes in the register

- **AI systems** (`systems.yaml`): every AI system the organization builds, buys or uses in a business process, including third-party models used through an API or SaaS product. Each system has an accountable owner, a lifecycle stage and, where relevant, an EU AI Act risk tier.
- **Risks** (`risks.yaml`): an event, tied to one system, that could harm the organization, individuals or society. Write each risk as *cause → event → consequence* ("Instructions hidden in retrieved content cause the assistant to reveal another customer's order details").
- **Governance controls** (`governance.yaml`): organization-wide controls such as policy, committees, inventory and impact-assessment procedures. They apply to every system, so they are recorded once rather than repeated against each risk.

## 2. Risk categories

Risks are categorized by the **trustworthy characteristics** in NIST AI RMF 1.0:

| Key | Characteristic |
|---|---|
| `valid_reliable` | Valid and reliable |
| `safe` | Safe |
| `secure_resilient` | Secure and resilient |
| `accountable_transparent` | Accountable and transparent |
| `explainable_interpretable` | Explainable and interpretable |
| `privacy_enhanced` | Privacy-enhanced |
| `fair_bias_managed` | Fair, with harmful bias managed |

Using a fixed taxonomy makes it possible to compare risk exposure across systems ("Where is our privacy exposure concentrated?").

## 3. Scoring

Each risk is rated on two 1–5 scales.

| Rating | Likelihood (over 12 months) | Impact |
|---|---|---|
| 1 | Rare: not expected to occur | Negligible: no meaningful harm |
| 2 | Unlikely: could occur, no history | Minor: limited, quickly reversible harm |
| 3 | Possible: has occurred in similar systems | Moderate: noticeable harm to individuals or operations |
| 4 | Likely: expected to occur at some point | Major: significant harm, regulatory attention, or loss of trust |
| 5 | Almost certain: occurring now or expected repeatedly | Severe: serious harm to people's rights, safety or livelihoods; enforcement action |

**Score = likelihood × impact** (1–25), banded by default as:

| Band | Score |
|---|---|
| Low | 1–4 |
| Medium | 5–9 |
| High | 10–15 |
| Critical | 16–25 |

- **Inherent** ratings assume no AI-specific controls are in place.
- **Residual** ratings reflect controls that are **implemented**, not planned. The validator warns when a residual score is lower than the inherent score but no treatment is implemented, because the reduction isn't yet supported by evidence.
- Residual likelihood and impact can never exceed their inherent values.

Most treatments reduce likelihood. Impact usually changes only when a control limits the scale of harm (for example, scoping retrieval so a breach can expose one customer instead of all of them).

## 4. Risk appetite and acceptance

`risk_appetite` (default **9**, the top of Medium) is the highest residual score the organization tolerates without further action.

A risk whose residual score is above appetite must either:
- have treatments that are being implemented (`mitigate`, `transfer` or `avoid`), or
- be formally **accepted**, with an `acceptance` block naming the approver, approval date, expiry date and rationale.

Acceptances expire. An expired acceptance is an error, which forces re-approval or treatment instead of letting accepted risks linger. Approvers should hold authority proportionate to the risk; for example, Critical risks are accepted only by an executive.

## 5. Review cadence

Each risk must be re-reviewed on a schedule set by its residual rating (`review_days`):

| Residual rating | Review every |
|---|---|
| Critical | 30 days |
| High | 90 days |
| Medium | 180 days |
| Low | 365 days |

A review re-confirms the ratings, treatment status and owner, then updates `last_reviewed`. Risks never reviewed, or past their review date, are flagged.

## 6. Framework mapping

Every treatment and governance control can reference:

- **NIST AI RMF 1.0** Core categories (`GOVERN 1` to `MANAGE 4`) or subcategories (`MEASURE 2.11`). Subcategories roll up to their category.
- **ISO/IEC 42001:2023** Annex A control objectives (`A.2` to `A.10`) or specific controls (`A.6.2.4`). Controls roll up to their objective.

`airisk coverage` reports, for each category or objective, whether it is:

- **Covered**: at least one implemented control references it.
- **Planned**: only planned or in-progress controls reference it.
- **Gap**: nothing references it.

A gap doesn't necessarily mean the requirement is unmet. It may be addressed outside the register (in HR or procurement processes, for example), but it should then be recorded as a governance control so coverage is evidenced in one place.

## 7. EU AI Act tiers

`eu_ai_act_tier` records the register owner's classification: `unacceptable`, `high`, `limited` or `minimal`. The validator enforces two rules:

- A system classified `unacceptable` (a prohibited practice) must be `retired`.
- A `high` risk system must document human oversight.

Classification under the EU AI Act is a legal determination. This field records the organization's conclusion; it does not make that determination.

## 8. Limitations

- Likelihood × impact is an ordinal scale. Scores are useful for prioritization, not arithmetic: a 12 is not "twice as risky" as a 6.
- The register shows what controls are claimed and planned. Verifying that they operate effectively still needs testing evidence, such as evaluation results, audit reports and logs.
