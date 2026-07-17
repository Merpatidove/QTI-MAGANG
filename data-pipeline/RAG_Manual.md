# HITE Retrieval Knowledge Base — RAG Manual
### Document No. KB-HITE-001 · Version 1.1 · Internal — Confidential

---

## 1. Purpose of This Manual

This manual is the canonical documentation corpus ingested into HITE's localized vector database (see **SOP-02 — Secure Context Retrieval**). Every entry answers one of the ticket categories used in the prototype defense dataset: Laravel/database connection failures, Docker container crashes, Git version-control conflicts, and Kubernetes/GitOps orchestration failures.

Not every ticket in the defense dataset is meant to reach this manual at all — Section 5 explains which ticket types are handled without a retrieval lookup.

Each entry is written to satisfy two audiences at once:

- **The LLM** reads the `Context` and `Diagnosis` sections as natural-language grounding material — the prose HITE cites when it explains *why* a ticket is failing and *how* the fix resolves it (SOP-03 Fact Verification).
- **The grading/evaluation script** reads a fixed set of explicit fields — present in the same position in every entry — so it can extract structured data without guessing at prose. This satisfies the 40/40/20 defense rubric without needing a second, separate answer key: retrieval accuracy, remediation correctness, and escalation/confidence judgment can all be scored straight from this one document.

## 2. Document Schema (Field Reference)

Every SOP entry in this manual follows the same fixed structure, in this exact order:

