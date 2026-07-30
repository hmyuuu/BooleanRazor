# BooleanRazor GitHub Pages Publication Design

**Date:** 2026-07-30

**Status:** approved design; implementation planning follows user review

**Repository:** `/Users/hmyuuu/workspace/BooleanRazor`

## 1. Purpose

BooleanRazor generates a checked, dependency-free report in `reports/site/`.
The report works from a local HTTP server, but the repository has no GitHub
Pages workflow. A direct upload of `reports/site/` would break evidence links
such as `../../src/table.rs` because those links leave the uploaded directory.

This design adds a Pages-specific publication stage. The stage keeps the local
report offline-first and converts repository evidence links into GitHub links
bound to the deployed commit. Pull requests build and validate the same
artifact. Pushes to `main` deploy it through GitHub's `github-pages`
environment.

The workflow follows the useful job structure in
[OrbitBreakersBench's Pages workflow](https://github.com/hmyuuu/OrbitBreakersBench/blob/main/.github/workflows/pages.yml):
one build job for pull requests and pushes, plus a deployment job restricted
to `main`. BooleanRazor adds commit-bound evidence links and stricter artifact
checks because its report acts as a scientific evidence index.

## 2. Goals

The implementation will:

- publish the generated report at the root of the BooleanRazor Pages site;
- keep report pages, styles, scripts, and internal navigation relative;
- map repository evidence links to the exact GitHub commit that produced the
  artifact;
- run `make report-check` before packaging;
- reject broken links, path escapes, symlinks, and non-regular files;
- build the artifact on pull requests without deploying it;
- deploy only a successful `main` build;
- use GitHub's `github-pages` environment and required OIDC permissions;
- provide local commands and tests for the artifact builder;
- leave scientific claims and generated report bytes unchanged.

## 3. Non-goals

This work will not:

- publish the repository tree, hidden data, run results, or custodian state;
- change `reports/data/project.json` or any scientific status;
- add a static-site framework, Node dependency, CDN, tracker, or runtime fetch;
- make branch previews public;
- run Rust tests, Julia verification, benchmark cells, or remote compute;
- add a custom domain;
- grant a workflow token repository-administration permission.

GitHub may require one repository setting before the first deployment:
**Settings → Pages → Build and deployment → GitHub Actions**. The workflow's
`GITHUB_TOKEN` cannot enable Pages when the repository has no Pages
configuration. A maintainer will perform that one-time setting change if the
repository needs it.

## 4. Chosen approach

Add a small Python publication builder and upload its `_site/` output.

The builder copies only `reports/site/`, adds `.nojekyll`, and rewrites links
that resolve inside the repository but outside `reports/site/`. Each rewritten
link points to:

```text
https://github.com/hmyuuu/BooleanRazor/blob/<deployment-commit>/<repo-path>
```

The builder derives `<deployment-commit>` from the checked-out Git `HEAD`.
This choice gives a reader GitHub's source view while binding the evidence to
the same snapshot as the published report.

Two alternatives were rejected:

1. Uploading `reports/site/` without a publication stage would leave evidence
   links broken.
2. Uploading the whole tracked repository would expose unrelated files and
   include tracked symlinks, which GitHub Pages artifacts forbid.

## 5. Components

### 5.1 Pages artifact builder

Add `scripts/build-pages.py` with this command:

```bash
uv run python scripts/build-pages.py \
  --repo-root . \
  --source reports/site \
  --output _site \
  --repository https://github.com/hmyuuu/BooleanRazor
```

The builder will:

1. resolve the repository root, source, and output without following
   symlinks;
2. require a clean 40-character commit ID from `git rev-parse HEAD`;
3. refuse unsafe output targets such as the repository root, filesystem root,
   or user home;
4. copy regular source files into a fresh staging directory;
5. use the Python standard library HTML parser to collect and validate link
   attributes;
6. classify each `href` and `src`;
7. preserve page fragments, external HTTPS links, and links whose targets stay
   inside `reports/site/`;
8. replace only the exact double-quoted attribute values for
   repository-local targets outside `reports/site/` with commit-bound GitHub
   blob URLs;
9. reject targets that leave the repository or use unsafe schemes;
10. verify each remaining internal artifact target;
11. write `.nojekyll`; and
12. replace `_site/` only after all checks pass.

The builder will preserve query strings and fragments during link
classification. It will percent-encode repository paths for GitHub URLs.
Generated HTML content will differ from `reports/site/` only at rewritten
link attributes.

### 5.2 Make targets

Add:

```text
make pages
make test-pages
```

`make pages` builds `_site/` from the checked report. `make test-pages` runs
the focused builder tests. The existing `test-report` target will include the
Pages builder tests so `make test` continues to cover report delivery.

Add `_site/` to `.gitignore`. The repository will track the builder, tests,
workflow, and design documents. It will not track the deployment artifact.

### 5.3 GitHub Actions workflow

Add `.github/workflows/pages.yml` with:

- `push` on `main`;
- `pull_request`;
- `workflow_dispatch`;
- top-level `contents: read`;
- concurrency group `pages-${{ github.ref }}` with stale runs cancelled.

The build job will:

1. check out the exact revision and full history with `actions/checkout@v6`
   and `fetch-depth: 0`, because `make report-check` resolves historical
   evidence commits;
2. install uv with the reviewed `astral-sh/setup-uv@v8` action and provision
   Python 3.11.13;
3. sync the locked development environment for Python 3.11.13;
4. run `make report-check`;
5. run the focused Pages tests;
6. build `_site/`; and
7. upload `_site/` with `actions/upload-pages-artifact@v4` and
   `include-hidden-files: true` so the artifact retains `.nojekyll`.

The deploy job will run only when the event is not `pull_request` and the ref
equals `refs/heads/main`. It will:

- depend on the build job;
- grant `pages: write` and `id-token: write`;
- target the `github-pages` environment;
- expose `steps.deployment.outputs.page_url`;
- run `actions/configure-pages@v5`; and
- run `actions/deploy-pages@v4`.

The workflow will not use path filters. A change to any tracked evidence file
can change the commit that a report link should cite, so each pull request and
`main` push must build one commit-bound artifact.

## 6. Data flow

```text
reports/data/project.json
        |
        v
make report-check
        |
        v
checked reports/site/
        |
        v
scripts/build-pages.py + git HEAD
        |
        +--> internal report links stay relative
        +--> repository evidence links become GitHub blob URLs at HEAD
        `--> _site/.nojekyll
                    |
                    v
        upload-pages-artifact
                    |
                    v
        deploy-pages on main only
```

The publication stage reads generated report files and Git metadata. It does
not read private datasets, run directories, environment secrets, or untracked
files.

## 7. Failure behavior

The build job will fail before artifact upload if:

- `make report-check` detects claim, schema, evidence, or generated-byte drift;
- Git `HEAD` does not name one exact commit;
- a source or output path crosses a symlink;
- an HTML link escapes the repository;
- an internal artifact link has no target;
- the source includes a non-regular file;
- the output contains a symbolic or hard link; or
- the builder cannot publish `_site/` as one complete artifact.

Pull-request failures block publication checks without touching the live site.
A failed `main` build leaves the prior Pages deployment intact. The deploy job
cannot run until the build job uploads a valid artifact.

## 8. Testing

`scripts/tests/test_build_pages.py` will cover:

- copying all four report pages and static assets;
- adding `.nojekyll`;
- preserving report navigation and fragment links;
- rewriting `../../src/...`, `../../tests/...`, `../../scripts/...`, and
  `../../research/...` targets to the exact commit;
- percent-encoding repository paths;
- rejecting a link outside the repository;
- rejecting symlinked source content and unsafe output paths;
- rejecting missing internal files;
- leaving HTTPS reference links unchanged;
- publishing output only after a successful validation pass; and
- producing the same artifact bytes for repeated builds at one commit.

A workflow-contract test will inspect `.github/workflows/pages.yml` and assert
the event gates, full-history checkout, job dependency, permissions,
environment, artifact path, hidden-file handling, and supported action
versions. The test will also assert that pull requests cannot enter the deploy
job.

Verification before completion will run:

```bash
make test-pages
make report-check
make test-report
make test
git diff --check
```

## 9. Acceptance criteria

The work is complete when:

1. a local `make pages` creates a symlink-free `_site/` with no broken internal
   links;
2. each repository evidence link names the local `HEAD` commit in its GitHub
   URL;
3. pull requests build and upload a validated Pages artifact without
   deploying;
4. a push to `main` deploys through the `github-pages` environment;
5. the deployed root opens the BooleanRazor status page;
6. the trajectory, methods, verification, and experiment pages retain their
   current content and navigation;
7. the focused and full local test commands pass; and
8. the repository documents the one-time Pages source setting.

The first live deployment may wait for a maintainer to enable GitHub Actions as
the Pages source. That setting changes repository configuration, while this
spec covers the tracked workflow and artifact contract.
