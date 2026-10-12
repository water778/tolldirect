# TollDirect — Massachusetts E-ZPass direct-payment feasibility

Simulation only. This is an operational feasibility note, not a live payment design. No money moves and no partner is contacted until the owner approves the inquiry.

## Bottom line

A third party cannot currently fund a driver’s E-ZPass MA account through any published interface. Massachusetts already has a rideshare-specific toll process, and it does the opposite of TollDirect: MassDOT adjusts the driver’s E-ZPass account to the commercial rate. The driver must still keep that account funded.

Direct allocation is not operational today. It would require a new written arrangement with MassDOT, a change to the TNC settlement process, and a licensed payment path. Real-time credit should not be assumed.

## 1. Can an authorized third party directly fund a driver’s E-ZPass MA account?

Not under any published pathway.

Official funding methods are account-holder methods: credit or debit card, checking account, check, or cash or card at a customer service center. Commercial prepaid accounts start at $50 per transponder. Mass.gov states that the account holder assigns a card or checking account, and that manual replenishment is the account holder’s responsibility.

Source: https://www.mass.gov/info-details/apply-for-e-zpass-ma

EZDriveMA terms put the duty on the account holder. Automatic replenishment requires the holder to provide a valid card or bank account with sufficient funds. Manual replenishment requires the holder to keep a positive balance. A zero or negative balance can produce a Pay By Plate invoice at a higher rate.

The same terms say the account holder shall not assign the obligations or benefits of the agreement without the express written consent of MassDOT or the EZDriveMA Customer Service Center. That is the relevant gate for any third-party funding arrangement.

Source: https://www.ezdrivema.com/documentation/TermsConditions.pdf

EZDriveMA also warns that third-party bill-pay services are not affiliated with the program. That is not a ban on a future official arrangement, but it shows that unofficial payment apps are outside the program.

Source: https://www.ezdrivema.com/

## 2. Commercial, fleet, institutional, or third-party arrangements

Published account types on EZDriveMA are:

- Private Individual — prepaid, up to 4 transponders
- Commercial Business — prepaid, for 3 or more axles, livery, taxi, combination, and other commercial plates; unlimited vehicles
- Commercial Surety — postpaid, same vehicle classes, with a MassDOT surety bond of six months of toll usage plus transponder cost, or $5,000, whichever is greater

Source: https://www.ezdrivema.com/accountcreationselection

These are still the account holder’s accounts. No institutional or third-party payee product is listed. Commercial accounts are opened by calling 1-877-627-7745, not through the private online flow.

The closest official third-party pattern is rental and lease reassignment under 700 CMR 7.04, which moves unpaid Pay By Plate responsibility to a lessee. That is liability transfer, not a credit into a driver’s prepaid E-ZPass account.

## 3. Private API or approved integration pathway

None found for account funding.

TransCore operates the MassDOT E-ZPass back office under a multi-year customer-service and financial-accounting contract and processes transactions to customer accounts. Its public project description mentions retail reconciliation, not a partner API for crediting a named driver account.

Source: https://transcore.com/projects/massdot

The only related official data path found is the TNC data exchange used for the commercial-rate upcharge, described below. That is a rate-adjustment feed, not a payment interface.

## 4. Who handles a partnership proposal

First official contact:

- EZDriveMA Customer Service Center, Commercial Department
- 27 Midstate Drive, Auburn, MA 01501
- customer.service@ezdrivema.com
- 1-877-627-7745; historical commercial option is 7
- Fax (508) 786-5222

Source: https://www.mass.gov/ezdrivema

The inquiry should ask to be routed to the MassDOT official responsible for EZDriveMA commercial accounts and the Transportation Network Company toll procedure. TransCore is the operator, not the approval authority. No named partnership officer was verified.

## 5. Can a passenger toll payment reach E-ZPass without the driver’s bank?

Not with the current official process.

Under Chapter 187 of the Acts of 2016, adding M.G.L. c. 159A½, TNC drivers pay the commercial toll rate on MassDOT roads while providing transportation network services. TNCs must have a process so those tolls are paid to MassDOT at the commercial rate. EZDriveMA’s rideshare page says TNCs send driver and ride data to MassDOT, which cross-references toll data and upcharges the driver’s account. The upcharge can take up to two weeks. Drivers are told to keep the account funded, preferably with a credit card.

Source: https://www.ezdrivema.com/rideshare

So the passenger fare can reimburse the driver through Uber or Lyft, but the toll itself is still drawn from the driver’s E-ZPass balance. The driver’s bank or card is the replenishment source unless a new written arrangement replaces it.

## 6. Prepaid balance and timing without the driver advancing money

Current timing works against a no-advance model:

- Tolls post after trip building. A MassDOT administrative-law report described a two-to-five-day image-review and trip-building period before posting.
- The rideshare commercial upcharge can take up to two weeks.
- A zero balance can generate a Pay By Plate invoice before any later credit arrives.

A workable pilot would therefore need either a MassDOT-approved prefunded commercial pool that credits the driver account before or with the toll post, or written acceptance of delayed credit with protection from Pay By Plate treatment. Neither exists today. Drivers would still advance money under the published rules.

## 7. Must Uber or Lyft change settlement?

Yes. Both currently reimburse the driver after the driver has paid the toll agency. Lyft states that it does not pay toll collectors. Uber adds the toll to the rider price and pays it to the driver.

Massachusetts already requires TNCs to support commercial-rate collection, but the implemented method is data sharing plus an upcharge on the driver account. Supporting TollDirect would require a new TNC process: identify the eligible toll portion of the single rider fare, release it to an authorized payee for the driver’s E-ZPass MA account, and suppress the driver reimbursement for that same toll. Without that change, the driver could be paid twice or the rider could be charged twice.

## Obstacles

- No public funding API
- Account-holder replenishment duty and no-assignment clause
- Existing TNC process charges the driver account
- Posting and upcharge delays
- An MA agreement would not cover out-of-state E-ZPass tolls
- Money-movement rules still require a licensed payment provider
- Commercial surety is a bond-backed postpaid account for the business, not a passenger-allocation product

## Realistic pilot

1. Send the draft inquiry only after owner approval. Ask whether MassDOT will even consider a written third-party credit path.
2. If the answer is no, stop. The architecture is not operational in Massachusetts.
3. If the answer is conditional, limit a paper pilot to E-ZPass MA accounts, Massachusetts facilities, and one TNC. Define trip-to-account matching, eligible amount, commercial-upcharge treatment, duplicate-payout block, failure handling, and timing.
4. Do not move money until MassDOT, the TNC, and a licensed payment provider have written approvals.

All TollDirect payment screens remain simulated.
