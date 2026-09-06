# MCP Trust Index — Scoring Rubric (v0.1)

**What this index measures:** *verifiability* and *supply-chain stability* of MCP servers.
**What it does NOT measure:** whether a server is exploitable, malicious, or insecure at runtime.

We perform **no** runtime testing, **no** exploitation, and **no** connection to third-party
systems. Every input is public metadata. A low grade means *"an outside party cannot check
what this server actually does"* — it is not an accusation.

## Inputs (all public, all permission-free)

| Source | Endpoint | Used for |
|---|---|---|
| Official MCP Registry | `registry.modelcontextprotocol.io/v0/servers` | canonical server list, declared version, description, endpoints, packages |
| npm registry | `registry.npmjs.org/<pkg>` | real published version, version history, description history |
| PyPI | `pypi.org/pypi/<pkg>/json` | same, for Python distributions |
| GitHub (public) | `api.github.com/repos/<owner>/<repo>` | repo exists? archived? license? last push? |

## Scoring

Each server starts at **100**. Deductions below are subtracted once each.

| Signal | Penalty | Why it matters |
|---|---|---|
| No repository **and** no package declared | −40 | Nobody outside the publisher can inspect the code |
| Declared repository returns HTTP 404 | −35 | Link is dead: repo deleted, renamed, or made private |
| Repository archived | −15 | No longer maintained |
| Not pushed to in > 365 days | −8 | Likely unmaintained |
| No open-source licence | −5 | Unclear reuse/audit rights |
| Repository is a fork | −3 | Provenance is indirect |
| Registry version ≠ version published on npm/PyPI | −10 | Registry metadata is out of sync with what users install |
| Registry description ≠ package description | −8 | The two public descriptions disagree |
| Package description changed between last two releases | −20 | Classic rug-pull shape: same version family, new behaviour |
| Remote endpoint over plain HTTP | −25 | Traffic not transport-encrypted |
| No endpoint and no package (metadata-only entry) | −10 | Nothing to install, nothing to verify |

## Grades

`A ≥ 90` · `B ≥ 75` · `C ≥ 60` · `D ≥ 40` · `E ≥ 20` · `F < 20`

The `verifiable` column is independent of the score: true when the server publishes a package,
or declares a repository that actually resolves.

## Limits you should hold us to

- **Point-in-time.** Scores describe the moment of the scan.
- **Coverage.** Only servers listed in the official registry are covered. Anything distributed
  only via GitHub, Docker Hub, or a blog post is out of scope for v0.1.
- **False negatives.** A dead repo link may be a rename we failed to follow. A "no source"
  server may publish source elsewhere.
- **Not a security verdict.** Nothing here says a server is safe or unsafe to run.

## Maintainer path

Publish the source (add `repository` to your registry entry, or ship a package),
fix the version, and open an issue — we re-scan and the score updates on the next run.
Disputes are resolved by showing the public metadata, not by argument.
