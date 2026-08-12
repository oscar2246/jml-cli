# IAM Provisioning CLI

A Python command line tool that provisions and manages user accounts in a live Active Directory domain. This is not a simulation against a text file; every option in the menu opens an LDAPS connection to a real domain controller running in my home lab and writes to it.

The tool covers the identity lifecycle a helpdesk or IAM team actually runs: a joiner gets an account, a mover gets re-enabled, a leaver gets disabled, and all of it lands in an audit trail.

## What it does

- Creates a real AD user object with a collision-safe LANID and email, both checked against the live directory before anything is written
- Sets an initial password over LDAPS and forces a change at next logon
- Enables and disables accounts by flipping a single bit in `userAccountControl`
- Searches the directory by `sAMAccountName`
- Writes a timestamped, append-only audit line for every create, enable and disable

## The joiner, in four steps

Creating an account is not one operation; it is four, and the order matters.

1. **Create the object disabled.** The account is added with `userAccountControl: 514`, which is a normal account with the disable bit set. An account cannot be created enabled without a password already on it, and a password cannot be set until the object exists.
2. **Set the password.** AD accepts `unicodePwd` only as a UTF-16-LE encoded string wrapped in literal double quotes, and only over an encrypted channel. This is the step that made LDAPS a hard requirement rather than a nice-to-have.
3. **Force a change at next logon.** Writing `0` to `pwdLastSet` marks the password expired immediately. The temporary password is printed once to the operator and never written to the log.
4. **Stop.** The account is left disabled on purpose. See below.

Every step is gated; if any one of them fails, the tool reports which step failed and returns before writing a local record.

## Architecture

| File | Responsibility |
|---|---|
| `main.py` | Menu and entry point. Talks to the operator, nothing else. |
| `user_ops.py` | Lifecycle operations and the `user_creation` class. Orchestrates the steps. |
| `AD_operations.py` | Every LDAP call. The only module that knows the directory exists. |
| `password_gen.py` | Password construction. Talks to nothing. |
| `storage.py` | JSON persistence and the audit log. |
| `secrets_local.py` | Host, bind account, credential, search base, mail domain. Not committed. |

Each module is defined by what it talks to. That is the rule that decided where password generation went; it talks to no operator, no directory and no filesystem, so it earned its own file.

## Design decisions

**Accounts are created disabled, and enabling is a separate step.** Requiring a second action limits the risk of an account sitting unused before anyone actually needs it. A brand new account also has no legitimate owner yet; if someone gets hold of it, there is no real user around to notice the activity is wrong, which makes a dormant account a quiet route to privilege escalation. The second step is also a second person, which is separation of duties; the account that provisions is not the account that approves.

**The service account was delegated four rights, not full control.** The ADUC delegation wizard offers "Create, delete, and manage user accounts," which hands over full control of every user object in the OU. Instead the grant was written explicitly with `dsacls`: create and delete child user objects, write `userAccountControl`, reset password, and write `pwdLastSet`. Nothing else. Read access was never granted at all, because the OU already allows authenticated users to read it. The tool can do exactly as much as it did before; what shrank is the damage if that credential is ever stolen.

Worth being honest about what that damage still is. The rights are scoped to one OU, so nothing outside it can be written. But create plus write on `userAccountControl` is enough to build a working account and switch it on, and any authenticated domain account can read most of the directory. Reset password in that OU also means any account already sitting in it can be taken over. Scoping the write does not scope what the resulting credential can read.

An ACE is also scoped to an object class, which cost me a working afternoon to learn. A delegation that reads correctly in the GUI can still be attached to the wrong class; mine was granted on group objects while I was testing user creation, so enable and disable worked while create returned `insufficientAccessRights`. "I delegated it" is never the whole question. Which class is.

**The disable bit is flipped, not overwritten.** A live account in my lab came back with `userAccountControl` of 66050, which decodes to 65536 (password never expires) plus 512 (normal account) plus 2 (disabled). Writing a flat 514 to disable that account would have quietly stripped the password-never-expires flag off it.

