# Architecture and competition rules

## Core models

- `divisions` (four seeded groups) → `teams` (each has a division) → `players` (one registered team, one registered division, optional unique Member ID).
- `competitions` (singles/doubles/threes/teams, optional division, draft → drawn → published → completed).
- `entries` (an individual, pair, trio or registered team). `entry_players` holds partnership members and snapshots of names, teams and divisions at time of entry.
- `matches` (round number, position, entry A/B, frame scores, winner, bye). `audit_log` records committee actions.

## Bracket constraints

- The random draw uses a secure PRNG and a power-of-two bracket, with a first-round bye allocated to the necessary number of competitors.
- First-round byes automatically advance their entrant. Normal match results have a strictly unequal frame score from 0 to 99.
- Players cannot enter a given competition twice. A registered team cannot be entered twice in a Teams competition.
- Singles with a chosen competition division can include only players in that division.
- Doubles and Threes default to same-division enforcement, and when a divisional event is selected the partners must match it. Different registered pub teams are permitted. Turn enforcement off before the draw to allow exceptions.
- Teams with a selected competition division must be registered in that division.
- Once drawn, entries and rules are locked, but a draft draw may be regenerated. Once published, a draw cannot be regenerated.
- Corrections that would invalidate a later scored result are blocked rather than silently altering it.

## Security and deployment notes

- Browser login is cookie-based, HttpOnly and SameSite strict. State-changing admin requests must present the CSRF token issued during login.
- The very first administrator is created using environment variables. Subsequent administrator accounts can be created by the owner through the committee UI.
- Public endpoints expose competition names and entrant names only when a draw is published. Imported member IDs are not exposed publicly.
- Do not expose directly to the internet without secure hosting/HTTPS, rate limiting and a tested backup strategy.
