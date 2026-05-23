---
status: queued
priority: low
owner: alex
updated: 2026-05-21
summary: "Publish octopus-adapter-sdk as a separate package so others can write adapters."
related:
  - 06-adapter-framework
  - 14-adapter-reminders-twoway
gates:
  - 14-adapter-reminders-twoway
---

# Adapter SDK (v2)

## Goal

Extract the `Adapter` protocol and its support types into a standalone package (`octopus-adapter-sdk`) so third parties (and future-you) can implement adapters without depending on the core CLI internals.

## To be expanded when activated.
