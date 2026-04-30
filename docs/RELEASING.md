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

1. Builds the wheel + sdist with `uv build`.
2. Builds `dist/getarch.pyz` with `shiv`.
3. Publishes the wheel + sdist to PyPI via the Trusted Publisher.
4. Attaches all three artefacts to a GitHub Release for the tag.

## Local dry run

```bash
uv build
uv run --with shiv shiv -c getarch -o dist/getarch.pyz .
./dist/getarch.pyz --help
```