| Element | Format | Parseable by |
|---|---|---|
| Title | `# SOP-<CATEGORY>-<NUMBER>: <Title>` | Regex on `^# SOP-` marks the start of a new entry |
| Metadata block | Plain `Key: Value` lines directly under the title, before any `##` | Regex `^(\w+): (.*)$` per line |
| `## Context` | First line is always `Error Signature: <text>`; remaining lines are prose | Line 1 via regex `Error Signature: (.*)`; rest passed to the LLM as-is |
| `## Diagnosis` | Prose root-cause explanation | Passed to the LLM as grounding text |
| `## Remediation` | Exactly one fenced ` ```bash ` block, optionally followed by a `Verification:` line | Code-fence content extracted verbatim as the ground-truth fix |

Metadata keys used throughout this manual:

- **SOP_ID** — unique identifier, referenced by the ticket-to-SOP answer key.
- **Category** — one of `Database`, `Docker`, `Git`, `Kubernetes`.
- **Confidence_Tier** — the tier HITE should assign per **SOP-05** if it retrieves this document with high similarity: `A` (safe to auto-deliver), `B` (deliver with "Review Recommended"), or `C` (requires human judgment before any fix is proposed).
- **Tags** — comma-separated keywords matching the `project_tags` convention used in ticket intake (SOP-01).

## 3. Confidence Tier Legend

| Tier | Meaning | Typical entries in this manual |
|---|---|---|
| A | Deterministic, low-risk, single-command fix | Timeouts, OOM limits, lockfile regeneration, standard merge conflicts |
| B | Correct fix is well-documented but requires judgment about production impact before applying | Killing a blocking transaction, changing healthcheck timing, resolving submodule state |
| C | No safe default exists; escalate with context only | Not used in this manual — no ticket category here is inherently unsafe to document |

## 4. SOP Index

| SOP_ID | Title | Category | Tier |
|---|---|---|---|
| SOP-DB-001 | MySQL Connection Timeout (SQLSTATE 2002) | Database | A |
| SOP-DB-002 | MySQL Too Many Connections (SQLSTATE 1040) | Database | A |
| SOP-DB-003 | Migration Lock Wait Timeout (Error 1205) | Database | B |
| SOP-DB-004 | Redis/Horizon Queue Connection Refused | Database | A |
| SOP-DB-005 | Read Replica Lag Causing Stale Reads | Database | B |
| SOP-DOC-001 | Container OOMKilled (Exit Code 137) | Docker | A |
| SOP-DOC-002 | Healthcheck Failing — Port Already in Use | Docker | A |
| SOP-DOC-003 | Volume Mount Permission Denied | Docker | A |
| SOP-DOC-004 | Dependency Crash Loop (depends_on Race) | Docker | B |
| SOP-DOC-005 | Image Build Failure — Composer Version Mismatch | Docker | A |
| SOP-GIT-001 | Standard Merge Conflict | Git | A |
| SOP-GIT-002 | Rebase Conflict Requiring Manual Resolution | Git | A |
| SOP-GIT-003 | Detached HEAD / Non-Fast-Forward Push Rejection | Git | B |
| SOP-GIT-004 | Lockfile Conflict (composer.lock / package-lock.json) | Git | A |
| SOP-GIT-005 | Submodule Checkout Conflict | Git | B |
| SOP-GIT-006 | CRLF/LF Line Ending Conflict | Git | A |
| SOP-K8S-001 | Image Pull Forbidden (Registry Authentication Failure) | Kubernetes | B |
| SOP-K8S-002 | Liveness Probe Failing (HTTP 503) | Kubernetes | B |

## 5. Ticket Types Outside This Manual's Scope

Not every ticket that reaches HITE is meant to trigger a search against this manual. Three patterns are handled by the agent's own judgment before — or instead of — retrieval, and intentionally have no corresponding SOP entry here:

- **Destructive action already executed** — a log showing a command like `sudo rm -rf <path>` describes something that already happened, not a state to remediate. There is no fix to retrieve; the correct behavior is immediate escalation to a human, the same fail-closed path used by the regex denylist in SOP-03.
- **Benign, non-error log lines** — routine operational noise (a normal SSH session ending, a health check succeeding) is not a ticket to resolve at all. Treating it as one and forcing a match against this manual would manufacture a fix for a problem that doesn't exist.
- **Confirmed self-healing** — a GitOps or orchestration event reporting that a sync or reconciliation already completed successfully means the system already recovered on its own. Retrieval is unnecessary once the outcome is already known-good.

If a future SOP entry is ever added for one of these patterns, it should carry `Confidence_Tier: C` and a `No automated remediation` remediation block, rather than a fabricated fix.

---

# Category: Database & Queue (Laravel)

# SOP-DB-001: MySQL Connection Timeout (SQLSTATE 2002)
SOP_ID: SOP-DB-001
Category: Database
Confidence_Tier: A
Tags: laravel, mysql, database, timeout

## Context
Error Signature: SQLSTATE[HY000] [2002] Connection timed out, thrown from Illuminate\Database\Connectors\Connector during a query, usually accompanied by a connection-pool status line showing active connections near the configured maximum.
This occurs when the application server cannot establish a TCP connection to the database host within the PDO connect timeout window, most commonly because the database is saturated with active connections or the network path between app and DB hosts is momentarily congested.

## Diagnosis
The connection pool status logged alongside the exception (`active=98/100`) indicates the database is near its connection ceiling, so new connection attempts are queued until they exceed PDO's default timeout. This is a capacity symptom, not a network outage — the database process itself is reachable, it simply cannot accept new sessions fast enough.

## Remediation
```bash
# 1. Confirm the DB host is reachable and check current connection load
mysqladmin -h db-prod-03.internal -u app_user -p ping
mysqladmin -h db-prod-03.internal -u app_user -p status | grep Threads_connected

# 2. Raise the PDO connection timeout in config/database.php
#    'options' => [PDO::ATTR_TIMEOUT => 10]

# 3. Clear and rebuild the config cache so the change takes effect
php artisan config:clear
php artisan config:cache --env=production

