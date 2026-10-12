# TollDirect — Architecture and partnership feasibility

Simulation only. Pending official partner integration. No live payments.

## Corrected architecture

TollDirect is a proposed **direct toll-payment allocation and settlement system**. It is not a driver reimbursement application.

Authorized path:

**Passenger → Authorized TollDirect payment routing → Driver’s registered E-ZPass account**

Rules:

- The driver is never an intermediary for the toll payment.
- The driver’s bank account is excluded from the toll-payment flow.
- The rider pays the trip fare once. The eligible toll is a portion of that fare, not a second charge.
- The same toll must not be both credited to E-ZPass and paid to the driver.
- Failures, delayed toll posts, and refunds are reconciled. There is no personal-bank fallback.

## What exists today

Uber and Lyft currently use a reimbursement model. The driver pays the toll agency, usually from a prepaid E-ZPass balance. The platform adds the toll to the rider fare and later credits the driver.<grok type="render_inline_citation" citation_id="79" />

Lyft states that it does not pay toll collectors and that drivers are responsible for paying toll agencies directly.<grok type="render_inline_citation" citation_id="75" />

Uber’s driver help says the toll is added to the rider’s price and paid to the driver, at the electronic rate in most places.<grok type="render_inline_citation" citation_id="79" />

That is the opposite of TollDirect’s proposed path.

## E-ZPass technical feasibility

No public E-ZPass API was found that lets a third party credit a specific driver account in real time.

Published funding methods are account-holder methods: credit or debit card, ACH from a bank, cash or check at a service center, and retail reload cards. Virginia E-ZPass describes automatic replenishment as usually within a 24-hour period after a low balance.<grok type="render_inline_citation" citation_id="68" />

E-ZPass is a group of agencies, not one national API. Commercial and fleet accounts exist, but they are still the account holder’s prepaid or postpaid relationship. New York Thruway’s Toll Management Service Provider commercial program was cancelled effective 27 August 2026.<grok type="render_inline_citation" citation_id="86" />

**Conclusion:** direct account funding is not available from existing public systems. It would require a new agency agreement, and real-time credit is unconfirmed. Settlement delay should be assumed until an agency states otherwise.

## Required partners and agreements

1. **Rideshare platform (Uber, Lyft, or another).** Change the toll portion from a driver reimbursement to an allocated payment with a registered E-ZPass account as the payee. Provide trip, vehicle, toll-event, and confirmation data. Block a second rider charge and a duplicate driver payout.
2. **Each E-ZPass / toll authority in the operating area.** Accept a third-party credit to a named account or transponder, confirm posting, handle delayed tolls and refunds, and define timing. One state agreement does not cover the network.
3. **Licensed payment provider.** Move the allocated toll portion under applicable money-transmission and payment rules. TollDirect must not informally hold rider funds.

## Controls before any production use

- Trip-to-account association
- Eligible-amount rules
- Duplicate-charge and duplicate-reimbursement prevention
- Reconciliation of gantry event, fare toll portion, routing, and E-ZPass confirmation
- Failure, delay, and refund handling with no bank fallback
- Official approvals completed

Until those exist, the prototype stays in simulation mode.
