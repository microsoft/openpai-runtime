# GIT plugin

## Goal
The cmd plugin offers user to download code from git repo.

## Schema
```yaml
extras:
  com.microsoft.pai.runtimeplugin:
    - plugin: git
      parameters:
        repo: <git repo>
        options:
        - <git clone options>
        clone_dir: <clone dir>
```