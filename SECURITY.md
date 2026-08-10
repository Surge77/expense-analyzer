# Security policy

## The most important thing

**Never commit a real bank statement.** It carries your account number,
running balance and complete transaction history. Once pushed to a public
repository it is in git history permanently — deleting the file in a later
commit does not remove it, and forks and clones keep their own copy.

`data/` is gitignored except the generated sample. Keep it that way.

If you have already pushed one:

1. Treat the account as exposed and tell your bank.
2. Rewrite history with [git-filter-repo](https://github.com/newren/git-filter-repo)
   and force-push.
3. Delete every fork, and ask GitHub Support to purge cached views.

## Credentials

This project needs none. The two public datasets download without any Kaggle
account.

If you do have Kaggle credentials on your machine, note that an **expired
token is worse than no token**: the request is rejected where sending nothing
would have succeeded. `expense_analyzer.data.loaders` detects this and names
the file to delete.

Never commit `~/.kaggle/access_token`, `kaggle.json`, or any `.env` file.
`.gitignore` covers all three.

## Reporting a vulnerability

Open a [security advisory](https://github.com/Surge77/expense-analyzer/security/advisories/new)
rather than a public issue. Please include reproduction steps and the version
or commit affected. Expect an initial response within seven days.

## Scope

This is a local analysis tool. It has no server, no authentication and no
network listener. It makes exactly one outbound connection — downloading a
public dataset from Kaggle — and only when you ask for a remote source.

The realistic risks are therefore:

- Accidentally committing personal financial data (covered above).
- A malicious CSV. Files are parsed with pandas as text and never evaluated,
  but pandas is not a security boundary; do not run this on untrusted input.
- Dependency vulnerabilities. Report these upstream, and open an issue here
  so the pin can be moved.
