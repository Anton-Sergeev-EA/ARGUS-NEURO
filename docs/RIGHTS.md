# Rights to the project, and what to do about the license (30 Oct 2026)

This is a practical guide, not legal advice. Before registering anything or changing the license, check it with a Russian patent attorney or an IP lawyer.

## Where things stand

- The code is published under the **MIT License** (`LICENSE`, copyright holder Sergeev Anton Valentinovich) since 28 Aug 2026.
- Authorship arises automatically when the code is created (Civil Code of the Russian Federation, part IV). The history of 108 commits in this repository is the first piece of evidence.
- MIT lets anyone use, copy, fork, sell or embed the code, provided the copyright line is kept. It gives **no exclusivity**. Copies already published stay under MIT for good: a license cannot be withdrawn from them.
- The name "ARGUS-NEURO" is not a registered trademark.

## What was added in the repository

- `CITATION.cff`: a machine-readable way to cite the project and its author.
- `NOTICE`: states that MIT covers the code and not the name, and that third-party data and dependencies keep their own terms.
- This document.

## What you must do yourself (a repository cannot do it)

1. **Make a dated, signed release.** Create a Git tag and a GitHub release, then connect the repository to Zenodo to obtain a DOI. This fixes a public date and the author.
2. **Register the program** (Rospatent, "программа для ЭВМ"). The certificate is the strongest proof of authorship. Check the current fee and the form on the Rospatent site.
3. **Deposit the code** (notary, or a certified hash) if you want a second dated proof.
4. **Check and file the trademark "ARGUS-NEURO"** (Civil Code art. 1477). First search for conflicts in the relevant classes: "Argus" is a common name. Until it is registered, do not use the ® sign.
5. **Confirm the two commits signed `Anton Sergeev <kavery@mail.ru>`** (only README.en.md, 5 Oct 2026). If that account is yours, nothing more is needed; if it belongs to someone else, get their written consent.
6. **Check who owns the work** if any of it was done on an employer's time or equipment, or under a grant: those agreements can give the organization rights.
7. **Ask the lawyer about code written with an AI assistant.** Russian law treats the author as a person whose creative work produced the code. How that applies to AI-assisted code is not settled here.
8. **Check data licenses.** The NASA catalogue states no dataset license (`docs/PUBLIC_BATTERY_DATA.md`); the terms for CALB and HUST are not recorded in the repository. The repository does not include these datasets; keep it that way until the terms are confirmed.
9. **Run a dependency license audit** (for example with `pip-licenses`) before choosing a stricter license. It was not run in this session.

## The license decision

You are the only copyright holder, so you may release **new** versions under another license. Old versions stay MIT. Three options:

| Option | What it gives | Cost |
|---|---|---|
| Stay on MIT | Widest adoption and trust | Anyone may build a closed paid product on your code; weak position with investors |
| **AGPL-3.0 and a commercial license** (dual licensing) | Open code; anyone who embeds it in a closed product or hosted service must open their code or buy a license from you | Some companies avoid AGPL; you need a CLA from every outside contributor |
| Source-available license (such as BSL) | Strongest protection against commercial copying | Not open source in the strict sense; less community goodwill |

**Recommendation:** keep MIT for what is already published, and move new versions of the core (`cpp_core`, the models and the API) to **AGPL-3.0 with a commercial license** once the lawyer confirms that the dependencies and data allow it. Keep the dashboard and the examples permissive if you want easy adoption.

Steps to switch, in this order:

1. The lawyer confirms the plan and drafts the commercial license text.
2. Add a `CLA.md` and require it for pull requests (before the first outside contribution).
3. Add `LICENSE-AGPL` and a clear statement of which version is under which license; keep the MIT text for the old tags.
4. Update the license line in all 9 READMEs, `NOTICE`, `CITATION.cff` and the package metadata, then tag a release.

This change was **not made** here: it needs your decision and the lawyer's check.

## What makes a project's author widely known

Law does not give this, publication does: a regular release history, a short paper or preprint with the backtest results, talks at conferences and meetups, a named maintainer, and a registered name. Linux is known through its trademark and its maintainer's role, not because the license reserves anything.
