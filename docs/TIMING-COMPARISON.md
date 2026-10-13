# Timing comparison

Both scenarios start with a $3.50 toll and an E-ZPass balance of zero.  
Real-time external E-ZPass credit is not verified and is not assumed.

## Proposed credit before assessment

| Stage | E-ZPass balance |
| --- | ---: |
| Authorized | 0 |
| Captured | 0 |
| Settled | 0 |
| Confirmed simulated credit | 350 |

- The credit is not allowed to precede capture.
- In the demonstration timing, capture completes about two minutes before the gantry, so the proposed credit would cover the toll.
- This is a **required future capability**, not an existing E-ZPass feature.
- Exposure in this modeled timing: no.
- Driver funding used: no.

## Credit after the official post

| Event | Time in the model |
| --- | --- |
| Crossing | 12 October 2026, 17:56 UTC |
| Official post | 15 October 2026, 17:56 UTC |
| Confirmed simulated credit | 17 October 2026, 17:56 UTC |

- The account is still at zero when the toll can be assessed.
- Exposure: yes. Gap: 2 days after the official post.
- No grace period is assumed. EZDriveMA has stated that funds must be on the account at the time of travel.
- Driver funding used to close the gap: no.
- The transaction remains unresolved until a confirmed credit exists. It is not silently paid by the driver.

## What a partner would have to provide

To remove the exposure without driver funding, one of these would be required in writing:

- a credit to the vehicle E-ZPass account that is effective before assessment, or
- a written waiver of Pay By Plate and penalties for that passenger toll while the credit is pending.

Neither has been verified.
