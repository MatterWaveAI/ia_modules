# Publishing ia_modules to PyPI

Releases publish to PyPI from GitHub Actions using
[trusted publishing](https://docs.pypi.org/trusted-publishers/): PyPI trusts the
`publish.yml` workflow in `github.com/matterwaveai/ia_modules` over GitHub OIDC,
so no API token is stored anywhere.

## One-time setup

1. On the PyPI project page for `ia_modules`, open **Publishing** and add a
   GitHub trusted publisher: owner `matterwaveai`, repository `ia_modules`,
   workflow `publish.yml`, environment `pypi`.
2. In the GitHub repository settings, create an environment named `pypi`
   (optionally with required reviewers).

## Releasing

1. Set `version` in `pyproject.toml` (for example `0.3.0`), add the release notes,
   and merge to `main`.
2. Publish a GitHub release whose tag is `v` plus that version (for example `v0.3.0`).

Publishing the release triggers `.github/workflows/publish.yml`, which:

1. Fails unless the release tag equals `v<version>` from `pyproject.toml`.
2. Installs the package with `pip install -e ".[dev,all]"` and runs `pytest tests/unit`.
3. Builds with `python -m build` and checks with `twine check dist/*`.
4. Uploads `dist/` to PyPI through `pypa/gh-action-pypi-publish` in the `pypi` environment.

Pushing a tag alone does not publish; only a published release does.

## Checking a build locally

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

## Fixing a bad release

PyPI never accepts the same version twice. Bump the version, release again, and
yank the bad version on PyPI if needed.