# 4. Restart the PHP-FPM pool to drop any connections stuck mid-handshake
sudo systemctl restart php8.3-fpm
```
Verification: re-run the failing query manually via `php artisan tinker` and confirm `Threads_connected` drops below 80% of `max_connections` within one minute.

---

# SOP-DB-002: MySQL Too Many Connections (SQLSTATE 1040)
SOP_ID: SOP-DB-002
Category: Database
Confidence_Tier: A
Tags: laravel, mysql, database, connection-pool

## Context
Error Signature: SQLSTATE[HY000] [1040] Too many connections, typically thrown from a queue worker or artisan command, with `Threads_connected` at or above `max_connections` in the MySQL status output.
This happens when the number of concurrent client connections (application servers, queue workers, ad-hoc scripts) exceeds the database's configured `max_connections` limit.

## Diagnosis
Unlike SOP-DB-001, this is a hard rejection, not a timeout — MySQL is explicitly refusing new sessions because it is already at capacity. It is frequently caused by a developer running a local `queue:work` process against a shared staging database that was not sized for additional concurrent workers.

## Remediation
```bash
# 1. Identify and terminate idle/orphaned connections
mysql -h db-staging-01.internal -u root -p -e "SHOW PROCESSLIST;"
mysql -h db-staging-01.internal -u root -p -e "KILL <idle_process_id>;"

# 2. Raise max_connections as immediate relief (does not require restart)
mysql -h db-staging-01.internal -u root -p -e "SET GLOBAL max_connections = 300;"

# 3. Reduce concurrent workers on the application side
php artisan horizon:terminate
# lower `numprocs` in the Horizon/Supervisor config, then
php artisan horizon
```
Verification: confirm `SHOW STATUS LIKE 'Threads_connected';` stays comfortably under the new `max_connections` ceiling under normal load.

---

# SOP-DB-003: Migration Lock Wait Timeout (Error 1205)
SOP_ID: SOP-DB-003
Category: Database
Confidence_Tier: B
Tags: laravel, mysql, database, migration

## Context
Error Signature: SQLSTATE[HY000]: General error: 1205 Lock wait timeout exceeded, raised during an `ALTER TABLE` statement run via `php artisan migrate --force`, with the migration appearing to hang for several minutes before failing.
This occurs when another transaction — typically a long-running report query or an unrelated batch job — holds a lock on the same table the migration is trying to alter.

## Diagnosis
`ALTER TABLE` requires a metadata lock that cannot be granted while any other transaction holds a conflicting lock on that table, even a read lock from a `SELECT`. The migration is not broken; it is correctly waiting, and will keep failing until the blocking transaction completes or is terminated.

## Remediation
```bash
# 1. Identify the blocking transaction
mysql -h db-staging-01.internal -u root -p -e \
  "SELECT * FROM information_schema.innodb_trx ORDER BY trx_started;"

# 2. Confirm with the on-call engineer before killing anything in production,
#    then terminate the blocking session
mysql -h db-staging-01.internal -u root -p -e "KILL <blocking_thread_id>;"

# 3. Re-run the migration
php artisan migrate --force
```
Verification: `php artisan migrate:status` shows the new migration as `Ran`, and the previously blocked query completes normally afterward.
Escalation note: because killing a live transaction can be destructive, this fix should be surfaced as Tier B — proposed but not auto-applied — so an engineer confirms the blocking session is safe to terminate.

---

# SOP-DB-004: Redis/Horizon Queue Connection Refused
SOP_ID: SOP-DB-004
Category: Database
Confidence_Tier: A
Tags: laravel, redis, queue, horizon

## Context
Error Signature: Predis\Connection\ConnectionException: Connection refused [tcp://redis-<project>.internal:6379], reported by a Horizon worker after repeated supervisor restarts, with `docker logs` showing the Redis container is running but clients keep disconnecting.
This indicates the Redis container is accepting the initial TCP handshake but is being restarted or reset shortly after, often due to a memory eviction policy or an unrelated container restart on the same Docker network.

## Diagnosis
Because the container logs show "Ready to accept connections" before each disconnect, the process itself is not crashing outright — something is interrupting established connections, most commonly a `docker compose restart` triggered elsewhere in the stack or Redis hitting `maxmemory` and evicting/dropping clients.

## Remediation
```bash
# 1. Confirm the Redis container is actually stable
docker ps | grep redis-<project>
docker logs redis-<project> --tail=50

# 2. Restart the Redis service cleanly
docker compose restart redis

