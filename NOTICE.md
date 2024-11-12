# Third-party components

Keel's application code is distributed under the repository's MIT license. Installed libraries, tool binaries and container images retain their own licenses and notices; they are fetched as dependencies rather than copied into the application source.

The exact Python and JavaScript dependencies are listed in `requirements.lock` and `web/package-lock.json`. Their installed distributions include license metadata. The infrastructure uses PostgreSQL, Redis7.0.11, Keycloak18.0.2, OPA0.60.0, Python and Node; preserve their original notices when redistributing images or binaries. Build-time GitHub Actions and the optional Playwright browser distribution also retain their upstream terms.

See [PROVENANCE.md](PROVENANCE.md) for pinned versions, source links and release evidence. Container images and runtime credentials are not included in the Git repository.
