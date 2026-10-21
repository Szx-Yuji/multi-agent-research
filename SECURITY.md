# Dependency security

The backend uses pip with Python **3.11**. Both production and development
requirements use `backend/constraints.txt`, which pins the reviewed dependency
graph. Keep it with both requirements files when copying or deploying the
backend. It contains **68 pins**: the tested Python 3.11.15 environment installs
67 packages; `async-timeout` is only required on Python 3.11.0–3.11.2.

Use Node **24** and npm **11.12.1** for the frontend. Its authoritative lockfile
is `frontend/package-lock.json`. Keep dependency scripts disabled through
`frontend/.npmrc` and explicit install flags.

```sh
# From backend/, in a clean Python 3.11 virtual environment:
python -m pip install --only-binary=:all: -r requirements-dev.txt
python -m pip check

# From the repository root, using a separate audit environment:
python -m pip install --only-binary=:all: pip-audit==2.10.1
python -m pip_audit --strict --no-deps --disable-pip -r backend/constraints.txt --format json

# From frontend/:
npm ci --ignore-scripts --no-audit
npm audit --json
```

Review upstream changes and update individual Python pins deliberately. Then
reinstall into a clean environment, compare `pip freeze`, run the audit and the
backend tests, and check Linux wheel availability. Regeneration guidance is in
`backend/constraints.txt`. Review JavaScript release notes and lockfile changes
before upgrading, and verify with `npm ci --ignore-scripts` and the build.
Review the source of any dependency lifecycle or build script before allowing
it; avoid broad script approval or forced major upgrades.

On **2026-10-21**, pip-audit **2.10.1** reported no known advisories for all 68
constraint pins. A fresh wheel-only install passed all 82 backend tests with
external sockets and DNS disabled, provider clients mocked, a temporary SQLite
database and no real `.env` files. The constraints also resolved with binary
wheels for Linux x86_64/Python 3.11. These checks cover known advisories and
tested behavior; they are not proof that dependencies have no other defects.

The dependency-audit workflow audits all Python pins and the complete npm
lockfile on changes and weekly, and saves raw JSON reports. There are no
advisory exceptions. Audit before release and keep new findings visible.