# 3. Restart Horizon so workers re-establish clean connections
php artisan horizon:terminate
php artisan horizon
```
Verification: `php artisan horizon:status` reports `running`, and the queue's failed-job count stops increasing.

---

# SOP-DB-005: Read Replica Lag Causing Stale Reads
SOP_ID: SOP-DB-005
Category: Database
Confidence_Tier: B
Tags: laravel, mysql, replication, read-replica

## Context
Error Signature: Read query against a replica returns stale or missing data immediately after a write, with `Seconds_Behind_Master` reported well above zero (commonly 30+ seconds) at the time of the failed read.
This occurs when an application reads from a replica immediately after writing to the primary, before replication has caught up, so the just-created or just-updated row is not yet visible.

## Diagnosis
This is a classic read-after-write consistency gap in a primary/replica topology, not a data-loss bug — the row exists on the primary and will appear on the replica once lag clears. It typically surfaces in flows where a user creates a record and the very next request reads it back for confirmation.

## Remediation
```bash
# 1. Confirm the lag at the time of the incident
mysql -h <replica_host> -u root -p -e "SHOW SLAVE STATUS\G" | grep Seconds_Behind_Master

# 2. Enable Laravel's sticky connection option so a read immediately
#    following a write in the same request goes to the primary
#    (config/database.php): 'sticky' => true

# 3. Rebuild config cache to apply the change
php artisan config:clear
php artisan config:cache --env=production
```
Verification: repeat the create-then-read flow that originally failed and confirm the record is returned immediately.
Escalation note: enabling `sticky` mode shifts load back to the primary, so this should be reviewed (Tier B) rather than auto-applied, particularly if the primary is already under load.

---

# Category: Containers (Docker)

# SOP-DOC-001: Container OOMKilled (Exit Code 137)
SOP_ID: SOP-DOC-001
Category: Docker
Confidence_Tier: A
Tags: docker, memory, oom

## Context
Error Signature: `docker inspect` reports `ExitCode 137` and `OOMKilled: true`; kernel log shows "Out of memory: Killed process" for the container's PHP-FPM process, often following a large export or import job.
This occurs when a process inside the container exceeds the memory limit assigned to it, causing the Linux kernel's OOM killer to terminate it.

## Diagnosis
The container's configured memory limit is smaller than the peak memory footprint of the workload it is running — frequently a CSV/report export that loads an entire dataset into memory rather than processing it in chunks.

## Remediation
```bash
# 1. Confirm the OOM kill in the kernel log
dmesg | grep -i "out of memory" | tail -5

# 2. Raise the container's memory limit in docker-compose.yml
#    mem_limit: 1024m  ->  mem_limit: 2048m

# 3. Recreate the container with the new limit
docker compose up -d --force-recreate <service_name>
```
Verification: re-run the job that triggered the crash and confirm memory usage (`docker stats <service_name>`) stays below the new limit.
Longer-term note: if the same job repeatedly approaches the new limit, the underlying export code should be refactored to stream/chunk data rather than relying on a larger memory ceiling.

---

# SOP-DOC-002: Healthcheck Failing — Port Already in Use
SOP_ID: SOP-DOC-002
Category: Docker
Confidence_Tier: A
Tags: docker, nginx, healthcheck, networking

## Context
Error Signature: `docker ps` shows the container as `unhealthy`; nginx error log reports `bind() to 0.0.0.0:80 failed (98: Address already in use)`.
This occurs when two replicas of the same service attempt to bind the same host port simultaneously, typically after a `docker compose up --scale` change that was not matched by an updated port mapping.

## Diagnosis
The container process itself is fine — nginx simply cannot start because another process (an orphaned replica from a previous scale operation) is already holding the port.

## Remediation
```bash
# 1. Find what is already bound to the port
sudo lsof -i :80
docker ps --format '{{.Names}} {{.Ports}}'

# 2. Stop the duplicate/orphaned container
docker stop <duplicate_container_id>

