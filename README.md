# Evidentia

## Evidence Supportability Engine

Evidentia tests whether a submitted evidence package can support a claimed recycling event.

> **Traceability records what was submitted. Evidentia tests what that evidence can actually support.**

Built as a HackDays 2.O prototype with a Gemini-powered evidence analysis pipeline.

## What it does

Evidentia takes:

- a structured recycling claim
- supporting documents such as certificates, invoices, manifests, weighbridge records, and facility records

It then:

1. Screens the submitted files through an evidence intake gate.
2. Uses Gemini for source-grounded extraction from messy PDFs and scanned evidence.
3. Validates extracted facts against their original sources.
4. Applies deterministic evidence and constraint logic.
5. Tracks provenance and correlated evidence.
6. Builds a case-scoped constraint graph.
7. Produces an evidence support envelope and identifies the binding constraint.
8. Uses Gemini again for bounded multimodal reconciliation and review reasoning.
9. Generates an evidence resolution path and replayable audit result.

Gemini does not make the final quantitative decision. Deterministic backend logic remains authoritative for calculations and hard constraints.

## Demo

The included synthetic evidence pack demonstrates a claim of **20.0 t**.

### Baseline

```text
Claimed:            20.0 t
Evidence-supported: 11.2 t
Final supportable:   8.0 t
Binding constraint: processing capacity