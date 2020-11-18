# GIT plugin

## Goal
The cmd plugin offers user to download code from git repo.

## Schema
```yaml
extras:
  com.microsoft.pai.runtimeplugin:
    - plugin: git
      parameters:
        repo_uri: <git repo>
        options:
        - <git clone options>
        clone_dir: <clone dir>
      failurePolicy: ignore/fail
```

## Notice
If parameter `clone_dir` is missing, repo will be cloned into `/usr/local/pai/code`.

If `clone_dir` exists and is not empty, `git` plugin will failed.