# 3. Bring the service back up at the intended scale
docker compose up -d --scale app=1 --no-recreate
```
Verification: `docker ps` shows the service as `healthy`, and `curl localhost:8080` returns a normal HTTP response.

---

# SOP-DOC-003: Volume Mount Permission Denied
SOP_ID: SOP-DOC-003
Category: Docker
Confidence_Tier: A
Tags: docker, filesystem, permissions

## Context
Error Signature: "failed to write to /var/www/html/storage/logs/laravel.log: Permission denied"; `ls -la` inside the container shows the log directory owned by `root` while the container process runs as a non-root user.
This occurs when a bind-mounted volume is recreated on a new host with default root ownership, while the container's runtime user (commonly `www-data`, uid 1000) has no write access.

## Diagnosis
This is a straightforward filesystem ownership mismatch introduced by volume recreation — it is not a code or configuration regression, and does not indicate a security issue beyond the ownership itself.

## Remediation
```bash
# 1. Inspect current ownership inside the container
docker exec <container> ls -la /var/www/html/storage/logs

# 2. Fix ownership to match the container's runtime user
docker exec -u root <container> chown -R www-data:www-data /var/www/html/storage

# 3. Persist the fix so it survives future volume recreation, by adding
#    to the image's entrypoint script:
#    chown -R www-data:www-data /var/www/html/storage
```
Verification: the application writes to `storage/logs/laravel.log` successfully on the next request without a permission error.

---

# SOP-DOC-004: Dependency Crash Loop (depends_on Race)
SOP_ID: SOP-DOC-004
Category: Docker
Confidence_Tier: B
Tags: docker, docker-compose, mysql, orchestration

## Context
Error Signature: a worker container repeatedly restarts with "No route to host" or SQLSTATE 2002 while the `db` service shows as `healthy` in `docker compose ps`; worker logs show retry attempts counting up to a fixed maximum before exiting.
This occurs when a `depends_on` healthcheck reports the database container as healthy (for example, because the port is open) before MySQL has actually finished InnoDB crash recovery and is ready to accept application connections.

## Diagnosis
The healthcheck and the actual readiness of the dependency have drifted apart — the port is technically open before the database engine is truly ready, so downstream services start too early and exhaust their retry budget before the database becomes usable.

## Remediation
```bash
# 1. Confirm the database's actual readiness versus its reported health
docker exec <db_container> mysqladmin ping -uroot -p

# 2. Tighten the healthcheck to reflect true readiness, with a longer
#    start_period to cover crash-recovery time (docker-compose.yml):
#    healthcheck:
#      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
#      interval: 5s
#      retries: 10
#      start_period: 30s

# 3. Recreate the stack so the corrected healthcheck takes effect
docker compose up -d --force-recreate
```
Verification: after a full stack restart, the worker container starts only after the database reports genuinely ready, with zero restart-loop entries in `docker compose ps`.
Escalation note: because this changes orchestration timing for the whole stack, it is surfaced as Tier B for review before being applied broadly.

---

# SOP-DOC-005: Image Build Failure — Composer Version Mismatch
SOP_ID: SOP-DOC-005
Category: Docker
Confidence_Tier: A
Tags: docker, ci-cd, composer, build

## Context
Error Signature: `docker build` fails during `composer install --no-dev --optimize-autoloader` with a class-not-found error referencing `vendor/composer/installed.php`, blocking the CI pipeline for a feature branch.
This occurs when the `composer.lock` file was generated with a newer Composer version than the one baked into the build image, producing a lock file format the older Composer binary cannot fully resolve.

## Diagnosis
This is a tooling version drift issue rather than a dependency conflict — the packages themselves are compatible, but the Composer binary in the image is stale, often because the base image's package cache has not been refreshed.

## Remediation
```bash
# 1. Confirm the Composer version baked into the current base image
docker run --rm <image> composer --version

# 2. Pin Composer explicitly in the Dockerfile rather than relying on
#    whatever apt/curl resolves at build time
#    RUN composer self-update 2.7.7

