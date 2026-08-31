from enum import StrEnum


class Decision(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    ERROR = "ERROR"


class EvidenceTrust(StrEnum):
    """How strongly ForgeGate can trust the producer identity."""

    UNSIGNED_LOCAL = "unsigned_local"
    CLAIMED_CI_METADATA = "claimed_ci_metadata"
    VERIFIED_CI_IDENTITY = "verified_ci_identity"
    SIGNED_ATTESTATION = "signed_attestation"


class VerificationLevel(StrEnum):
    """What kind of engineering observation the evidence represents."""

    DECLARED = "declared"
    SIMULATED = "simulated"
    REPLAYED = "replayed"
    HOST_TESTED = "host_tested"
    TARGET_BUILT = "target_built"
    CI_VALIDATED = "ci_validated"
    SYSTEM_OBSERVED = "system_observed"
    PHYSICALLY_VERIFIED = "physically_verified"


class CollectorType(StrEnum):
    JUNIT = "junit"
    COVERAGE_XML = "coverage_xml"
    LCOV = "lcov"
    SARIF = "sarif"
    BENCHMARK_JSON = "benchmark_json"
    MANUAL_APPROVAL = "manual_approval"


class Operator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    EXISTS = "exists"


class Aggregation(StrEnum):
    VALUE = "value"
    COUNT = "count"
    ALL = "all"
    ANY = "any"
