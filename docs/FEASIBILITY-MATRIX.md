# Feasibility matrix

Real-time E-ZPass credit is not listed as an existing capability.

| Capability | Implemented technology | Simulated behavior | Unverified provider capability | Required authorization |
| --- | --- | --- | --- | --- |
| Match one active trip to one vehicle crossing | Yes | Synthetic trips and crossings | Uber/Lyft active-trip feed | TNC data agreement |
| Use only a recorded toll amount | Yes | Official amount supplied by synthetic post | MassDOT posted-amount feed | Toll-authority data agreement |
| Charge the passenger method already on the trip | Adapter contract only | Synthetic charge identifier | TNC or processor toll-portion charge | TNC and payment-provider agreement |
| Credit the vehicle E-ZPass account | Adapter contract only | Synthetic credit identifier | External credit without debiting the driver | MassDOT / E-ZPass agreement |
| Keep authorization separate from E-ZPass balance | Yes | Balance stays 0 until confirmed credit | Real posting behavior | E-ZPass confirmation interface |
| Credit before assessment | Not available | Timing model only | Pre-assessment credit or penalty waiver | Written MassDOT ruling |
| Credit after official post | Exposure detection only | 2-day gap shown | Whether penalties apply during the gap | Written MassDOT ruling |
| Block a duplicate crossing | Yes | Second event blocked | Provider idempotency keys | Provider agreement |
| Leave a failed charge unresolved | Yes | No driver fallback | Real failure and retry semantics | Provider agreement |
| Refund and commercial-rate delta | Yes | Synthetic reversal and delta | Official adjustment notice | MassDOT and processor agreement |
| Durable audit ledger | Yes | Local SQLite | Provider reconciliation files | Operational agreement |
| Real-time external E-ZPass credit | No | Not assumed | Not verified | Not requested as a current fact |

## Current external fact

EZDriveMA customer service, 12 October 2026: funds must be on the account at the time of travel. The account holder remains responsible for a positive balance. See `EZDRIVEMA-REPLY.md`.