# 3. Rebuild without cache to force the pinned version to take effect
docker build --no-cache -t <image> .
```
Verification: the CI pipeline's build step completes successfully and `composer --version` inside the resulting image matches the pinned version.

---

# Category: Version Control (Git)

# SOP-GIT-001: Standard Merge Conflict
SOP_ID: SOP-GIT-001
Category: Git
Confidence_Tier: A
Tags: git, version-control, merge

## Context
Error Signature: `git merge` reports "CONFLICT (content): Merge conflict in <file>" and "Automatic merge failed; fix conflicts and then commit the result," with `git status` listing the file under "both modified."
This occurs when two branches both changed overlapping lines of the same file since their common ancestor, and Git cannot automatically decide which version to keep.

## Diagnosis
This is routine, expected Git behavior when two contributors edit the same region of a file in parallel — it does not indicate a mistake by either party, only that manual reconciliation of the two changes is required.

## Remediation
```bash
# 1. See which files need manual resolution
git status

# 2. Open each conflicting file and resolve the <<<<<<< / ======= / >>>>>>>
#    markers, keeping the correct combination of both changes

# 3. Stage the resolved file(s) and complete the merge
git add <file>
git commit -m "Resolve merge conflict in <file>"
```
Verification: `git status` shows a clean working tree and the merge commit appears in `git log`.

---

# SOP-GIT-002: Rebase Conflict Requiring Manual Resolution
SOP_ID: SOP-GIT-002
Category: Git
Confidence_Tier: A
Tags: git, version-control, rebase

## Context
Error Signature: `git rebase` stops mid-sequence with "CONFLICT (content): Merge conflict in <file>" and "error: could not apply <commit>...", requiring the conflict to be resolved before the rebase can continue.
This occurs when a commit being replayed onto a new base touches lines that the new base has since changed, the same underlying cause as a merge conflict but surfaced one commit at a time during a rebase.

## Diagnosis
Because a rebase replays commits individually, this can surface the same logical conflict repeatedly across several commits in the sequence — each one must be resolved in turn rather than all at once.

## Remediation
```bash
# 1. See which files need resolution for the current commit in the sequence
git status
git diff --name-only --diff-filter=U

# 2. Resolve the conflict markers in each listed file, then
git add <file>
git rebase --continue

# 3. If the history is too tangled to resolve safely, abort back to the
#    pre-rebase state and re-plan
git rebase --abort
```
Verification: `git rebase --continue` completes with no remaining conflicts, and `git log --oneline` shows the expected linear history.

---

# SOP-GIT-003: Detached HEAD / Non-Fast-Forward Push Rejection
SOP_ID: SOP-GIT-003
Category: Git
Confidence_Tier: B
Tags: git, version-control, branching

## Context
Error Signature: `git push` is rejected with "! [rejected] HEAD -> <branch> (non-fast-forward)," and `git status` reports "HEAD detached at <commit>," indicating commits were made without an active branch reference.
This occurs when a developer checks out a specific commit directly (for example, to test a hotfix) and then makes and commits changes without first creating a branch, leaving that work unreachable from any branch.

## Diagnosis
The work itself is not lost — it exists as a reachable commit from the detached HEAD state — but it is not attached to any branch pointer, so it cannot be pushed directly and risks being garbage-collected if left unreferenced for too long.

## Remediation
```bash
# 1. Immediately save the detached work on a proper branch
git branch recovered-work-<date>

# 2. Return to the intended branch
git checkout <branch>

# 3. Bring the recovered commits into the intended branch
git cherry-pick <commit_sha>

# 4. Push normally once the branch is up to date
git push origin <branch>
```
Verification: `git log <branch>` includes the recovered commits, and the branch push succeeds without rejection.
Escalation note: because recovery involves choosing which commits to keep and where they belong, this is surfaced as Tier B rather than auto-applied.

---

# SOP-GIT-004: Lockfile Conflict (composer.lock / package-lock.json)
SOP_ID: SOP-GIT-004
Category: Git
Confidence_Tier: A
Tags: git, dependency-management, composer, npm

## Context
Error Signature: `git pull` or `git merge` reports a conflict specifically inside `composer.lock` or `package-lock.json`, with conflict markers surrounding a version-number mismatch for the same package.
This occurs when two contributors independently run `composer update` or `npm install` and each push a lock file reflecting a slightly different dependency resolution.

## Diagnosis
Manually editing the conflict markers inside a lock file is not reliable, since the file's internal checksums must stay consistent with its own content — the correct fix is to accept one side and regenerate the lock file from the package manifest rather than hand-editing it.

## Remediation
```bash
# 1. Accept one side as the starting point (commonly the incoming branch)
git checkout --theirs composer.lock

