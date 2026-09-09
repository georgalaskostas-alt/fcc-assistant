# Local site configuration

FCC Assistant can load a semantic catalog for one or many refinery units without committing real plant metadata to GitHub.

Set the environment variable `FCC_SITE_CONFIG` to a local JSON file before starting the backend.

Example:

```bash
export FCC_SITE_CONFIG="$HOME/.fcc-assistant/site.json"
```

Use `examples/site-config.example.json` as a safe template.

The catalog contains semantic unit and variable names only. Production PI WebIds, credentials and other plant-specific connection details should remain in separate local configuration and must not be committed.

When `FCC_SITE_CONFIG` is not set, the application uses the built-in FCC development catalog so the simulator continues to work out of the box.
