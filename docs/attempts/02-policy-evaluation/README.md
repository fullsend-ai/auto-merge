# Attempt 2: policy evaluation before merge authority

Status: local synthetic and SDK/platform experiments executed; historical
read-only GitHub observation and native vendor-content preparation executed.
An active PR/workflow trial is not deployed; this is not production-ready.

Attempt 1 remains the installed agent-led lab. Attempt 2 tests whether reusable
Gemara artifacts and a small deterministic evaluator can represent requirements,
assess bounded evidence and produce an explainable non-authoritative result.
The [platform experiment](../../../experiments/autonomy-platform/README.md) tests
SDK reuse, repository qualification, the four modes,
trusted shared/repository policy and an alternative engine. Read the
[platform experiment plan](SPIKE-PLAN.md) for the revised scope. An optional
model observer is secondary and cannot provide merge authority.

Start with the [runnable demo](../../../experiments/gemara-spike/README.md),
the [recorded walkthrough](../../../experiments/gemara-spike/walkthrough.html),
then the [findings](FINDINGS.md), [work log](WORKLOG.md),
[ADR proposal](ADR-PROPOSAL.md), and [Attempt 1 baseline](../01-agent-led/README.md).

The three responsibilities remain separate:

1. Review and other evidence producers supply judgments and observations.
2. Policy evaluation interprets the required evidence and may recommend a hold.
3. A trusted runtime and native SCM would control any real merge request.

Policy assessment and local qualification are implemented. The original demo
uses synthetic input; the separate observer uses GitHub GET requests and saves
only normalized observations. It passes no credential to either adapter and
does not execute the installed agent or enable mutation. Independent native-SDK
and JSON implementations now exercise a common result boundary for a closed
lab profile. This is not general policy-engine equivalence. See the
[measured SDK compatibility limit](../../../experiments/autonomy-platform/SDK-COMPATIBILITY.md)
before choosing a production implementation.
