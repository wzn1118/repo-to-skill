# Security policy

This project is experimental and has no supported stable release or response-time guarantee.
The [threat model](docs/threat-model.md) documents the current boundaries and known limitations.

Do not include credentials, private source code or a weaponized exploit in a public issue.
For a vulnerability, use GitHub private vulnerability reporting if it is available for this repository;
otherwise request a private reporting channel from the maintainer without publishing exploit details.

A useful report identifies the affected revision, a minimal benign reproduction, the trust boundary
crossed and expected behavior. Avoid testing against other users, third-party services or hosted systems
without permission. Local Docker execution is not advertised as a multi-tenant security boundary.
