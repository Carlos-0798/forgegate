# Start an independent local workspace

ForgeGate turns existing engineering reports into a reviewed policy decision and
a portable assurance package. It does not execute your tests. Start with the
synthetic demonstration below, then use your real report files and an appropriate
policy. Windows and Python 3.12 are the tested target.

## Install and prepare

In a short, private local directory, with the supplied wheel beside you:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .\forgegate-0.1.0a1-py3-none-any.whl
.\.venv\Scripts\python.exe -m forgegate workspace-init .\my-workspace --demo
```

The installation requires the dependencies in your package cache or access to
your configured Python package index. This is not an offline dependency bundle.
Use the explicit interpreter path above; no activation script or PowerShell
execution-policy change is needed.

Initialization refuses every existing target, including an empty directory. It
creates a random local operator identity restricted to `sample-project`, two
databases, project/policy documents, original synthetic JUnit files and two
reviewable candidates. It does **not** start a service or browser session.
Omit `--demo` for a clean workspace with no candidate or evidence records.
Use `--project-id my-project --project-name "My Project"` to customize it.

## Start, then authorize the browser

From the same installation directory:

```powershell
.\.venv\Scripts\python.exe -m forgegate dashboard `
  --database .\my-workspace\forgegate.db `
  --trust-store .\my-workspace\trust-store.json `
  --job-store .\my-workspace\jobs.db --existing-pair --port 8000
```

Keep the terminal running and visit `http://127.0.0.1:8000/app/`.
Select **Start local activation**. In a second PowerShell terminal, replace the
example code with the one currently shown in the browser:

```powershell
.\.venv\Scripts\python.exe -m forgegate dashboard-activate FG-ABCDE-FGHJK `
  --server http://127.0.0.1:8000 `
  --identity .\my-workspace\identity.json `
  --private-key .\my-workspace\operator-key.pem `
  --role operator --project sample-project
```

If you changed the project ID, use that ID in the activation command. If the port
is occupied, change it in both commands and the browser URL. A browser refresh
cannot start a stopped local server. Stop deliberately with `Ctrl+C`; the
workspace persists and the same start command reopens it.

## Review and repeat a complete task

1. On **Overview**, review `synthetic-demo-pass` and `synthetic-demo-fail`.
   The negative example is an intended policy rejection, not a software crash.
2. Start **Quick assessment** for another candidate. Use the corresponding
   synthetic commit shown in `my-workspace/START_HERE.md`, not an actual commit.
3. Select the original `artifacts/synthetic-demo-pass.xml` or
   `artifacts/synthetic-demo-fail.xml`. Load and explicitly select the saved
   policy. Review the original-file metadata and normalized counts.
4. Confirm assessment. Expected results: PASS has 2 passing tests, 0 failures
   and 0 errors; FAIL has 1 passing test, 1 failure and 0 errors.
5. Review and download the assurance package. Extract it into the directory
   named by its ZIP basename, then run `forgegate verify-assurance <directory>`.
   Save originals for offline replay before leaving the assessment if needed.

The starter policy also rejects error-only, zero-test and all-skipped reports.
It does not claim coverage, performance or security requirements have passed.
Edit/review an appropriate policy and materialize it for the candidate's frozen
project profile before relying on real project decisions. For a workspace with
no evaluated history, `START_HERE.md` explains first-policy materialization.
Existing saved policies are immutable historical inputs; updates to the default
template do not silently modify them.

## Private files and evidence

`operator-key.pem` is an unencrypted private key. Keep the entire workspace in a
private directory with appropriate Windows account permissions. Its `.gitignore`
prevents accidental ordinary Git addition but is not encryption or an ACL.
Do not share the workspace, database, private key or original reports by default.
Review deliberately exported files before handing them to a recipient.

The samples are **SYNTHETIC / declared / unsigned_local**. They demonstrate
software behavior, not producer authenticity, physical measurements or measured
human productivity gains. No hardware access is enabled by this quickstart.
