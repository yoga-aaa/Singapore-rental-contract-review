# Singapore Rental Contract Review

Zhao Yujia | PE6201 Individual Project | 3 October 2026

## Problem statement

I am building a comparison assistant for international students renting in Singapore for the first time, across HDB and private residential housing. An illustrative user is a student comparing a draft lease before signing, unfamiliar with local contract language and looking for concrete questions to ask an agent. This persona represents the wider group, not one designated student.

The problem is locating potentially adverse obligations and the reference wording that supports a concern. The scope is selected English clauses, including deposits, repairs, termination, occupancy, rent and utilities. The CEA tenancy templates are comparison references, not mandatory legal standards. Whole-flat and room arrangements may be submitted as synthetic examples, but the templates do not cover every room-specific agreement. The system must abstain on uncovered arrangements.

The prototype accepts synthetic text or a readable PDF, previews extracted fragments, and requires confirmation before review. Housing-specific retrieval supports three labels: review_required, no_material_difference_found and insufficient_evidence. A supported risk includes an actionable question and an exact source excerpt. Equivalent wording or a clearly beneficial variation should not be flagged merely because the text differs. A passing comparison never means that an agreement is safe to sign.

The deployment decision is a classroom demonstration, not a real-contract service. Scans, legal advice, automatic landlord communication and personal documents are excluded. The external test shows that quality targets are not met; the prototype demonstrates an auditable workflow and its limitations rather than claiming reliable risk screening.

## Business and technical trade off analysis

### Technology and ownership

I chose a hybrid of deterministic checks, local BM25 retrieval and rented language models. Keyword rules are cheap and reproducible, but cannot reliably distinguish actors, triggers, exceptions or paraphrases. BM25 avoids embedding charges and keeps reference retrieval inspectable. It can miss semantic matches, so topic and clause routing supplement it. I did not implement the proposed FAISS index or train a classifier: the small dataset supports prompt development, not credible supervised training.

I own the Python orchestration, PDF intake, housing filter, reference parser, evidence validation, budget accounting and evaluation code. I use Streamlit for the interface and pypdf for extraction. I rent GPT-4.1 for drafts and GPT-4o for evidence checks through OpenRouter. These were chosen for structured comparison, at higher cost than the originally proposed single mini model. The second model is a component under test, not ground truth. I skipped low-code tools because exact-span checks and immutable evaluation artifacts were central; I do not claim a low-code trial that did not happen.

### Implemented workflow and limits

The user previews provisional PDF fragments and selects clauses. Scanned or poorly extracted pages stop processing rather than disappearing silently. The reference index separates HDB and private templates and retains numbered clauses, schedules and qualifying context. Local matches can produce evidence-backed results without model calls. Unsettled offline clauses are shown as model_needed, not completed predictions.

Live review uses a structured draft, deterministic citation checks and a second evidence check. The repaired v17 prompt selects contract-span IDs; the program attaches original text instead of accepting abbreviated quotations. New guards reject unsupported exhaustive rules, omitted dispute-fee mechanisms and confusion between replenishment and remedy periods. Unit tests, saved-output replay and a separately authorized paid regression test check these changes.

### Evaluation and economic decision

The development set contains 30 synthetic clauses. An older 20-case external set is now regression material. The new set has 20 DeepSeek-authored cases, reviewed in a separate DeepSeek chat according to the owner, then adjudicated and accepted before prediction. It is not legal-expert gold. Exact model versions and original chats are unavailable. The cases were seen during reference diagnosis, so the new batch is external-source diagnostic evidence, not a strictly untouched holdout.

The frozen v16 run achieved precision 1/2, recall 1/14, locator validity 4/4, and unsafe non-abstention 2/4; sixteen results abstained. The unchanged keyword baseline achieved precision 3/4, recall 3/14 and unsafe non-abstention 4/4. The baseline beat v16 on precision and recall. The separately frozen v17 regression, using unchanged labels on the same exposed cases, achieved precision 5/5, recall 5/14, unsafe non-abstention 0/4 and locator validity 6/6; fourteen results abstained. It improves label outcomes but is not independent generalization.

Correct labels and real source locations do not ensure correct explanations. The project-assistant citation audit supports 1/4 v16 and only 2/6 v17 non-abstaining results; uncertain judgments count as failures. Owner confirmation is pending. This provisional internal first pass is not expert review. The 95% substantive-support goal remains unmet, despite v17 precision of 100%.

Nine v16 cases contained abbreviated contract quotations. These disappear in v17, but incomplete coverage and unsupported reasoning remain. I preserve both runs and never relabel after prediction. A saved-output replay is not new model inference.

The v16 batch used 29 calls, 83,563 tokens and US$0.2383215; v17 used 36 calls, 99,584 tokens and US$0.2722430. Total spending was US$0.5105645. The v17 average is US$0.0136 per fragment. Twenty unrelated fragments are not one agreement: US$0.2722 for twenty clauses is a projection, not measured agreement cost. The interface records actual document-review cost; offline demonstrations use zero credits. Setup requires packages and reference download, not training. No staff-time savings or commercial return were measured.

### Responsible use and course coverage

The main silent failure is a plausible explanation attached to a real but non-supporting quote. Exact citations, bounded comparisons, adversarial regressions and separate substantive auditing address it, but have not solved it. Abstention reduces some unsafe conclusions while worsening missed-risk recall. I therefore keep paid mode disabled by default and do not deploy for real signing decisions.

Personal-data detectors, synthetic-only confirmation, local serving and no saved uploads reduce exposure; detection remains incomplete. API transmission needs explicit opt-in. Before-call cost reservations, provider price ceilings and stops on unknown usage limit spending without pretending to guarantee account billing. There are no automatic retries or autonomous actions.

The project covers AI selection and ownership, RAG, structured prompting, bounded orchestration without autonomous agents, cost evaluation, and responsible use. Tests, GitHub setup instructions and an offline recorded demonstration support reproducibility. Better substantive evidence checks and a fresh independently labelled dataset are needed before any reliability claim. AI assisted code, tests, writing and synthetic narration; I remain responsible for reviewing the submitted work and its claims.

### Evidence

Repository: https://github.com/yoga-aaa/Singapore-rental-contract-review/tree/codex/project-foundation

CEA tenancy templates v1.4 are registered in data/source_registry.csv. Hashes, denominators and audit limitations are in docs/external_evaluation_v16.md and docs/regression_evaluation_v17.md. The private evidence archive contains frozen cases, labels, responses and scoring instructions, without credentials; copyrighted source PDFs are restored by verified official downloads, not redistributed.
