# octopus-cli

The reference implementation of the [Octopus](../README.md) folder-native task system.

## Install (development)

```bash
cd cli/
pip install -e .[dev]
```

After install, both `octopus` and `octo` are on PATH and behave identically.

```bash
octopus --version
octo --help
```

## Status

Walking-skeleton (request 02). Pure file operations on `.octopus/` folders. No SQLite, no TUI, no adapters yet.

Implemented verbs:

- `init`, `where`
- `capture`, `task list`, `task show`
- `plan`, `focus`, `park`, `defer`
- `start`, `finish`, `drop`
- `set`

See `.spectacular/specs/CLI-VERBS.md` for the verb contract.