# 2. Regenerate the lock file from the manifest so it is internally consistent
composer install
# or, for a Node project:
# npm install

# 3. Stage and commit the regenerated lock file
git add composer.lock
git commit -m "Regenerate lockfile after merge"
```
Verification: `composer validate` (or `npm ls`) reports no inconsistencies, and the application installs cleanly from the regenerated lock file.

---

# SOP-GIT-005: Submodule Checkout Conflict
SOP_ID: SOP-GIT-005
Category: Git
Confidence_Tier: B
Tags: git, submodules, version-control

## Context
Error Signature: `git submodule update --init --recursive` fails with "Your local changes to the following files would be overwritten by checkout," referencing files inside a submodule path.
This occurs when uncommitted local changes exist inside a submodule's working tree, and Git will not silently discard them when moving the submodule to the commit recorded by the parent repository.

## Diagnosis
This is Git deliberately protecting uncommitted work inside the submodule — the correct next step depends on whether those local changes are meant to be kept, which requires a judgment call rather than a safe default.

## Remediation
```bash
# 1. Inspect what has changed inside the submodule
cd packages/<project>-shared-ui
git status

# 2a. If the local changes should be kept, stash them first
git stash

# 2b. If the local changes are not needed, discard them instead
# git checkout -- .

# 3. Return to the parent repository and complete the update
cd ../..
git submodule update --init --recursive
```
Verification: `git submodule status` shows the submodule at the expected commit with a clean working tree.
Escalation note: because step 2 requires deciding whether to keep or discard local work, this is surfaced as Tier B for the requester to confirm before either path is taken.

---

# SOP-GIT-006: CRLF/LF Line Ending Conflict
SOP_ID: SOP-GIT-006
Category: Git
Confidence_Tier: A
Tags: git, line-endings, cross-platform

## Context
Error Signature: `git merge` warns "LF will be replaced by CRLF in <file>" followed by a conflict in that same file, where `git diff` shows nearly every line as changed even though the actual content edits were small.
This occurs when contributors on different operating systems have different `core.autocrlf` settings, so line endings are converted inconsistently and Git sees whole-file differences that are mostly cosmetic.

## Diagnosis
The underlying content change is usually minor; the noise comes entirely from mismatched line-ending conventions between a Windows contributor (CRLF) and a Linux/WSL contributor (LF) working on the same file.

## Remediation
```bash
# 1. Standardize line endings for this repository going forward
echo "* text=auto eol=lf" >> .gitattributes

# 2. Renormalize all tracked files to the standardized ending
git add --renormalize .
git commit -m "Normalize line endings to LF"

# 3. Ask Windows-based contributors to stop converting on checkout for this repo
git config core.autocrlf input
```
Verification: `git diff` on the previously conflicting file now shows only the genuine content change, with no whole-file line-ending noise.

---

# Category: Container Orchestration (Kubernetes)

# SOP-K8S-001: Image Pull Forbidden (Registry Authentication Failure)
SOP_ID: SOP-K8S-001
Category: Kubernetes
Confidence_Tier: B
Tags: kubernetes, ci-cd, gitops, registry

## Context
Error Signature: a Kubernetes Warning event with reason `Failed` reporting "Failed to pull image <registry>/<image>:<tag>: 403 Forbidden" for a pod, blocking the container from starting.
This occurs when the container registry rejects the pull request due to an invalid, expired, or insufficiently scoped credential in the pod's image pull secret, or because the image's visibility changed to private without the cluster's pull secret being updated to match.

## Diagnosis
A 403 response, as opposed to a 404, confirms the image reference itself is correct — the registry recognizes the request but is not authorizing it, which almost always traces back to the credential Kubernetes is using to authenticate the pull rather than a wrong image name or tag.

## Remediation
```bash
# 1. Confirm which image pull secret the pod/deployment references
kubectl get pod <pod_name> -n <namespace> -o jsonpath='{.spec.imagePullSecrets}'