The part that makes this worth caring about is that nothing would have reported it. The modify returns success, the account is disabled exactly as asked, and the tool has no idea it destroyed a setting on the way through. It surfaces months later when an account nobody touched suddenly demands a password change and something breaks at an inconvenient hour. A crash tells you where to look; silent corruption does not. So the tool reads the current value and changes one bit, `uac | 2` to disable and `uac & ~2` to enable, and everything else on the object survives.

**Passwords satisfy the complexity policy by construction.** The generator builds each character class separately, then shuffles. The obvious alternative is to generate a random string and test it against the rules in a loop, but that test is a second copy of the domain password policy, and the two copies have to agree forever. Raise complexity on the domain next year and the checker keeps approving passwords AD now rejects; the failures are intermittent and no test catches them. `secrets.token_urlsafe` looks perfectly reasonable and misses AD complexity roughly one time in twenty-five for exactly this reason.

Construction assumes a policy too, and I would rather say that than have someone point it out. Three upper, three lower, four digits and two symbols is a bet on what the domain wants. The difference is that the bet lives in one place, it is readable, and it fails visibly instead of drifting out of sync. The symbol set is trimmed on purpose as well; the credential travels through a distinguished name, a shell and a helpdesk copy-paste, so quotes, backslashes and commas were left out.

**The directory is written first, the local record second.** The JSON file and the audit log are only updated once AD confirms the change. Reversed, the log would record work that never happened, and an audit trail that lies is worse than no audit trail at all.

## Security notes

- The bind runs over LDAPS. Plain LDAP sends the service account password across the wire in cleartext, and the password step will not work without encryption anyway.
- All user input reaching an LDAP filter is escaped with `escape_filter_chars`. LDAP injection is the same class of problem as SQL injection and gets the same treatment.
- Host, bind account, credential, search base and mail domain live in `secrets_local.py`, which is gitignored. Hardcoding them was the first thing fixed once this became a portfolio repo.

## Running it

Requires Python 3 and `ldap3`, plus a `secrets_local.py` in the project root:

```python
DC_host_ip = "10.0.0.143"
SVC_Account_AD = "svc_account@idm.internal"
SVC_PW = "..."
SEARCH_BASE = "OU=TestUsers,OU=IDM_Lab,DC=idm,DC=internal"
domain = "idm.internal"
```

The service account needs the four delegated rights listed above on the target OU, and the domain controller needs a certificate on port 636.

```
python main.py
```

## Known limitations

These are open and I know why each one is still here.

- **Two sources of truth.** Collision checks query AD, but list, enable and disable read the local JSON file. Delete a user in ADUC and the CLI still believes it exists. AD should become the single source of truth and the JSON file should become a cache.
- **Partial provisioning.** If the object is created and the password step fails, the tool returns before saving a record, which leaves an AD object the CLI has no memory of. The two standard answers are a compensating delete or a reconciliation job that finds orphans; neither is built yet.
- **The DN is not escaped.** Distinguished names have their own escaping rules, separate from filter escaping. The risk is low because LANIDs are generated uppercase letters and digits, but generated input is still input.
- **The client does not validate the DC certificate.** The channel is encrypted but not authenticated. Importing the CA root and connecting by FQDN would close it.
- **The audit log records only successes, and never who did it.** A failed provisioning attempt leaves no trace, which is backwards; repeated failures to create accounts are exactly the pattern a security team wants to see. The log also records what happened and to whom, but never by whom, because the CLI has no operator identity yet. The fix is to log the attempt and the outcome as separate events, both carrying the operator who initiated them.

## Next

Scheduled activation is the one I want most: a future-dated start where the account is provisioned now and enabled automatically on the hire date. That is a real IGA feature and it fits the separation-of-duties model already here, since a schedule approves the enable in advance instead of a person doing it by hand.

After that, attribute modification for movers, and reconciliation against the directory.

An identity is easy to create. The hard part is proving who created it, when, and with what authority; that is what the rest of this repo is for.
