# Product brief

ForgeGate answers one question: given a release candidate, its versioned policy,
and engineering artifacts produced elsewhere, is there sufficient attributable
evidence to mark the candidate PASS, FAIL, REVIEW, or ERROR?

The first user is an individual developer or small team that already runs tests
and scans but lacks a consistent, explainable release decision. ForgeGate does
not execute those tools. It validates and normalizes their outputs, binds them to
a candidate and execution context, applies a deterministic policy, and exports
an auditable result.

## Current product objective — 2026-09-08

Build a useful, independently reviewable Windows engineering tool and a credible
portfolio project. Commercialization and paid adoption are not acceptance
prerequisites. The intended user already has test and analysis reports and needs
to assess, explain and hand off one software version.

The primary task is: select a project/version and existing reports, understand
blocking or missing evidence, and deliver a conclusion another person can check.
The expected benefit is less manual report reconciliation and handoff work while
preserving correct decisions. Human time savings and improved error detection
remain **NOT MEASURED**; parser speed and regression-test counts are not substitutes.

Phase 52 established local installed-wheel delivery. Standard software reports,
reviewed Dashboard decisions, and bounded original-report offline replay are
implemented. AVS is a real integration case; the generic example and core remain
usable independently. Optional MSP430 live status supports the operator and is
separate from release evidence. See [current status](../PROJECT_STATUS.md).

## Product decisions

- Reuse standard reports and the existing policy/collector services. Keep the
  core domain-neutral and consume peer projects through versioned artifacts.
- Compare against a competent manual workflow using ordinary report viewers,
  search, spreadsheets and documented hash tools. Do not handicap the baseline.
- Measure setup separately from repeat use, include user interaction and report
  preparation, and score exact decisions, reasons and source references.
- Retain integrity, scope, policy-authority and idempotency checks when reducing
  UI steps. A faster incorrect release decision is unacceptable.
- Keep implemented recovery, plugin and device capabilities; defer new managed
  workspace switching, broader plugin ecosystems and team/cloud expansion until
  an observed core-task need justifies them. Existing accessibility obligations
  remain open quality work, not presumed complete.

The [Phase 53 protocol](EFFICIENCY_ACCEPTANCE.md) defines baseline collection,
bottleneck selection and remeasurement. It is a plan, not an efficiency result.
Every substantial next feature must name its user task, expected reduction in
effort or error, design tradeoff, and verification method.

## Non-goals

- device control, a general telemetry platform, analog acquisition, crawling,
  or test execution; the implemented input-only MSP430 monitor is optional;
- a generic project-management system;
- production-grade identity operations, SaaS, SSO, or compliance certification;
  existing local Ed25519 signing does not authenticate imported report producers;
- treating file presence, a hash, or user-supplied CI metadata as proof that a
  test truly ran.