# 2. Check whether the referenced secret's token is still valid
kubectl get secret <pull_secret_name> -n <namespace> -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d

# 3. Recreate the pull secret with a fresh registry token
kubectl create secret docker-registry <pull_secret_name> \
  --docker-server=ghcr.io \
  --docker-username=<registry_user> \
  --docker-password=<fresh_token> \
  -n <namespace> --dry-run=client -o yaml | kubectl apply -f -

# 4. Restart the affected deployment so it picks up the new secret
kubectl rollout restart deployment/<deployment_name> -n <namespace>
```
Verification: `kubectl get pods -n <namespace>` shows the pod transitioning to `Running`, and `kubectl describe pod <pod_name>` no longer lists a `Failed` image-pull event.
Escalation note: rotating a registry credential touches shared authentication material, so this is surfaced as Tier B — an engineer should confirm the correct token and scope before it is applied.

---

# SOP-K8S-002: Liveness Probe Failing (HTTP 503)
SOP_ID: SOP-K8S-002
Category: Kubernetes
Confidence_Tier: B
Tags: kubernetes, observability, healthcheck

## Context
Error Signature: a Kubernetes Warning event with reason `Unhealthy` reporting "Liveness probe failed: HTTP probe failed with statuscode: 503" for a pod, which restarts the container repeatedly once the failure threshold is exceeded.
This occurs when the container's health endpoint responds but reports itself as not ready to serve traffic, commonly because the process is still initializing, is overloaded, or a dependency it checks is temporarily unavailable.

## Diagnosis
A 503 response means the probe reached the application successfully — this is not a networking or crash issue, it is the application itself signaling it is unhealthy, so restarting the pod without addressing the underlying cause will likely just repeat the same failure.

## Remediation
```bash
# 1. Check what the health endpoint is actually reporting
kubectl exec <pod_name> -n <namespace> -- curl -s localhost:<port>/healthz

# 2. Review recent logs for the root cause behind the 503
kubectl logs <pod_name> -n <namespace> --previous --tail=100

# 3. If the probe is simply too aggressive for startup time, loosen it
#    rather than restart-looping the pod (deployment spec):
#    livenessProbe:
#      initialDelaySeconds: 30
#      periodSeconds: 15
#      failureThreshold: 5

# 4. Apply the updated probe configuration
kubectl apply -f <deployment_manifest>.yaml
```
Verification: `kubectl get pods -n <namespace>` shows the pod stable with zero restarts over the following several minutes, and the liveness probe succeeds consistently.
Escalation note: since the right fix depends on whether the 503 reflects a real dependency failure or just an overly strict probe, this is surfaced as Tier B for a human to confirm before probe thresholds are changed.

---

## Appendix: Reference Parser (Python)

The snippet below illustrates how a grading script can extract the structured fields from this manual — splitting on entry boundaries, then pulling metadata, error signature, and the remediation command out of each block.

```python
import re

def parse_sop_manual(path):
    text = open(path, encoding="utf-8").read()
    # Split into individual SOP entries on the H1 boundary
    blocks = re.split(r"\n(?=# SOP-)", text)
    entries = []
    for block in blocks:
        if not block.startswith("# SOP-"):
            continue
        title_match = re.match(r"# (SOP-[\w-]+): (.+)", block)
        if not title_match:
            continue
        sop_id, title = title_match.group(1), title_match.group(2)

        meta = dict(re.findall(r"^(\w+): (.*)$", block, re.MULTILINE))

        sig_match = re.search(r"Error Signature: (.*)", block)
        error_signature = sig_match.group(1) if sig_match else None

        code_match = re.search(r"```bash\n(.*?)```", block, re.DOTALL)
        remediation = code_match.group(1).strip() if code_match else None

        entries.append({
            "sop_id": sop_id,
            "title": title,
            "category": meta.get("Category"),
            "confidence_tier": meta.get("Confidence_Tier"),
            "tags": [t.strip() for t in meta.get("Tags", "").split(",")],
            "error_signature": error_signature,
            "remediation_command": remediation,
        })
    return entries
```

— End of Manual —
