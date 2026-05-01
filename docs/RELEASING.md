# Releasing getarch

Releases publish to PyPI as a wheel + sdist and to a GitHub Release as those
artefacts plus a single-file `getarch.pyz` (a `shiv` zipapp).

## One-time setup

* On https://pypi.org/manage/account/publishing/, register a Trusted
  Publisher for the `getarch` project pointing at this repository, the
  `release.yml` workflow, and the GitHub environment named `pypi`.
* In this repository's settings, create the `pypi` environment and protect
  it with branch/tag rules so only `v*` tag pushes can deploy.

No PyPI API tokens are needed: the workflow uses
[OIDC Trusted Publishing](https://docs.pypi.org/trusted-publishers/).

## Cutting a release

```bash
# Bump the version in pyproject.toml.
uv version 2.0.0
git add pyproject.toml
git commit -m "chore: release 2.0.0"
git tag -a v2.0.0 -m "v2.0.0"
git push origin main --tags
```

The `release.yml` workflow then:

1. Computes `SOURCE_DATE_EPOCH` from the tagged commit's timestamp
   (`git log -1 --format=%ct`) and pins `PYTHONHASHSEED=0`, `LC_ALL=C`,
   `TZ=UTC` for deterministic output.
2. Builds the wheel + sdist with `uv build` (honours `SOURCE_DATE_EPOCH`).
3. Builds `dist/getarch.pyz` with `shiv --reproducible --build-id "$SOURCE_DATE_EPOCH"`.
4. Re-runs the shiv build and `cmp` against the first artefact: the job
   fails if the two zipapps are not bit-identical.
5. Publishes the wheel + sdist to PyPI via the Trusted Publisher.
6. Attaches all three artefacts to a GitHub Release for the tag.

## AUR upload

The repository ships an AUR-ready `PKGBUILD` under
`packaging/aur/getarch/`. After a release lands on PyPI:

1. Bump `pkgver` in `packaging/aur/getarch/PKGBUILD` and the matching
   `.SRCINFO`.
2. Replace the placeholder `sha256sums=('SKIP')` with the real PyPI
   sdist checksum:
   ```bash
   curl -sL "https://files.pythonhosted.org/packages/source/g/getarch/getarch-${VERSION}.tar.gz" \
     | sha256sum
   ```
3. Refresh `.SRCINFO`:
   ```bash
   cd packaging/aur/getarch
   makepkg --printsrcinfo > .SRCINFO
   ```
4. Push to the AUR repo (separate `ssh://aur@aur.archlinux.org/getarch.git`
   remote — set up with `git remote add aur …`).
5. Commit the bumped `pkgver` + `.SRCINFO` + checksum back to this repo
   so the in-tree PKGBUILD stays in sync with what's on AUR.

## Local dry run

```bash
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) \
PYTHONHASHSEED=0 LC_ALL=C TZ=UTC \
  uv build
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) \
PYTHONHASHSEED=0 LC_ALL=C TZ=UTC \
  uv run --with shiv shiv \
    --reproducible \
    --build-id "$(git log -1 --format=%ct)" \
    -c getarch -o dist/getarch.pyz .
./dist/getarch.pyz --help
```
