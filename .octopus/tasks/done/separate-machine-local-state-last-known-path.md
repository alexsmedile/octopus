---
archived: true
bucket: done
created: '2026-06-15'
end_date: '2026-06-20'
kind: chore
title: Separate machine-local state (last_known_path) from versioned activity.md
---

> Resolved as **D110** (machine-local state in `config.local.toml`), implemented
> in the CLI. Two follow-ups filed for the shipped gaps:
> [[init-auto-gitignore-config-local-toml]] and
> [[reindex-force-migrate-last-known-path]].

## Problema

`activity.md` mischia metadati condivisibili (id, title, type, status) con stato
**machine-specific**: `last_known_path` è un path assoluto (es.
`/Users/alex/code/flows/soulid-documents`). Poiché `activity.md` finisce sotto
git, committarlo porta lo username/percorso macchina nella history di un repo
potenzialmente condiviso/pubblico — in contrasto con la natura "local-first" del
tool e con il fatto che ogni clone su un'altra macchina avrà un path diverso.

Riscontrato committando `.octopus/` nel repo `soulid-documents`: il commit guard
ha segnalato `/Users/alex/...` in `activity.md`.

## Vincoli attuali

- `last_known_path` è **required** (`core/models.py:93-94`).
- Serve a rilevare rename/spostamenti cartella (`db/reindex.py:98-99`).
  Quindi non è eliminabile: ha una funzione.

## Proposta

Separare lo stato locale dai metadati versionati:

- Spostare `last_known_path` (ed eventuale altro stato macchina) in un file
  **gitignorato**, es. `.octopus/local.yml` o `.octopus/.local/state.yml`.
- `octopus init` aggiunge automaticamente quel path a `.gitignore` (creandolo se
  manca), come fanno gli altri tool folder-native.
- `activity.md` resta condivisibile: solo identità e metadati di progetto.
- Mantenere retrocompatibilità: se `last_known_path` è ancora in `activity.md`,
  leggerlo e migrarlo al file locale al primo comando (vedi octopus-migrate).

## Acceptance

- Nuovo `octopus init` non scrive path assoluti in file versionati.
- `.octopus/` committabile senza far scattare scanner di path/segreti.
- Reindex/rename detection continua a funzionare via lo stato locale.
