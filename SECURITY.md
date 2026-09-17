# Security Policy

## Supported versions

Only the current `main` branch and the live site at
https://akashic.cryptideffects.com receive fixes. There are no
long-term support branches.

## What counts

The site is static: HTML, JSON and a small amount of JavaScript served from a CDN, with no
accounts, no server-side code and no telemetry. The scraper runs on the maintainer's
machine. The interesting surface is therefore small:

- Anything that lets a page served by the site run script it should not (for example
  through a vendor's product text that reaches the page unescaped).
- Anything in the scraper that could be made to write outside its data directory or run
  commands from fetched content.
- Dependency advisories in `app/package-lock.json` or `scraper/pyproject.toml`.

Out of scope: the vendors' own sites, and rate limits or blocking they apply to the
scraper, which is polite by design.

## Reporting

Please use GitHub's private vulnerability reporting rather than a public issue:
https://github.com/drlholloway/akashic/security/advisories/new

You will get an acknowledgement within a week. Credit is given in the changelog unless
you ask otherwise.
