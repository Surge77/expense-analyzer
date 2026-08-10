# 0003 — Datasets are downloaded, not committed

**Status:** accepted

## Context

The project depends on two public Kaggle datasets. Committing them would make
the repository self-contained and remove a network dependency from CI.

## Decision

Download on demand into kagglehub's cache, outside the project. Commit only
the locally generated sample.

## Why

**Licence.** Both datasets carry their own terms. Redistributing someone
else's data inside an MIT-licensed repository muddies what the MIT licence
actually covers.

**Size and permanence.** The bank dataset is 6 MB of Excel. Committing it puts
it in git history forever, including for everyone who ever clones.

**The habit matters more than these two files.** This repository processes
bank statements. "Data does not go in the repository" needs to be
unconditional, because the one time it gets relaxed is the time somebody
commits their own statement.

**No credentials are needed.** Verified by downloading both with `HOME`
redirected and `KAGGLE_API_TOKEN` blanked, so the barrier is genuinely zero.

## Cost

`pytest -m integration` needs a network connection, and CI has a job that can
fail for reasons unrelated to the code. Mitigated by keeping the default
`pytest` run entirely offline: the sample is generated locally, so a fresh
clone works with no network at all.

One surprise worth recording: a *stale* Kaggle token breaks these downloads.
An expired credential is rejected where sending nothing succeeds, so having
authenticated once and then rotating leaves the machine worse off than never
authenticating. `loaders.py` detects this and names the file to delete,
because the raw failure is an opaque HTTP 400.
