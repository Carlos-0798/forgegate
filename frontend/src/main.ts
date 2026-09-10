import "./styles.css";

type Role = "operator" | "producer";
type Route = "overview" | "devices" | "projects" | "candidates" | "evidence" | "decision" | "assurance" | "audit" | "jobs" | "recovery";

interface RecoveryDependency {
  backup_sha256: string;
  job_ids: string[];
  status: "VERIFIED" | "NOT_SUPPLIED" | "FAILED";
  error_code: string | null;
  result_payloads_verified: number;
  jobs_without_result: number;
}

interface RecoveryHandoff {
  schema_version: "forgegate.recovery-readiness-handoff.v1";
  handoff_id: string;
  source_report_sha256: string;
  report_fingerprint: string;
  disposition: "READY_FOR_REHEARSAL" | "BLOCKED";
  readiness: {
    schema_version: "forgegate.workspace-recovery-readiness.v1";
    backup_sha256: string;
    manifest_fingerprint: string;
    checked_at: string;
    status: "READY" | "INCOMPLETE";
    archived_job_count: number;
    dependencies: RecoveryDependency[];
    availability: "observed_during_check_only";
    restore: "NOT_PERFORMED";
  };
  dependency_count: number;
  verified_dependency_count: number;
  result_payloads_verified: number;
  jobs_without_result: number;
  payload_transfer: "NOT_INCLUDED";
  live_availability: "NOT_CHECKED";
  restore: "NOT_PERFORMED";
}

interface RecoveryRehearsalReview {
  schema_version: "forgegate.recovery-rehearsal-review.v1";
  review_id: string;
  source_receipt_sha256: string;
  disposition: "VERIFIED_RESTORED_COPY";
  receipt: {
    schema_version: "forgegate.recovery-rehearsal.v1";
    rehearsal_id: string;
    handoff_sha256: string;
    handoff: RecoveryHandoff;
    completed_at: string;
    candidate_store: { sha256: string; size_bytes: number };
    job_store: { sha256: string; size_bytes: number };
    post_restore_job_count: number;
    post_restore_job_event_count: number;
    post_restore_inspection_fingerprint: string;
    status: "RESTORED_COPY_VERIFIED";
    restore_mode: "new_directory_only";
    archived_payloads: "VERIFIED_EXTERNAL_NOT_REHYDRATED";
    live_workspace_changed: false;
    automatic_execution: "NOT_PERFORMED";
    hardware_access: "NOT_PERFORMED";
    producer_authenticity: "NOT_VERIFIED";
    external_identity_and_artifact_files: "NOT_CHECKED";
    availability: "observed_during_rehearsal_only";
  };
  path_input: "NOT_ACCEPTED";
  restore_execution: "NOT_PERFORMED_BY_REVIEW";
  live_workspace_switch: "NOT_PERFORMED";
  continuing_availability: "NOT_CHECKED";
}

interface CollectionJob {
  schema_version: "forgegate.collection-job.v1" | "forgegate.collection-job.v2";
  job_id: string;
  candidate_id: string;
  project_id: string;
  state: string;
  revision: number;
  created_at: string;
  updated_at: string;
  lease_expires_at: string | null;
  result_fingerprint: string | null;
  request_fingerprint: string;
  candidate_fingerprint: string;
  error_code: string | null;
  source_bytes: string;
  authority: string;
  execution_owner_id?: string | null;
  lease_renewal_count?: number;
}

interface JobPage {
  enabled: boolean;
  project_id: string;
  jobs: CollectionJob[];
  next_after_job_id: string | null;
  has_more: boolean;
  observed_at: string;
  archived_job_ids: string[];
  project_usage: {
    schema_version: "forgegate.job-project-usage.v1";
    project_id: string;
    store_version: 3 | 4;
    archiving_enabled: boolean;
    current_jobs: number;
    archived_jobs: number;
    pending_input_bytes: number;
    live_result_bytes: number;
    external_backup_dependencies: string[];
    dependency_availability: "NOT_CHECKED";
    store_capacity_remaining: "NOT_DISCLOSED";
  } | null;
}

interface JobReview {
  record: CollectionJob;
  events: Array<{ record: CollectionJob; actor: AuditEvent["actor"] }>;
  archive?: {
    archived_at: string;
    plan_fingerprint: string;
    plan: {backup_sha256: string; result_size_bytes: number};
  } | null;
  result: {
    collections: Array<{
      collector_name: string; status: string; evidence: EvidenceRecord[];
      warnings: Array<{code: string; message: string}>;
      rejected_records: Array<{code: string; message: string}>;
    }>;
    assembly: {
      assembly_id: string; warning_disposition: string;
      bundle: {candidate_commit: string; generated_at: string; producer: string; evidence: EvidenceRecord[]};
      collections: Array<{collector_name: string; collector_version: string; warnings: Array<{code: string; message: string}>}>;
    } | null;
  } | null;
}

interface Principal {
  session_id: string;
  identity_id: string;
  display_name: string;
  role: Role;
  project_ids: string[];
  trust_store_id: string;
  authenticated_at: string;
  expires_at: string;
}

interface DashboardSession {
  status: "AUTHENTICATED";
  principal: Principal;
  csrf_token: string;
}

interface ActivationStart {
  activation_code: string;
  expires_at: string;
  poll_after_seconds: number;
}

interface ActivationStatus {
  status: "PENDING" | "CHALLENGE_ISSUED" | "AUTHENTICATED";
  expires_at: string;
  principal: Principal | null;
  csrf_token: string | null;
}

interface RegisteredProject {
  project_id: string;
  profile_version: number;
  config_fingerprint: string;
  registered_at: string;
  config: {
    project: { id: string; name: string; repository: string; default_branch: string };
    release_tracks: Record<string, { policy: string }>;
  };
}

interface ProjectPage {
  projects: RegisteredProject[];
  next_after_project_id: string | null;
  has_more: boolean;
}

interface Candidate {
  candidate_id: string;
  project_id: string;
  version: string;
  commit_sha: string;
  source_branch: string;
  release_track: string;
  status: string;
  revision: number;
  created_at: string;
  updated_at: string;
  evaluated_at: string | null;
  evaluation_id: string | null;
  project_profile_id: string | null;
  project_profile_version: number | null;
}

interface CandidatePage {
  candidates: Candidate[];
  next_after_candidate_id: string | null;
  has_more: boolean;
}

interface AuditEvent {
  event_id: string;
  sequence: number;
  event_type: string;
  occurred_at: string;
  project_id: string;
  candidate_id: string | null;
  subject_fingerprint: string;
  subject_id: string;
  subject_schema_version: string;
  actor: { display_name: string; identity_id: string; role: Role } | null;
}

interface AuditPage {
  events: AuditEvent[];
  next_after_sequence: number | null;
  has_more: boolean;
}

interface Overview {
  forgegate_version: string;
  api_version: string;
  database_schema_version: number;
  deployment: string;
  hardware_access: string;
  limitations: string[];
  principal: Principal;
}

interface LiveSourceStatus {
  source_id: string;
  source_type: string;
  display_name: string;
  data_origin?: "LIVE_TELEMETRY" | "SIMULATED";
  access_mode: "READ_ONLY";
  connection: "CONNECTING" | "CONNECTED" | "DISCONNECTED" | "ERROR";
  heartbeat: "NOT_OBSERVED" | "NORMAL" | "STALE" | "INVALID";
  device_health: "UNKNOWN" | "NORMAL" | "WARNING" | "FAULT";
  detail_code: string;
  detail_message: string;
  endpoint: string;
  protocol: string;
  baud_rate: number;
  expected_interval_seconds: number;
  stale_after_seconds: number;
  observed_at: string;
  last_heartbeat_at: string | null;
  heartbeat_age_seconds: number | null;
  sequence: number | null;
  uptime_ms: number | null;
  device_state: string | null;
  fault_flags: string | null;
  reported_issues: Array<{ code: string; label: string; mask: string }>;
  frames_received: number;
  protocol_errors: number;
  sequence_gaps: number;
  reconnects: number;
  evidence_boundary: "LIVE_STATUS_ONLY_NOT_RELEASE_EVIDENCE";
  hardware_control: "NOT_PERFORMED";
}

interface MonitorControlView {
  schema_version: "forgegate.monitor-control.v1";
  project_id: string;
  presets: Array<{
    preset_id: string;
    name: string;
    adapter: "msp430.uart.v1" | "forgegate.simulated-demo.v1";
    port: string | null;
    stale_after_seconds: number;
  }>;
  session: {
    state: "STOPPED" | "RUNNING" | "STOPPING" | "ERROR";
    revision: number;
    run_id: string | null;
    active_preset_id: string | null;
    detail_code: string;
    detail_message: string;
  };
}

interface MonitorControls {
  element: HTMLElement;
  configured: () => boolean | undefined;
  refresh: (manual?: boolean) => Promise<void>;
}

interface CandidateTransition {
  transition_id: string;
  from_status: string;
  to_status: string;
  to_revision: number;
  occurred_at: string;
  reason: string | null;
}

interface ArtifactReference {
  path_or_uri: string;
  media_type: string;
  sha256: string;
  size_bytes: number;
}

interface EvidenceRecord {
  evidence_id: string;
  kind: string;
  scope: string;
  value: unknown;
  unit: string | null;
  status: string;
  source_tool: string;
  source_version: string;
  artifact: ArtifactReference;
  collected_at: string;
  trust: string;
  verification_level: string;
}

interface EvidenceBinding {
  binding_id: string;
  bound_at: string;
  candidate_fingerprint: string;
  assembly_fingerprint: string;
  assembly: {
    assembly_id: string;
    warning_disposition: string;
    bundle: { generated_at: string; producer: string; evidence: EvidenceRecord[] };
    collections: Array<{ collector_name: string; collector_version: string; source: ArtifactReference; artifacts: ArtifactReference[]; warnings: Array<{ code: string; message: string }> }>;
  };
}

interface DashboardJobEvidenceBindingResult {
  schema_version: "forgegate.dashboard-job-evidence-binding.v1";
  job_id: string;
  result_fingerprint: string;
  assembly_id: string;
  assembly_fingerprint: string;
  binding: EvidenceBinding;
  candidate_transition: "NOT_PERFORMED";
  policy_decision: "NOT_PERFORMED";
  source_artifact_bytes: "not_embedded";
}

interface PolicyMaterial {
  material_id: string;
  project_profile_id: string;
  project_profile_version: number;
  release_track: string;
  artifact: ArtifactReference;
  policy_fingerprint: string;
  policy: { name: string; rules: Array<{ id: string }> };
}

interface RuleEvaluation {
  rule_id: string;
  claim: string;
  decision: string;
  mandatory: boolean;
  expected: unknown;
  actual: unknown;
  evidence_ids: string[];
  reason_code: string;
  explanation: string;
  remediation_hint: string | null;
}

interface PolicyEvaluation {
  evaluation_id: string;
  policy_name: string;
  policy_fingerprint: string;
  evidence_fingerprint: string;
  candidate_commit: string;
  evaluated_at: string;
  decision: string;
  rule_results: RuleEvaluation[];
  evaluated_evidence_ids: string[];
  policy_material_id?: string;
  project_profile_id?: string;
  project_profile_version?: number;
}

interface ReleaseAttestation {
  attestation_id: string;
  generator_version: string;
  assurance: "unsigned_local";
  issued_at: string;
  transition_chain_fingerprint: string;
}

interface CandidateAssuranceReview {
  schema_version: "forgegate.dashboard-candidate-assurance-review.v1";
  candidate: Candidate;
  transitions: CandidateTransition[];
  evidence_binding_required: boolean;
  evidence_binding: EvidenceBinding | null;
  policy_material_required: boolean;
  policy_material: PolicyMaterial | null;
  policy_evaluation: PolicyEvaluation | null;
  attestation: ReleaseAttestation | null;
  assurance_bundle_id: string | null;
  assurance: "unsigned_local" | null;
  verification_scope: "retained_documents_and_embedded_policy_bytes" | null;
  source_artifact_bytes: "not_embedded" | null;
  limitations: string[];
}

type ReviewDetail = readonly [label: string, value: string, mono?: boolean];

interface ReviewedMutation {
  serializedBody?: string;
  title: string;
  eyebrow: string;
  summary: string;
  confirmLabel: string;
  endpoint: string;
  body: Record<string, unknown>;
  idempotencyPrefix: string | null;
  details: ReviewDetail[];
  completed: (response: unknown) => string;
}

interface LiveStatusPage {
  schema_version: "forgegate.live-status.v1";
  observed_at: string;
  refresh_after_seconds: number;
  sources: LiveSourceStatus[];
}

interface ApiProblem {
  error?: { code?: string; message?: string; request_id?: string };
}

interface LocalDownload {
  blob: Blob;
  filename: string;
}

interface AssemblyDownload extends LocalDownload {
  fingerprint: string;
}

class RequestProblem extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId: string,
    readonly retryAfterSeconds: number | null,
    readonly origin: "http" | "browser" = "http"
  ) {
    super(message);
  }
}

const mount = document.querySelector<HTMLDivElement>("#app");
if (mount === null) throw new Error("Dashboard mount point is missing");
const root: HTMLDivElement = mount;

let session: DashboardSession | null = null;
let currentRoute: Route = routeFromHash();
let projects: RegisteredProject[] = [];
let selectedProjectId: string | null = null;
let candidateCursor: string | null = null;
let candidateCursorHistory: Array<string | null> = [];
let activationTimer: number | null = null;
let activationGeneration = 0;
let sessionExpiryTimer: number | null = null;
let liveStatusTimer: number | null = null;
let liveStatusGeneration = 0;
let lastLiveAnnouncement = "";
let auditViewGeneration = 0;
let jobsViewGeneration = 0;
let recoveryViewGeneration = 0;
let overviewViewGeneration = 0;
let candidatesViewGeneration = 0;
let projectListTruncated = false;
let candidateSearch = "";
let candidateStatusFilter = "ALL";

const MAX_DASHBOARD_IMPORT_BYTES = 3_900_000;
const MAX_RECOVERY_REPORT_BYTES = 262_144;

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className !== undefined) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(text: string, className = "button secondary"): HTMLButtonElement {
  const node = el("button", className, text);
  node.type = "button";
  return node;
}

function resetCandidatePagination(): void {
  candidateCursor = null;
  candidateCursorHistory = [];
}

function keepFocusInsideDialog(dialog: HTMLDialogElement, event: KeyboardEvent): void {
  if (event.key !== "Tab") return;
  const focusable = Array.from(
    dialog.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
  );
  const first = focusable[0];
  const last = focusable.at(-1);
  if (first === undefined || last === undefined) return;
  const active = document.activeElement;
  if (event.shiftKey && (active === first || !dialog.contains(active))) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (active === last || !dialog.contains(active))) {
    event.preventDefault();
    first.focus();
  }
}

function routeFromHash(): Route {
  const candidate = window.location.hash.replace(/^#\/?/, "").split("?", 1)[0];
  return candidate === "devices" || candidate === "projects" || candidate === "candidates" ||
    candidate === "evidence" || candidate === "decision" || candidate === "assurance" || candidate === "audit" || candidate === "jobs" || candidate === "recovery"
    ? candidate
    : "overview";
}

function candidateIdFromHash(): string | null {
  const query = window.location.hash.split("?", 2)[1];
  if (query === undefined) return null;
  const value = new URLSearchParams(query).get("candidate_id");
  return value !== null && /^cand-[0-9a-f]{24}$/.test(value) ? value : null;
}

function candidateReviewHash(route: "evidence" | "decision" | "assurance", candidateId: string): string {
  return `#/${route}?${new URLSearchParams({ candidate_id: candidateId }).toString()}`;
}

function requestId(): string {
  return `dashboard-${crypto.randomUUID()}`;
}

function retryAfterSeconds(response: Response): number | null {
  const value = response.headers.get("Retry-After");
  if (value === null || !/^\d+$/.test(value)) return null;
  const seconds = Number(value);
  return Number.isSafeInteger(seconds) && seconds > 0 ? seconds : null;
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("X-Request-ID", requestId());
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    cache: "no-store",
    headers
  });
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw requestProblem(response, payload);
  }
  return payload as T;
}

function requestProblem(response: Response, payload: unknown): RequestProblem {
  const problem = payload as ApiProblem;
  return new RequestProblem(
    response.status,
    problem.error?.code ?? "DASHBOARD_REQUEST_FAILED",
    problem.error?.message ?? "The local service rejected the request.",
    problem.error?.request_id ?? response.headers.get("X-Request-ID") ?? "unavailable",
    retryAfterSeconds(response)
  );
}

async function downloadAssuranceArchive(
  candidateId: string,
  revision: number,
  bundleId: string
): Promise<LocalDownload> {
  if (session === null) throw new Error("Dashboard session is unavailable");
  const response = await fetch(
    `/app/api/candidates/${encodeURIComponent(candidateId)}/assurance-export`,
    {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Accept": "application/zip",
        "Content-Type": "application/json",
        "X-ForgeGate-CSRF": session.csrf_token,
        "X-Request-ID": requestId()
      },
      body: JSON.stringify({ expected_revision: revision, expected_bundle_id: bundleId })
    }
  );
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => ({}));
    throw requestProblem(response, payload);
  }
  const returnedBundleId = response.headers.get("X-ForgeGate-Assurance-Bundle");
  const mediaType = response.headers.get("Content-Type")?.split(";", 1)[0];
  if (returnedBundleId !== bundleId || mediaType !== "application/zip") {
    throw new RequestProblem(
      500,
      "DASHBOARD_EXPORT_RESPONSE_INVALID",
      "The local service returned an unexpected assurance archive identity or media type.",
      response.headers.get("X-Request-ID") ?? "unavailable",
      null
    );
  }
  const blob = await response.blob();
  if (blob.size === 0 || blob.size > 16_924_672) {
    throw new RequestProblem(
      500,
      "DASHBOARD_EXPORT_RESPONSE_INVALID",
      "The local service returned an empty or oversized assurance archive.",
      response.headers.get("X-Request-ID") ?? "unavailable",
      null
    );
  }
  return {
    blob,
    filename: `assurance-${bundleId.replace(/^sha256:/, "")}.zip`
  };
}

async function downloadJobAssembly(
  job: CollectionJob,
  assemblyId: string
): Promise<AssemblyDownload> {
  if (session === null || job.result_fingerprint === null) throw new Error("Dashboard job result is unavailable");
  const mediaType = "application/vnd.forgegate.evidence-bundle-assembly+json";
  const response = await fetch(
    `/app/api/jobs/${encodeURIComponent(job.job_id)}/assembly-export?${new URLSearchParams({project_id: job.project_id})}`,
    {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Accept": mediaType,
        "Content-Type": "application/json",
        "X-ForgeGate-CSRF": session.csrf_token,
        "X-Request-ID": requestId()
      },
      body: JSON.stringify({
        expected_job_revision: job.revision,
        expected_result_fingerprint: job.result_fingerprint,
        expected_assembly_id: assemblyId
      })
    }
  );
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => ({}));
    throw requestProblem(response, payload);
  }
  if (
    response.headers.get("Content-Type")?.split(";", 1)[0] !== mediaType
    || response.headers.get("X-ForgeGate-Job-Result") !== job.result_fingerprint
    || response.headers.get("X-ForgeGate-Assembly") !== assemblyId
  ) {
    throw new RequestProblem(500, "DASHBOARD_EXPORT_RESPONSE_INVALID", "The local service returned an unexpected job-result or assembly identity.", response.headers.get("X-Request-ID") ?? "unavailable", null);
  }
  const assemblyFingerprint = response.headers.get("X-ForgeGate-Assembly-Fingerprint");
  if (assemblyFingerprint === null || !/^sha256:[0-9a-f]{64}$/.test(assemblyFingerprint)) {
    throw new RequestProblem(500, "DASHBOARD_EXPORT_RESPONSE_INVALID", "The local service omitted the canonical assembly fingerprint.", response.headers.get("X-Request-ID") ?? "unavailable", null);
  }
  const contentLength = response.headers.get("Content-Length");
  if (contentLength !== null && (!/^\d+$/.test(contentLength) || Number(contentLength) > 33_554_432)) {
    throw new RequestProblem(500, "DASHBOARD_EXPORT_RESPONSE_INVALID", "The local service returned an oversized assembly export.", response.headers.get("X-Request-ID") ?? "unavailable", null);
  }
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength === 0 || bytes.byteLength > 33_554_432 || `sha256:${await sha256Hex(bytes)}` !== assemblyFingerprint) {
    throw new RequestProblem(500, "DASHBOARD_EXPORT_RESPONSE_INVALID", "The downloaded assembly bytes do not match the reviewed fingerprint.", response.headers.get("X-Request-ID") ?? "unavailable", null);
  }
  return {
    blob: new Blob([bytes], {type: mediaType}),
    filename: `evidence-assembly-${assemblyId.replace(/^sha256:/, "")}.json`,
    fingerprint: assemblyFingerprint
  };
}

function saveLocalDownload(download: LocalDownload): void {
  const url = URL.createObjectURL(download.blob);
  const link = el("a");
  link.href = url;
  link.download = download.filename;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function clearActivationTimer(): void {
  if (activationTimer !== null) window.clearTimeout(activationTimer);
  activationTimer = null;
  activationGeneration += 1;
}

function clearSessionExpiryTimer(): void {
  if (sessionExpiryTimer !== null) window.clearTimeout(sessionExpiryTimer);
  sessionExpiryTimer = null;
}

function clearLiveStatusTimer(): void {
  if (liveStatusTimer !== null) window.clearTimeout(liveStatusTimer);
  liveStatusTimer = null;
  liveStatusGeneration += 1;
  lastLiveAnnouncement = "";
}

function scheduleSessionExpiry(): void {
  clearSessionExpiryTimer();
  if (session === null) return;
  const expiresAt = new Date(session.principal.expires_at).valueOf();
  const delay = expiresAt - Date.now();
  if (!Number.isFinite(expiresAt) || delay <= 0) {
    renderActivation("Your Dashboard session expired. Start a new local activation to continue.");
    return;
  }
  sessionExpiryTimer = window.setTimeout(() => {
    renderActivation("Your Dashboard session expired. Start a new local activation to continue.");
  }, delay);
}

function problemRecovery(problem: RequestProblem | null, fallback: string): string {
  if (problem?.origin === "browser") return fallback;
  if (problem?.status === 409) {
    return "Reload authoritative state, review the changed values, and submit a new request. This operation will not be retried automatically.";
  }
  if (problem?.status === 413) {
    return "Reduce the request below the stated 4 MiB service limit, then review it before trying again.";
  }
  if (problem?.status === 429) {
    return problem.retryAfterSeconds === null
      ? "Wait for the local rate window to reset before retrying manually."
      : `Wait ${problem.retryAfterSeconds} seconds for the local rate window to reset before retrying manually.`;
  }
  if (problem?.status === 500) {
    return "Do not assume the write failed. Record the request ID, inspect local logs and authoritative state, then retry only after the cause is understood.";
  }
  return fallback;
}

function showProblem(container: HTMLElement, error: unknown, recovery: string): void {
  const problem = error instanceof RequestProblem ? error : null;
  const browserValidation = problem?.origin === "browser";
  const panel = el("section", "problem-panel");
  panel.setAttribute("role", "alert");
  panel.setAttribute("aria-live", "assertive");
  panel.tabIndex = -1;
  panel.append(
    el("p", "problem-code", `ERROR [${problem?.code ?? "DASHBOARD_UNEXPECTED_ERROR"}]`),
    el("h2", undefined, browserValidation ? "Browser validation stopped this action" : "The request did not complete"),
    el("p", "problem-status", browserValidation ? "Browser validation — not an HTTP response" : `HTTP status: ${problem?.status ?? "unavailable"}`),
    el("p", undefined, problem?.message ?? "An unexpected browser-side error occurred."),
    el("p", "recovery", `Safe next step: ${problemRecovery(problem, recovery)}`),
    el("p", "request-id", browserValidation ? "Request ID: not issued by browser validation" : `Request ID: ${problem?.requestId ?? "not available"}`)
  );
  container.replaceChildren(panel);
  panel.focus();
}

function holdRateLimitedAction(
  dialog: HTMLDialogElement,
  action: HTMLButtonElement,
  problem: RequestProblem
): boolean {
  if (problem.status !== 429 || problem.retryAfterSeconds === null) return false;
  let remaining = problem.retryAfterSeconds;
  const originalLabel = action.textContent ?? "Confirm creation";
  action.disabled = true;
  action.textContent = `Retry in ${remaining}s`;
  const interval = window.setInterval(() => {
    remaining -= 1;
    if (remaining > 0) {
      action.textContent = `Retry in ${remaining}s`;
      return;
    }
    window.clearInterval(interval);
    action.textContent = originalLabel;
    action.disabled = false;
  }, 1000);
  dialog.addEventListener("close", () => window.clearInterval(interval), { once: true });
  return true;
}

function statusBadge(value: string): HTMLSpanElement {
  const normalized = value.toLowerCase();
  const tone = ["fail", "error", "denied", "disconnected", "stale", "invalid", "fault"].some(
    (item) => normalized.includes(item)
  )
    ? "negative"
    : ["warning", "connecting", "not observed"].some((item) => normalized.includes(item))
      ? "warning"
      : ["pass", "ready", "complete", "authenticated", "connected", "normal"].some((item) =>
          normalized.includes(item)
        )
        ? "positive"
        : "neutral";
  return el("span", `badge ${tone}`, value);
}

function definition(label: string, value: string, mono = false): HTMLDivElement {
  const item = el("div", "definition");
  item.append(el("dt", undefined, label), el("dd", mono ? "mono" : undefined, value));
  return item;
}

function shell(content: HTMLElement): void {
  if (session === null) {
    root.replaceChildren(content);
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    return;
  }

  const frame = el("div", "app-frame");
  const header = el("header", "topbar");
  const brand = el("div", "brand");
  const mark = el("span", "brand-mark", "FG");
  mark.setAttribute("aria-hidden", "true");
  const brandText = el("div");
  brandText.append(el("strong", undefined, "ForgeGate"), el("span", undefined, "Local assurance"));
  brand.append(mark, brandText);

  const identity = el("div", "identity-summary");
  identity.append(
    statusBadge(session.principal.role),
    el("span", undefined, session.principal.display_name),
    el("span", "session-expiry", `expires ${formatDate(session.principal.expires_at)}`)
  );
  const logout = button("End session", "button quiet");
  logout.addEventListener("click", () => void logoutSession());
  header.append(brand, identity, logout);

  const body = el("div", "app-body");
  const nav = el("nav", "side-nav");
  nav.setAttribute("aria-label", "Primary");
  const reviewCandidateId = candidateIdFromHash();
  for (const [group, routes] of [
    ["WORKSPACE", [["overview", "Overview", "Start and continue work"], ["candidates", "Candidates", "Assess reports and review releases"], ["projects", "Projects", "Profiles and policy authority"]]],
    ["REVIEW", [["evidence", "Evidence", "Bound records and sources"], ["decision", "Decision", "Rules and explanations"], ["assurance", "Assurance", "Verify and hand off"]]],
    ["OPERATIONS", [["jobs", "Jobs", "Collection lifecycle"], ["devices", "Devices", "Live read-only status"], ["audit", "Audit", "Project history and actors"], ["recovery", "Recovery", "Offline readiness handoff"]]]
  ] as const) {
    const section = el("section", "nav-group");
    section.append(el("p", "nav-group-label", group));
    for (const [route, label, detail] of routes) {
      const link = el("a", currentRoute === route ? "nav-link active" : "nav-link");
      link.href = reviewCandidateId !== null && ["evidence", "decision", "assurance"].includes(route)
        ? candidateReviewHash(route as "evidence" | "decision" | "assurance", reviewCandidateId)
        : `#/${route}`;
      if (currentRoute === route) link.setAttribute("aria-current", "page");
      link.append(el("strong", undefined, label), el("span", undefined, detail));
      section.append(link);
    }
    nav.append(section);
  }

  content.id = "workspace";
  content.tabIndex = -1;
  body.append(nav, content);
  frame.append(header, body);
  root.replaceChildren(frame);
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
}

function page(title: string, eyebrow: string, description: string): HTMLElement {
  const main = el("main", "workspace");
  const heading = el("header", "page-heading");
  heading.append(el("p", "eyebrow", eyebrow), el("h1", undefined, title), el("p", undefined, description));
  main.append(heading);
  return main;
}

function loadingPage(title: string): void {
  const main = page(title, "LOCAL CONTROL PLANE", "Loading authoritative data from ForgeGate…");
  const loading = el("div", "loading-panel");
  loading.setAttribute("role", "status");
  loading.append(el("span", "spinner"), el("span", undefined, "Loading"));
  main.append(loading);
  shell(main);
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString();
}

function shortHash(value: string): string {
  return value.length > 18 ? `${value.slice(0, 10)}…${value.slice(-7)}` : value;
}

async function loadSession(): Promise<void> {
  try {
    session = await api<DashboardSession>("/app/api/session");
    scheduleSessionExpiry();
    await renderRoute();
  } catch (error) {
    if (error instanceof RequestProblem && error.status === 401) {
      renderActivation();
      return;
    }
    const main = page("Dashboard unavailable", "LOCAL CONTROL PLANE", "The page could not confirm the local service state.");
    showProblem(main, error, "Verify that `forgegate dashboard` is running, then reload this page.");
    shell(main);
  }
}

function renderActivation(notice?: string): void {
  overviewViewGeneration += 1;
  candidatesViewGeneration += 1;
  jobsViewGeneration += 1;
  auditViewGeneration += 1;
  recoveryViewGeneration += 1;
  clearActivationTimer();
  clearSessionExpiryTimer();
  clearLiveStatusTimer();
  session = null;
  projects = [];
  projectListTruncated = false;
  selectedProjectId = null;
  candidateSearch = "";
  candidateStatusFilter = "ALL";
  resetCandidatePagination();
  const main = el("main", "activation-shell");
  main.id = "workspace";
  main.tabIndex = -1;
  const card = el("section", "activation-card");
  const brand = el("div", "activation-brand");
  brand.append(el("span", "brand-mark large", "FG"), el("span", "eyebrow", "FORGEGATE LOCAL"));
  card.append(
    brand,
    el("h1", undefined, "Release assurance without surrendering the key"),
    el(
      "p",
      "lede",
      "This browser starts unauthenticated. Approve a short-lived session from the ForgeGate CLI; your private key and API token never enter this page."
    )
  );
  if (notice !== undefined) {
    const status = el("p", "session-notice", notice);
    status.setAttribute("role", "status");
    card.append(status);
  }
  const boundary = el("div", "boundary-grid");
  for (const [label, value] of [
    ["Network", "Loopback only"],
    ["Credential", "CLI-held Ed25519 key"],
    ["Hardware", "CLI-configured, read-only"],
    ["Product status", "Windows Local Alpha"]
  ]) {
    const item = el("div", "boundary-item");
    item.append(el("span", undefined, label), el("strong", undefined, value));
    boundary.append(item);
  }
  const actions = el("div", "activation-actions");
  const start = button("Start local activation", "button primary");
  start.addEventListener("click", () => void startActivation(card));
  const cli = el("p", "muted", "The CLI will select the exact identity, role, and project scopes.");
  actions.append(start, cli);
  card.append(boundary, actions);

  const aside = el("aside", "assurance-note");
  aside.append(
    el("p", "eyebrow", "EVIDENCE BOUNDARY"),
    el("h2", undefined, "What this page does not prove"),
    el("p", undefined, "A successful session does not authenticate imported evidence, verify hardware, publish a release, or approve remote deployment."),
    el("p", "mono subtle", "browser_hardware_control = NOT_PERFORMED")
  );
  main.append(card, aside);
  shell(main);
}

async function startActivation(card: HTMLElement): Promise<void> {
  clearActivationTimer();
  const generation = activationGeneration;
  const actions = card.querySelector<HTMLElement>(".activation-actions");
  if (actions === null) return;
  actions.replaceChildren(el("p", "muted", "Creating a one-time browser-bound request…"));
  try {
    const activation = await api<ActivationStart>("/app/api/activations", {
      method: "POST",
      body: "{}"
    });
    if (generation !== activationGeneration) return;
    const notice = card.querySelector<HTMLElement>(".session-notice");
    if (notice !== null) notice.textContent = "A new one-time activation is pending. Use the code shown below.";
    const panel = el("section", "activation-code-panel");
    panel.setAttribute("aria-live", "polite");
    panel.append(
      el("p", "eyebrow", "ONE-TIME CODE"),
      el("p", "activation-code", activation.activation_code),
      el("p", undefined, `Expires ${formatDate(activation.expires_at)}. In a separate terminal run:`)
    );
    const command = el(
      "code",
      "command",
      `forgegate dashboard-activate ${activation.activation_code} --server ${window.location.origin} --identity IDENTITY.json --private-key KEY.pem --role ROLE --project PROJECT_ID`
    );
    panel.append(
      command,
      el("p", "muted", "Run from your ForgeGate environment. Replace IDENTITY.json and KEY.pem with your local files, ROLE with producer or operator, and PROJECT_ID with an authorized project. Keep --server exactly as shown; never paste a private key into this page.")
    );
    actions.replaceChildren(panel);
    pollActivation(Math.max(activation.poll_after_seconds, 1));
  } catch (error) {
    if (generation !== activationGeneration) return;
    showProblem(actions, error, "Retry activation. If it repeats, restart the local Dashboard service.");
    addActivationRetry(actions, () => void startActivation(card), error);
  }
}

function addActivationRetry(container: HTMLElement, retry: () => void, error: unknown): void {
  const action = button("Retry local activation", "button primary");
  action.addEventListener("click", retry);
  container.append(action);
  if (error instanceof RequestProblem && error.status === 429 && error.retryAfterSeconds !== null) {
    action.disabled = true;
    action.textContent = `Retry after ${error.retryAfterSeconds}s`;
    // Do not automatically send a new request when the rate window ends.
    const generation = activationGeneration;
    activationTimer = window.setTimeout(() => {
      if (generation !== activationGeneration) return;
      action.disabled = false;
      action.textContent = "Retry local activation";
    }, Math.min(error.retryAfterSeconds * 1000, 2_147_483_647));
  }
}

function pollActivation(delaySeconds: number): void {
  const generation = activationGeneration;
  activationTimer = window.setTimeout(async () => {
    try {
      const state = await api<ActivationStatus>("/app/api/activation");
      if (generation !== activationGeneration) return;
      if (state.status === "AUTHENTICATED" && state.principal !== null && state.csrf_token !== null) {
        clearActivationTimer();
        session = { status: "AUTHENTICATED", principal: state.principal, csrf_token: state.csrf_token };
        scheduleSessionExpiry();
        await renderRoute();
        return;
      }
      pollActivation(delaySeconds);
    } catch (error) {
      if (generation !== activationGeneration) return;
      clearActivationTimer();
      if (error instanceof RequestProblem && [401, 404, 410].includes(error.status)) {
        renderActivation("The one-time activation expired or is no longer available. Start a new activation and use its new code.");
        return;
      }
      const main = page("Activation interrupted", "LOCAL CONTROL PLANE", "The browser could not complete the local activation handshake.");
      showProblem(main, error, "Start a new activation request.");
      addActivationRetry(main, () => renderActivation(), error);
      shell(main);
    }
  }, delaySeconds * 1000);
}

async function logoutSession(): Promise<void> {
  if (session === null) return;
  try {
    await api<{ status: string }>("/app/api/session", {
      method: "DELETE",
      headers: { "X-ForgeGate-CSRF": session.csrf_token }
    });
  } catch {
    // Local protected state is cleared even if the server session already expired.
  }
  renderActivation("The Dashboard session ended. Start a new local activation when you are ready.");
}

async function renderRoute(): Promise<void> {
  overviewViewGeneration += 1;
  candidatesViewGeneration += 1;
  jobsViewGeneration += 1;
  auditViewGeneration += 1;
  recoveryViewGeneration += 1;
  if (session === null) {
    renderActivation();
    return;
  }
  clearLiveStatusTimer();
  currentRoute = routeFromHash();
  if (currentRoute === "overview") await renderOverview();
  if (currentRoute === "devices") await renderDevices();
  if (currentRoute === "projects") await renderProjects();
  if (currentRoute === "audit") await renderAudit();
  if (currentRoute === "jobs") await renderJobs();
  if (currentRoute === "recovery") await renderRecovery();
  if (currentRoute === "candidates") await renderCandidates();
  if (currentRoute === "evidence") await renderEvidence();
  if (currentRoute === "decision") await renderDecision();
  if (currentRoute === "assurance") await renderAssurance();
}

async function renderDevices(): Promise<void> {
  const owner = session;
  if (owner === null) return;
  clearLiveStatusTimer();
  const generation = liveStatusGeneration;
  const hash = window.location.hash;
  const main = page(
    "Live devices",
    "READ-ONLY OBSERVATION",
    "Connection, heartbeat freshness, and device-reported health are independent signals. No serial command is sent."
  );
  const toolbar = el("section", "toolbar live-toolbar");
  const refresh = button("Refresh now", "button secondary");
  const cadence = statusBadge("Live · every 1 s");
  toolbar.append(cadence, refresh);
  const announcement = el("p", "sr-only");
  announcement.setAttribute("aria-live", "polite");
  announcement.setAttribute("aria-atomic", "true");
  const content = el("section", "live-status-region");
  content.setAttribute("aria-label", "Live device status");
  content.setAttribute("aria-busy", "true");
  content.append(el("p", "muted", "Loading the current read-only device status…"));
  const current = (): boolean => session === owner && generation === liveStatusGeneration
    && currentRoute === "devices" && window.location.hash === hash && main.isConnected;
  const controls = createMonitorControls(owner, current);
  let refreshing = false;
  const refreshStatus = async (): Promise<void> => {
    if (!current() || refreshing) return;
    refreshing = true;
    refresh.disabled = true;
    if (liveStatusTimer !== null) window.clearTimeout(liveStatusTimer);
    liveStatusTimer = null;
    // Read both independent views together, then render sources with the known
    // configuration mode. The persistent controls retain focus across polling.
    const [status] = await Promise.allSettled([
      api<LiveStatusPage>("/app/api/live-status"), controls.refresh()
    ]);
    if (!current()) return;
    refreshing = false;
    refresh.disabled = false;
    let delay = 2000;
    if (status.status === "fulfilled") {
      const result = status.value;
      content.setAttribute("aria-busy", "false");
      content.replaceChildren(renderLiveStatus(result, controls.configured()));
      const signature = result.sources
        .map((source) => `${source.data_origin === "SIMULATED" ? "SIMULATED " : ""}${source.display_name}: ${source.connection}, heartbeat ${source.heartbeat}, device ${source.device_health}`)
        .join(". ");
      if (signature !== lastLiveAnnouncement) {
        announcement.textContent = signature || "No monitor is currently running.";
        lastLiveAnnouncement = signature;
      }
      delay = Math.max(1, result.refresh_after_seconds) * 1000;
    } else if (handleProtectedProblem(content, status.reason, "Refresh the current monitor status, then inspect its reported error.")) {
      return;
    }
    liveStatusTimer = window.setTimeout(() => void refreshStatus(), delay);
  };
  refresh.addEventListener("click", () => void refreshStatus());
  main.append(toolbar, controls.element, announcement, content);
  shell(main);
  await refreshStatus();
}

function createMonitorControls(owner: DashboardSession, current: () => boolean): MonitorControls {
  const element = el("section", "monitor-control-region");
  element.append(el("p", "muted", "Loading saved monitor presets…"));
  const panel = el("section", "panel monitor-control-panel");
  const origin = el("p", "eyebrow", "SAVED MONITOR PRESET");
  const state = el("p", "monitor-session-state", "Monitor session unavailable");
  state.setAttribute("aria-live", "polite");
  const detail = el("p", "muted");
  const active = el("p", "mono");
  const label = el("label", "field");
  label.htmlFor = "monitor-preset";
  const select = el("select");
  select.id = "monitor-preset";
  select.name = "monitor-preset";
  select.setAttribute("aria-describedby", "monitor-preset-description");
  label.append(el("span", undefined, "Saved preset"), select);
  const description = el("p", "monitor-preset-description");
  description.id = "monitor-preset-description";
  const start = button("Start monitoring", "button primary");
  const stop = button("Stop monitoring", "button secondary");
  const reload = button("Reload monitor session", "button quiet");
  const actions = el("div", "toolbar");
  const problem = el("div", "monitor-control-problem");
  const operator = owner.principal.role === "operator";
  if (operator) actions.append(start, stop);
  actions.append(reload);
  panel.append(origin, el("h2", undefined, "Monitor session"), state, detail, active, label, description,
    el("p", "command-boundary", "Stop monitoring ends only the monitor session. The Dashboard server stays running. Live status is not release evidence."), actions, problem);
  if (!operator) panel.append(el("p", "muted", "Read-only session. An operator must start or stop monitoring."));

  let view: MonitorControlView | null | undefined;
  let pending = false;
  let fresh = false;
  let requestGeneration = 0;
  let optionsSignature = "";
  let readProblemVisible = false;
  const mountPanel = (): void => {
    if (element.firstElementChild !== panel) element.replaceChildren(panel);
  };
  const update = (): void => {
    const selected = view?.presets.find(preset => preset.preset_id === select.value);
    const running = view?.session.run_id !== null && view?.session.run_id !== undefined;
    const activePreset = view?.presets.find(preset => preset.preset_id === view?.session.active_preset_id);
    const simulated = (running ? activePreset : selected)?.adapter === "forgegate.simulated-demo.v1";
    origin.textContent = simulated ? "SIMULATED DEMO — NO HARDWARE OBSERVATION" : "SAVED MONITOR PRESET";
    description.textContent = selected === undefined ? "No saved preset is available."
      : selected.adapter === "forgegate.simulated-demo.v1"
        ? "SIMULATED: six scripted connection, heartbeat and health states change every 5 seconds and repeat every 30 seconds. No serial port is opened; the demo provides no hardware evidence."
        : `Read-only MSP430 UART v1 · ${selected.port ?? "No port configured"} · stale after ${selected.stale_after_seconds} seconds. Starting the monitor does not establish a connection or validate measurements.`;
    select.disabled = !operator || pending || !fresh || running;
    start.disabled = !operator || pending || !fresh || selected === undefined || running;
    stop.disabled = !operator || pending || !fresh || !running;
    stop.textContent = view?.session.state === "STOPPING" ? "Retry stop monitoring" : "Stop monitoring";
    reload.disabled = pending;
    if (view !== null && view !== undefined) {
      const nextState = `Monitoring ${view.session.state} · revision ${view.session.revision}`;
      if (state.textContent !== nextState) state.textContent = nextState;
      detail.textContent = `${view.session.detail_code}: ${view.session.detail_message}`;
      active.textContent = `Project: ${view.project_id} · Active preset: ${activePreset?.name ?? "None"} · Run: ${view.session.run_id ?? "None"}`;
    }
    panel.setAttribute("aria-busy", String(pending));
  };
  const accept = (result: MonitorControlView | null): void => {
    view = result;
    fresh = true;
    if (result === null) {
      element.replaceChildren();
      return;
    }
    mountPanel();
    const signature = JSON.stringify(result.presets);
    if (signature !== optionsSignature) {
      const selected = select.value;
      select.replaceChildren(...result.presets.map(preset => {
        const option = el("option", undefined, `${preset.name}${preset.adapter === "forgegate.simulated-demo.v1" ? " · SIMULATED" : ""}`);
        option.value = preset.preset_id;
        return option;
      }));
      select.value = result.presets.some(preset => preset.preset_id === selected)
        ? selected : result.session.active_preset_id ?? result.presets[0]?.preset_id ?? "";
      optionsSignature = signature;
    }
    if (result.session.run_id !== null && result.session.active_preset_id !== null) select.value = result.session.active_preset_id;
    update();
  };
  const refresh = async (manual = false): Promise<void> => {
    if (!current() || pending) return;
    const request = ++requestGeneration;
    try {
      const result = await api<MonitorControlView | null>("/app/api/monitor-presets");
      if (!current() || request !== requestGeneration) return;
      accept(result);
      if (manual || readProblemVisible) problem.replaceChildren();
      readProblemVisible = false;
    } catch (error) {
      if (!current() || request !== requestGeneration) return;
      fresh = false;
      mountPanel();
      update();
      if (error instanceof RequestProblem && error.status === 401) {
        handleProtectedProblem(problem, error, "Start a new local activation.");
        return;
      }
      if (!readProblemVisible || manual) {
        if (handleProtectedProblem(problem, error, "Reload the monitor session before starting or stopping it.")) return;
        readProblemVisible = true;
      }
    }
  };
  const command = async (action: "start" | "stop"): Promise<void> => {
    if (!current() || !operator || pending || !fresh || view === null || view === undefined) return;
    if ((action === "start" && start.disabled) || (action === "stop" && stop.disabled)) return;
    const body = action === "start"
      ? {preset_id: select.value, expected_revision: view.session.revision}
      : {run_id: view.session.run_id};
    pending = true;
    const request = ++requestGeneration;
    problem.replaceChildren();
    readProblemVisible = false;
    update();
    try {
      const result = await api<MonitorControlView>(`/app/api/monitor-session/${action}`, {
        method: "POST", headers: {"X-ForgeGate-CSRF": owner.csrf_token}, body: JSON.stringify(body)
      });
      if (!current() || request !== requestGeneration) return;
      accept(result);
    } catch (error) {
      if (!current() || request !== requestGeneration) return;
      fresh = false;
      if (handleProtectedProblem(problem, error, "The monitor outcome is unconfirmed. Reload the monitor session before trying again; no connection is claimed.")) return;
    } finally {
      if (current() && request === requestGeneration) {
        pending = false;
        update();
      }
    }
  };
  select.addEventListener("change", () => { if (current()) update(); });
  start.addEventListener("click", () => void command("start"));
  stop.addEventListener("click", () => void command("stop"));
  reload.addEventListener("click", () => void refresh(true));
  update();
  return {element, configured: () => view === undefined ? undefined : view !== null, refresh};
}

function renderLiveStatus(result: LiveStatusPage, controlled: boolean | undefined): HTMLElement {
  const wrapper = el("div", "live-status-stack");
  if (result.sources.length === 0) {
    wrapper.append(
      emptyState(
        controlled === false ? "No live monitor configured" : "No monitor is currently running",
        controlled === false
          ? "Restart the Dashboard with --msp430-port COM4 to enable the optional read-only MSP430 UART v1 monitor."
          : controlled === true
            ? "Select a saved preset above and start monitoring with an operator session."
            : "Reload the monitor session to check which monitoring options are available."
      )
    );
    return wrapper;
  }
  for (const source of result.sources) wrapper.append(renderLiveSource(source));
  wrapper.append(el("p", "live-sampled-at muted", `Status sampled ${formatDate(result.observed_at)}`));
  return wrapper;
}

function renderLiveSource(source: LiveSourceStatus): HTMLElement {
  const simulated = source.data_origin === "SIMULATED";
  const sourcePanel = el("article", "live-source-panel");
  const heading = el("div", "card-heading");
  const title = el("div");
  title.append(el("p", "eyebrow", simulated ? "SIMULATED SOURCE — NO HARDWARE OBSERVATION" : "LIVE SOURCE"),
    el("h2", undefined, `${simulated ? "SIMULATED · " : ""}${source.display_name}`));
  heading.append(title, statusBadge(source.access_mode));

  const stateGrid = el("section", "device-state-grid");
  stateGrid.setAttribute("aria-label", `${source.display_name} current states`);
  stateGrid.append(
    liveStateCard("Connection", source.connection, simulated ? "Scripted connection state; no serial endpoint is opened." : connectionDescription(source.connection)),
    liveStateCard("Heartbeat", source.heartbeat, simulated ? "Scripted heartbeat freshness; no device frame was observed." : heartbeatDescription(source)),
    liveStateCard("Device health", source.device_health, simulated ? "Scripted health state; this is not a firmware report or hardware diagnosis." : healthDescription(source))
  );

  const detail = el("section", "live-detail-banner");
  detail.append(statusBadge(source.detail_code), el("p", undefined, source.detail_message));

  const columns = el("div", "content-columns");
  const telemetry = el("section", "panel");
  telemetry.append(el("p", "eyebrow", simulated ? "SIMULATED VALUES" : "LATEST VALID TEL FRAME"), el("h3", undefined, "Telemetry position"));
  const telemetryValues = el("dl", "definition-list");
  telemetryValues.append(
    definition("Sequence", nullableNumber(source.sequence)),
    definition("Device uptime", source.uptime_ms === null ? "Not observed" : formatDuration(source.uptime_ms)),
    definition("Reported state", source.device_state ?? "Not observed"),
    definition("Fault flags", source.fault_flags ?? "Not observed", true),
    definition("Last heartbeat", source.last_heartbeat_at === null ? "Not observed" : formatDate(source.last_heartbeat_at)),
    definition("Heartbeat age", source.heartbeat_age_seconds === null ? "Not observed" : `${source.heartbeat_age_seconds.toFixed(3)} s`)
  );
  telemetry.append(telemetryValues);
  if (source.reported_issues.length > 0) {
    const issues = el("section", "reported-issues");
    issues.append(el("h4", undefined, simulated ? "Simulated issue examples" : "Decoded firmware reports"));
    const list = el("ul", "issue-list");
    for (const issue of source.reported_issues) {
      const item = el("li");
      item.append(el("code", undefined, issue.mask), el("span", undefined, issue.label));
      list.append(item);
    }
    issues.append(list, el("p", "muted", simulated
      ? "Scripted examples only; no device report or hardware diagnosis is established."
      : "Decoded from the versioned MSP430 UART v1 adapter; these are device reports, not ForgeGate diagnoses."));
    telemetry.append(issues);
  }

  const monitor = el("section", "panel");
  monitor.append(el("p", "eyebrow", "MONITOR DIAGNOSTICS"), el("h3", undefined, simulated ? "Simulated source" : "Read-only transport"));
  const monitorValues = el("dl", "definition-list");
  monitorValues.append(
    definition("Endpoint", source.endpoint, true),
    definition("Protocol", source.protocol, true),
    definition("Baud", simulated ? "Not applicable (simulated)" : String(source.baud_rate)),
    definition("Stale after", `${source.stale_after_seconds.toFixed(1)} s`),
    definition("Valid frames", String(source.frames_received)),
    definition("Protocol errors", String(source.protocol_errors)),
    definition("Sequence gaps", String(source.sequence_gaps)),
    definition("Reconnects", String(source.reconnects))
  );
  monitor.append(monitorValues);
  columns.append(telemetry, monitor);

  const boundary = el("p", "live-boundary mono", `${source.evidence_boundary} · hardware_control=${source.hardware_control}`);
  sourcePanel.append(heading);
  if (simulated) sourcePanel.append(el("p", "live-simulation-notice", "SIMULATED: six demo states change every 5 seconds and repeat every 30 seconds. No serial port is opened, and no physical hardware or release evidence is produced."));
  sourcePanel.append(stateGrid, detail, columns, boundary);
  return sourcePanel;
}

function liveStateCard(label: string, value: string, description: string): HTMLElement {
  const card = el("article", "device-state-card");
  card.append(el("span", undefined, label), statusBadge(value.replaceAll("_", " ")), el("p", undefined, description));
  return card;
}

function connectionDescription(value: LiveSourceStatus["connection"]): string {
  if (value === "CONNECTED") return "The configured serial endpoint is open for input.";
  if (value === "CONNECTING") return "The monitor is attempting a read-only connection.";
  if (value === "DISCONNECTED") return "The configured endpoint is not currently available.";
  return "The endpoint could not be opened or read.";
}

function heartbeatDescription(source: LiveSourceStatus): string {
  if (source.heartbeat === "NORMAL") return "The latest valid TEL frame is inside the freshness window.";
  if (source.heartbeat === "STALE") return "A previous valid frame exists, but no current frame arrived in time.";
  if (source.heartbeat === "INVALID") return "The latest TEL frame failed framing, range, or CRC validation.";
  return "No valid TEL frame has been observed in this process.";
}

function healthDescription(source: LiveSourceStatus): string {
  if (source.device_health === "FAULT") return `The firmware reports FAULT${source.fault_flags === null ? "" : ` with flags ${source.fault_flags}`}.`;
  if (source.device_health === "WARNING") return "The firmware reports WARNING.";
  if (source.device_health === "NORMAL") return `The firmware reports ${source.device_state ?? "a normal operating state"}.`;
  return "No normal, warning, or fault state has been established.";
}

function nullableNumber(value: number | null): string {
  return value === null ? "Not observed" : String(value);
}

function formatDuration(milliseconds: number): string {
  const seconds = Math.floor(milliseconds / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return `${hours}h ${minutes}m ${remainder}s`;
}

async function renderOverview(): Promise<void> {
  const owner = session;
  const hash = window.location.hash;
  const generation = ++overviewViewGeneration;
  const current = (): boolean => owner !== null && session === owner && window.location.hash === hash && generation === overviewViewGeneration;
  loadingPage("Overview");
  const main = page("Your release workbench", "EVIDENCE → DECISION → HANDOFF", "Assess a report batch, investigate a result, or continue a release review.");
  const refresh = button("Refresh workspace", "button quiet");
  refresh.addEventListener("click", () => { if (current()) { projects = []; void renderOverview(); } });
  main.append(refresh);
  try {
    const overview = await api<Overview>("/app/api/overview");
    if (!current()) return;
    const visible = await ensureProjects();
    if (!current()) return;
    const operational = el("details", "panel workspace-details");
    operational.append(el("summary", undefined, `Local service connected · v${overview.forgegate_version} · Session and evidence boundaries`));
    const list = el("dl", "definition-list");
    list.append(
      definition("Service", `${overview.deployment} · API ${overview.api_version} · database schema v${overview.database_schema_version}`),
      definition("Role", overview.principal.role),
      definition("Project scopes", overview.principal.project_ids.join(", ")),
      definition("Identity", overview.principal.identity_id, true),
      definition("Trust store", overview.principal.trust_store_id, true),
      definition("Session expires", formatDate(overview.principal.expires_at)),
      definition("Hardware access", overview.hardware_access)
    );
    const items = el("ul", "limitation-list");
    for (const limitation of overview.limitations) items.append(el("li", undefined, limitation));
    operational.append(list, items);
    if (visible.length === 0) {
      main.append(emptyState("No registered projects in this session", "Register a project with the CLI, then refresh this workspace. Your activation must include its project scope."), operational);
      shell(main);
      return;
    }
    const project = visible.find(item => item.project_id === selectedProjectId) ?? visible[0]!;
    selectedProjectId = project.project_id;
    const toolbar = el("section", "toolbar workbench-toolbar");
    const label = el("label", "field compact-field");
    label.append(el("span", undefined, "Working project"));
    const selector = el("select");
    for (const item of visible) {
      const option = el("option", undefined, `${item.config.project.name} · ${item.project_id}`);
      option.value = item.project_id;
      option.selected = item.project_id === project.project_id;
      selector.append(option);
    }
    selector.addEventListener("change", () => {
      if (!current()) return;
      selectedProjectId = selector.value;
      resetCandidatePagination();
      void renderOverview();
    });
    label.append(selector);
    toolbar.append(label);
    main.append(toolbar);
    if (projectListTruncated) main.append(el("p", "muted", "Showing the first 100 authorized projects. Narrow your activation scope to reach an unlisted project."));
    const start = el("section", "workbench-start");
    const introduction = el("div");
    introduction.append(el("p", "eyebrow", "START AN ASSESSMENT"), el("h2", undefined, "Turn existing reports into a reviewable decision"), el("p", "muted", "Choose a version and commit, select your test and quality reports, then review the policy and confirm. Save the assurance bundle and original-report replay for your handoff."));
    const actions = el("div", "workbench-actions");
    if (owner!.principal.role === "operator") {
      const quick = button("Quick assessment", "button primary");
      quick.addEventListener("click", () => { if (current()) openCandidateDialog(main, quick, undefined, true); });
      actions.append(quick);
    } else {
      actions.append(el("p", "muted", "Read-only session. An operator can create and assess a candidate."));
    }
    const browse = el("a", "button secondary", "Browse candidates");
    browse.href = "#/candidates";
    browse.addEventListener("click", () => { resetCandidatePagination(); candidateSearch = ""; candidateStatusFilter = "ALL"; });
    actions.append(browse);
    start.append(introduction, actions);
    main.append(start);
    const work = el("section", "workbench-work");
    work.append(el("h2", undefined, "Continue a review"));
    main.append(work, operational);
    // Render useful navigation before the optional candidate read completes.
    shell(main);
    try {
      const result = await api<CandidatePage>(`/app/api/projects/${encodeURIComponent(project.project_id)}/candidates?limit=25`);
      if (!current()) return;
      work.append(el("p", "muted", `${result.candidates.length} candidates loaded for ${project.project_id}${result.has_more ? "; more are available in Candidates" : ""}. Counts apply to this loaded page, in candidate-ID order; they are not project-wide totals or recency rankings.`));
      const metrics = el("section", "metric-grid workbench-metrics");
      for (const [title, statuses] of [
        ["Loaded candidates", ["DRAFT", "COLLECTING", "READY", "EVALUATING", "PASS", "FAIL", "REVIEW", "ERROR"]],
        ["Needs investigation", ["FAIL", "REVIEW", "ERROR"]],
        ["In progress", ["DRAFT", "COLLECTING", "READY", "EVALUATING"]],
        ["Policy passed", ["PASS"]]
      ] as const) {
        const count = result.candidates.filter(item => (statuses as readonly string[]).includes(item.status)).length;
        const metric = el("article", "metric-card");
        metric.append(el("span", undefined, title), el("strong", undefined, String(count)));
        metrics.append(metric);
      }
      work.append(metrics);
      if (result.candidates.length === 0) {
        work.append(emptyState("Ready for the first assessment", owner!.principal.role === "operator"
          ? "Start Quick assessment above to create a candidate and review existing reports."
          : "An operator can create the first candidate and assess existing reports for this project."));
      } else {
        const cards = el("div", "workbench-candidates");
        if (result.candidates.length > 6) work.append(el("p", "muted", "Showing the first 6 candidates from this loaded page. Browse candidates for the complete list and filters."));
        for (const candidate of result.candidates.slice(0, 6)) {
          const card = el("article", "workbench-candidate");
          const heading = el("div", "card-heading");
          heading.append(el("h3", undefined, candidate.version), statusBadge(candidate.status));
          const next = candidateNextAction(candidate);
          const link = el("a", "button quiet", next.label);
          link.href = candidateReviewHash(next.route, candidate.candidate_id);
          card.append(heading, el("p", "muted", `${candidate.release_track} · updated ${formatDate(candidate.updated_at)}`), el("p", "mono", `${candidate.candidate_id} · ${shortHash(candidate.commit_sha)}`), el("p", undefined, next.description), link);
          cards.append(card);
        }
        work.append(cards);
      }
    } catch (error) {
      if (!current()) return;
      if (handleProtectedProblem(work, error, "Refresh the workspace to retry the selected project's candidates.")) return;
    }
  } catch (error) {
    if (!current()) return;
    if (handleProtectedProblem(main, error, "Reload the Overview page.")) return;
    main.append(refresh);
    shell(main);
  }
}

function candidateNextAction(candidate: Candidate): { route: "evidence" | "decision" | "assurance"; label: string; description: string } {
  if (["FAIL", "REVIEW", "ERROR"].includes(candidate.status)) return {route: "decision", label: "Investigate decision", description: "Inspect rule outcomes and the evidence behind this result."};
  if (candidate.status === "PASS") return {route: "assurance", label: "Review handoff", description: "Review attestation availability and verify the portable assurance bundle."};
  return {route: "evidence", label: "Continue review", description: "Check retained evidence and the next available reviewed action."};
}

async function ensureProjects(): Promise<RegisteredProject[]> {
  if (projects.length === 0) {
    const owner = session;
    const pageResult = await api<ProjectPage>("/app/api/projects?limit=100");
    if (owner === null || session !== owner) return [];
    projects = pageResult.projects;
    projectListTruncated = pageResult.has_more;
    if (selectedProjectId === null && projects[0] !== undefined) selectedProjectId = projects[0].project_id;
  }
  return projects;
}

async function renderProjects(): Promise<void> {
  loadingPage("Projects");
  const main = page("Authorized projects", "IMMUTABLE PROFILES", "Only projects in the active session scope are discoverable here.");
  try {
    const visible = await ensureProjects();
    if (visible.length === 0) {
      main.append(emptyState("No registered projects", "The active scopes contain no registered project profile."));
    } else {
      const grid = el("section", "card-grid");
      for (const project of visible) {
        const card = el("article", "project-card");
        const heading = el("div", "card-heading");
        heading.append(el("h2", undefined, project.config.project.name), statusBadge(`Profile v${project.profile_version}`));
        const details = el("dl", "definition-list compact");
        details.append(
          definition("Project ID", project.project_id, true),
          definition("Default branch", project.config.project.default_branch),
          definition("Registered", formatDate(project.registered_at)),
          definition("Fingerprint", shortHash(project.config_fingerprint), true)
        );
        const openCandidates = button("Open candidates", "button secondary");
        openCandidates.addEventListener("click", () => {
          selectedProjectId = project.project_id;
          resetCandidatePagination();
          window.location.hash = "#/candidates";
        });
        card.append(heading, details, openCandidates);
        grid.append(card);
      }
      main.append(grid);
    }
  } catch (error) {
    if (handleProtectedProblem(main, error, "Reload the authorized project list.")) return;
  }
  shell(main);
}

function auditHash(projectId: string, candidateId = "", afterSequence = 0): string {
  const query = new URLSearchParams({ project_id: projectId });
  if (candidateId !== "") query.set("candidate_id", candidateId);
  if (afterSequence > 0) query.set("after_sequence", String(afterSequence));
  return `#/audit?${query.toString()}`;
}

async function renderAudit(): Promise<void> {
  const generation = ++auditViewGeneration;
  const authority = session;
  const active = () => generation === auditViewGeneration && session === authority;
  const main = page("Project audit", "APPEND-ONLY HISTORY", "Trace retained project and candidate events without changing release state.");
  if (authority?.principal.role !== "operator") {
    main.append(emptyState("Operator session required", "Producer sessions cannot read audit events. No audit request was sent."));
    shell(main);
    return;
  }
  const scopes = authority.principal.project_ids;
  if (scopes.length === 0) {
    main.append(emptyState("No project scope", "Activate an operator session with an authorized project."));
    shell(main);
    return;
  }
  const query = new URLSearchParams(window.location.hash.split("?", 2)[1] ?? "");
  const projectId = query.get("project_id") ?? (scopes.includes(selectedProjectId ?? "") ? selectedProjectId! : scopes[0]!);
  const candidateId = query.get("candidate_id") ?? "";
  const cursorText = query.get("after_sequence") ?? "0";
  const cursor = Number(cursorText);
  if (!scopes.includes(projectId) || (candidateId !== "" && !/^cand-[0-9a-f]{24}$/.test(candidateId)) ||
      !/^\d+$/.test(cursorText) || !Number.isSafeInteger(cursor)) {
    main.append(emptyState("Invalid audit selection", "The project must be in your scope, the candidate ID must be complete, and the cursor must be a non-negative safe integer."));
    const reset = el("a", "button secondary", "Reset audit filters");
    reset.href = "#/audit";
    main.append(reset);
    shell(main);
    return;
  }
  const form = el("form", "toolbar audit-filters");
  const projectLabel = el("label", "field");
  projectLabel.append(el("span", undefined, "Audit project"));
  const selector = el("select");
  for (const scope of scopes) {
    const option = el("option", undefined, scope);
    option.value = scope;
    option.selected = scope === projectId;
    selector.append(option);
  }
  selector.value = projectId;
  projectLabel.append(selector);
  const candidateLabel = el("label", "field");
  candidateLabel.append(el("span", undefined, "Candidate ID (optional)"));
  const candidateInput = el("input");
  candidateInput.value = candidateId;
  candidateInput.placeholder = "All project events";
  candidateInput.pattern = "cand-[0-9a-f]{24}";
  candidateInput.maxLength = 29;
  candidateInput.title = "Use the complete cand- identifier followed by 24 lowercase hexadecimal characters.";
  candidateLabel.append(candidateInput);
  selector.addEventListener("change", () => { candidateInput.value = ""; });
  const apply = button("Apply audit filters", "button primary");
  apply.type = "submit";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (candidateInput.value !== "" && !/^cand-[0-9a-f]{24}$/.test(candidateInput.value)) {
      candidateInput.reportValidity();
      return;
    }
    const hash = auditHash(selector.value, candidateInput.value);
    if (window.location.hash === hash) void renderAudit();
    else window.location.hash = hash;
  });
  const refresh = button("Refresh audit page", "button secondary");
  refresh.addEventListener("click", () => void renderAudit());
  form.append(projectLabel, candidateLabel, apply, refresh);
  main.append(form, el("p", "command-boundary", "Successful retained operations only—not a complete security log. Missing actor metadata is not inferred. Sequence numbers are store-wide and may have gaps; timestamps are supplied values, not trusted time. No hardware or producer-authenticity claim is implied."));
  const results = el("section", "audit-results");
  results.setAttribute("aria-live", "polite");
  results.append(el("p", "muted", "Loading audit events…"));
  main.append(results);
  shell(main);
  try {
    const params = new URLSearchParams({ project_id: projectId, after_sequence: String(cursor), limit: "25" });
    if (candidateId !== "") params.set("candidate_id", candidateId);
    const result = await api<AuditPage>(`/app/api/audit-events?${params.toString()}`);
    if (!active()) return;
    results.replaceChildren();
    results.append(el("p", "pager-status", `${result.events.length} events shown after sequence ${cursor} · ${result.has_more ? "More events available" : "End of matching history"}. Refresh to check for newly appended events.`));
    if (result.events.length === 0) {
      results.append(emptyState("No matching audit events", "Clear the candidate filter, return to the first page, or check for newly appended history. This is not proof that an operation succeeded or failed."));
    }
    for (const event of result.events) {
      const item = el("details", "audit-event panel");
      const summary = el("summary", undefined, `#${event.sequence} · ${event.event_type} · ${formatDate(event.occurred_at)}`);
      const values = el("dl", "definition-list");
      values.append(
        definition("Event ID", event.event_id, true),
        definition("Project", event.project_id),
        definition("Candidate", event.candidate_id ?? "Project-level event", true),
        definition("Subject schema", event.subject_schema_version),
        definition("Subject ID", event.subject_id, true),
        definition("Subject fingerprint", event.subject_fingerprint, true),
        definition("Actor", event.actor?.display_name ?? "Not recorded — no authenticated identity is inferred"),
        definition("Actor role", event.actor?.role ?? "Not recorded"),
        definition("Actor identity", event.actor?.identity_id ?? "Not recorded", true)
      );
      item.append(summary, values);
      if (event.candidate_id !== null) {
        const review = el("a", "button quiet", "Review candidate evidence");
        review.href = candidateReviewHash("evidence", event.candidate_id);
        item.append(review);
      }
      results.append(item);
    }
    const pager = el("nav", "pager");
    pager.setAttribute("aria-label", "Audit pages");
    const first = el("a", "button quiet", "First audit page");
    first.href = auditHash(projectId, candidateId);
    pager.append(first);
    if (result.has_more && result.next_after_sequence !== null) {
      const next = el("a", "button secondary", "Next audit page");
      next.href = auditHash(projectId, candidateId, result.next_after_sequence);
      pager.append(next);
    }
    pager.append(el("p", "muted", "Browser Back restores the previous filter/cursor. No snapshot total is claimed."));
    results.append(pager);
  } catch (error) {
    if (!active()) return;
    handleProtectedProblem(results, error, "Check the project scope, then use Refresh audit page. No write was performed.");
  }
}

function validRecoveryHandoff(value: unknown, sourceHash: string): value is RecoveryHandoff {
  if (!isJsonObject(value) || value.schema_version !== "forgegate.recovery-readiness-handoff.v1") return false;
  const readiness = value.readiness;
  return typeof value.handoff_id === "string" && /^sha256:[0-9a-f]{64}$/.test(value.handoff_id) &&
    value.source_report_sha256 === sourceHash &&
    (value.disposition === "READY_FOR_REHEARSAL" || value.disposition === "BLOCKED") &&
    isJsonObject(readiness) && readiness.schema_version === "forgegate.workspace-recovery-readiness.v1" &&
    (readiness.status === "READY" || readiness.status === "INCOMPLETE") &&
    typeof readiness.backup_sha256 === "string" && /^[0-9a-f]{64}$/.test(readiness.backup_sha256) &&
    typeof readiness.checked_at === "string" && Array.isArray(readiness.dependencies) &&
    Number.isSafeInteger(value.dependency_count) && value.dependency_count === readiness.dependencies.length &&
    ((readiness.status === "READY") === (value.disposition === "READY_FOR_REHEARSAL"));
}

function validRecoveryRehearsalReview(
  value: unknown,
  sourceHash: string
): value is RecoveryRehearsalReview {
  if (
    !isJsonObject(value) ||
    value.schema_version !== "forgegate.recovery-rehearsal-review.v1" ||
    typeof value.review_id !== "string" ||
    !/^sha256:[0-9a-f]{64}$/.test(value.review_id) ||
    value.source_receipt_sha256 !== sourceHash ||
    value.disposition !== "VERIFIED_RESTORED_COPY" ||
    value.path_input !== "NOT_ACCEPTED" ||
    value.restore_execution !== "NOT_PERFORMED_BY_REVIEW" ||
    value.live_workspace_switch !== "NOT_PERFORMED" ||
    value.continuing_availability !== "NOT_CHECKED"
  ) return false;
  const receipt = value.receipt;
  return isJsonObject(receipt) &&
    receipt.schema_version === "forgegate.recovery-rehearsal.v1" &&
    receipt.status === "RESTORED_COPY_VERIFIED" &&
    receipt.restore_mode === "new_directory_only" &&
    receipt.live_workspace_changed === false &&
    receipt.archived_payloads === "VERIFIED_EXTERNAL_NOT_REHYDRATED" &&
    typeof receipt.rehearsal_id === "string" && /^sha256:[0-9a-f]{64}$/.test(receipt.rehearsal_id) &&
    typeof receipt.handoff_sha256 === "string" && /^[0-9a-f]{64}$/.test(receipt.handoff_sha256) &&
    typeof receipt.completed_at === "string" &&
    typeof receipt.post_restore_job_count === "number" && Number.isSafeInteger(receipt.post_restore_job_count) &&
    receipt.post_restore_job_count >= 0 &&
    typeof receipt.post_restore_job_event_count === "number" && Number.isSafeInteger(receipt.post_restore_job_event_count) &&
    receipt.post_restore_job_event_count >= receipt.post_restore_job_count &&
    isJsonObject(receipt.candidate_store) &&
    typeof receipt.candidate_store.sha256 === "string" && /^[0-9a-f]{64}$/.test(receipt.candidate_store.sha256) &&
    typeof receipt.candidate_store.size_bytes === "number" &&
    Number.isSafeInteger(receipt.candidate_store.size_bytes) && receipt.candidate_store.size_bytes >= 0 &&
    isJsonObject(receipt.job_store) &&
    typeof receipt.job_store.sha256 === "string" && /^[0-9a-f]{64}$/.test(receipt.job_store.sha256) &&
    typeof receipt.job_store.size_bytes === "number" &&
    Number.isSafeInteger(receipt.job_store.size_bytes) && receipt.job_store.size_bytes >= 0 &&
    typeof receipt.post_restore_inspection_fingerprint === "string" &&
    /^sha256:[0-9a-f]{64}$/.test(receipt.post_restore_inspection_fingerprint) &&
    receipt.automatic_execution === "NOT_PERFORMED" &&
    receipt.hardware_access === "NOT_PERFORMED" &&
    receipt.producer_authenticity === "NOT_VERIFIED" &&
    receipt.external_identity_and_artifact_files === "NOT_CHECKED" &&
    receipt.availability === "observed_during_rehearsal_only" &&
    isJsonObject(receipt.handoff) &&
    typeof receipt.handoff.source_report_sha256 === "string" &&
    /^[0-9a-f]{64}$/.test(receipt.handoff.source_report_sha256) &&
    validRecoveryHandoff(receipt.handoff, receipt.handoff.source_report_sha256);
}

async function renderRecovery(): Promise<void> {
  const generation = ++recoveryViewGeneration;
  const owner = session;
  const active = () => generation === recoveryViewGeneration && session === owner && currentRoute === "recovery";
  const main = page(
    "Recovery handoff",
    "HISTORICAL OFFLINE CHECK",
    "Review a CLI-generated readiness report and hand its validated identity to a recovery rehearsal. No backup payload is uploaded."
  );
  if (owner?.principal.role !== "operator") {
    main.append(emptyState("Operator session required", "Recovery report review requires an operator session. No document was sent."));
    shell(main);
    return;
  }
  const form = el("section", "panel recovery-import");
  form.append(
    el("p", "eyebrow", "LOCAL REPORT IMPORT"),
    el("h2", undefined, "Select an offline readiness report"),
    el("p", "muted", "Use forgegate.workspace-recovery-readiness.v1 output from workspace recovery-check. The report contains identities and outcomes, not ZIP payloads or local paths.")
  );
  const label = el("label", "field file-field");
  label.append(el("span", undefined, "Recovery readiness JSON"));
  const input = el("input");
  input.type = "file";
  input.accept = ".json,application/json";
  input.required = true;
  label.append(input);
  const review = button("Review recovery report", "button primary");
  const status = el("section", "recovery-review");
  status.setAttribute("aria-live", "polite");
  form.append(label, el("p", "muted", "Maximum size: 262,144 bytes. The exact UTF-8 bytes are hashed before same-origin validation."), review);
  const rehearsalForm = el("section", "panel recovery-import");
  rehearsalForm.append(
    el("p", "eyebrow", "COMPLETED REHEARSAL IMPORT"),
    el("h2", undefined, "Review a verified restored-copy receipt"),
    el("p", "muted", "Use forgegate.recovery-rehearsal.v1 from workspace rehearse-recovery. The browser submits exact receipt text, never a restored database, backup ZIP, local path, or private key.")
  );
  const rehearsalLabel = el("label", "field file-field");
  rehearsalLabel.append(el("span", undefined, "Recovery rehearsal JSON"));
  const rehearsalInput = el("input");
  rehearsalInput.type = "file";
  rehearsalInput.accept = ".json,application/json";
  rehearsalInput.required = true;
  rehearsalLabel.append(rehearsalInput);
  const rehearsalReview = button("Review rehearsal receipt", "button primary");
  const rehearsalStatus = el("section", "recovery-review");
  rehearsalStatus.setAttribute("aria-live", "polite");
  rehearsalForm.append(
    rehearsalLabel,
    el("p", "muted", "Maximum size: 1,048,576 bytes. Exact UTF-8 bytes and the content-derived receipt are validated."),
    rehearsalReview
  );
  main.append(form, status, rehearsalForm, rehearsalStatus);
  shell(main);
  input.addEventListener("change", () => {
    input.setCustomValidity("");
    review.disabled = false;
    status.replaceChildren();
  });
  review.addEventListener("click", async () => {
    const file = input.files?.[0];
    if (file === undefined) {
      input.setCustomValidity("Select one recovery readiness JSON document.");
      input.reportValidity();
      return;
    }
    input.setCustomValidity("");
    if (file.size === 0 || file.size > MAX_RECOVERY_REPORT_BYTES) {
      showProblem(status, new RequestProblem(413, "DASHBOARD_RECOVERY_IMPORT_TOO_LARGE", "The selected report is empty or exceeds 262,144 bytes.", "browser-side", null, "browser"), "Choose the exact bounded JSON report created by recovery-check.");
      return;
    }
    review.disabled = true;
    status.replaceChildren(el("p", "muted", "Hashing and validating the selected report…"));
    try {
      const bytes = await file.arrayBuffer();
      if (bytes.byteLength !== file.size) throw new Error("The selected file changed while it was read.");
      const document = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      const parsed: unknown = JSON.parse(document);
      if (!isJsonObject(parsed) || parsed.schema_version !== "forgegate.workspace-recovery-readiness.v1") {
        throw new Error("Expected schema_version forgegate.workspace-recovery-readiness.v1.");
      }
      const sourceHash = await sha256Hex(bytes);
      const handoff = await api<RecoveryHandoff>("/app/api/recovery-review", {
        method: "POST",
        headers: { "X-ForgeGate-CSRF": owner.csrf_token },
        body: JSON.stringify({ document, expected_sha256: sourceHash })
      });
      if (!active()) return;
      if (!validRecoveryHandoff(handoff, sourceHash)) {
        throw new RequestProblem(500, "DASHBOARD_RECOVERY_RESPONSE_INVALID", "The service returned an inconsistent recovery handoff.", "unavailable", null);
      }
      const heading = el("div", "card-heading");
      const title = el("div");
      title.append(el("p", "eyebrow", "VALIDATED HANDOFF"), el("h2", undefined, handoff.disposition === "READY_FOR_REHEARSAL" ? "Ready for an explicit rehearsal" : "Recovery is blocked"));
      heading.append(title, statusBadge(handoff.disposition));
      const metrics = el("section", "metric-grid");
      for (const [name, value] of [
        ["Archived tasks", String(handoff.readiness.archived_job_count)],
        ["Dependencies verified", `${handoff.verified_dependency_count} / ${handoff.dependency_count}`],
        ["Result payloads", String(handoff.result_payloads_verified)],
        ["No-result tasks", String(handoff.jobs_without_result)]
      ]) {
        const card = el("article", "metric-card");
        card.append(el("span", undefined, name), el("strong", undefined, value));
        metrics.append(card);
      }
      const identity = el("dl", "definition-list");
      identity.append(
        definition("Handoff ID", handoff.handoff_id, true),
        definition("Imported file SHA-256", handoff.source_report_sha256, true),
        definition("Root backup SHA-256", handoff.readiness.backup_sha256, true),
        definition("Root manifest", handoff.readiness.manifest_fingerprint, true),
        definition("Observed during offline check", formatDate(handoff.readiness.checked_at)),
        definition("Restore", handoff.restore),
        definition("Backup payload transfer", handoff.payload_transfer),
        definition("Live availability", handoff.live_availability)
      );
      const dependencies = el("section", "dependency-list");
      dependencies.append(el("h3", undefined, "Original backup dependencies"));
      if (handoff.readiness.dependencies.length === 0) {
        dependencies.append(emptyState("No archived payload dependency", "This validated snapshot contains no archived task requiring an original result backup."));
      }
      for (const dependency of handoff.readiness.dependencies) {
        const item = el("details", "panel dependency-item");
        const summary = el("summary");
        summary.append(statusBadge(dependency.status), el("span", undefined, `${shortHash(dependency.backup_sha256)} · ${dependency.job_ids.length} task(s)`));
        const values = el("dl", "definition-list");
        values.append(
          definition("Backup SHA-256", dependency.backup_sha256, true),
          definition("Tasks", dependency.job_ids.join(", "), true),
          definition("Verified result payloads", String(dependency.result_payloads_verified)),
          definition("Valid tasks without result", String(dependency.jobs_without_result)),
          definition("Failure code", dependency.error_code ?? "none")
        );
        item.append(summary, values);
        dependencies.append(item);
      }
      const boundary = el("p", "command-boundary", "This handoff records a past offline observation. Before recovery, rerun recovery-check against the files you will use. Downloading this JSON performs no restore, availability probe, candidate write, hardware action, or publication.");
      const actions = el("div", "dialog-actions");
      const download = button("Download reviewed handoff JSON", "button secondary");
      const downloadStatus = el("p", "muted");
      download.addEventListener("click", async () => {
        const serialized = `${JSON.stringify(handoff, null, 2)}\n`;
        const encoded = new TextEncoder().encode(serialized);
        const exportedHash = await sha256Hex(encoded.buffer);
        saveLocalDownload({
          blob: new Blob([encoded], { type: "application/json" }),
          filename: `recovery-handoff-${handoff.handoff_id.replace(/^sha256:/, "")}.json`
        });
        downloadStatus.textContent = `Browser download requested · exported file SHA-256 ${exportedHash}`;
      });
      actions.append(download);
      status.replaceChildren(heading, metrics, identity, dependencies, boundary, actions, downloadStatus);
      download.focus();
    } catch (error) {
      if (!active()) return;
      const normalized = error instanceof RequestProblem ? error : new RequestProblem(422, "DASHBOARD_RECOVERY_IMPORT_INVALID", error instanceof Error ? error.message : "The selected report is invalid.", "browser-side", null, "browser");
      showProblem(status, normalized, "Generate a fresh report with workspace recovery-check, then select its exact JSON output.");
      review.disabled = false;
    }
  });
  rehearsalInput.addEventListener("change", () => {
    rehearsalInput.setCustomValidity("");
    rehearsalReview.disabled = false;
    rehearsalStatus.replaceChildren();
  });
  rehearsalReview.addEventListener("click", async () => {
    const file = rehearsalInput.files?.[0];
    if (file === undefined) {
      rehearsalInput.setCustomValidity("Select one recovery rehearsal JSON document.");
      rehearsalInput.reportValidity();
      return;
    }
    rehearsalInput.setCustomValidity("");
    if (file.size === 0 || file.size > 1_048_576) {
      showProblem(
        rehearsalStatus,
        new RequestProblem(413, "DASHBOARD_REHEARSAL_IMPORT_TOO_LARGE", "The selected receipt is empty or exceeds 1,048,576 bytes.", "browser-side", null, "browser"),
        "Choose the exact bounded REHEARSAL.json created by rehearse-recovery."
      );
      return;
    }
    rehearsalReview.disabled = true;
    rehearsalStatus.replaceChildren(el("p", "muted", "Hashing and validating the completed rehearsal receipt…"));
    try {
      const bytes = await file.arrayBuffer();
      if (bytes.byteLength !== file.size) throw new Error("The selected file changed while it was read.");
      const document = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      const parsed: unknown = JSON.parse(document);
      if (!isJsonObject(parsed) || parsed.schema_version !== "forgegate.recovery-rehearsal.v1") {
        throw new Error("Expected schema_version forgegate.recovery-rehearsal.v1.");
      }
      const sourceHash = await sha256Hex(bytes);
      const reviewed = await api<RecoveryRehearsalReview>("/app/api/recovery-rehearsal-review", {
        method: "POST",
        headers: { "X-ForgeGate-CSRF": owner.csrf_token },
        body: JSON.stringify({ document, expected_sha256: sourceHash })
      });
      if (!active()) return;
      if (!validRecoveryRehearsalReview(reviewed, sourceHash)) {
        throw new RequestProblem(500, "DASHBOARD_REHEARSAL_RESPONSE_INVALID", "The service returned an inconsistent rehearsal review.", "unavailable", null);
      }
      const receipt = reviewed.receipt;
      const heading = el("div", "card-heading");
      const title = el("div");
      title.append(el("p", "eyebrow", "VALIDATED COMPLETION RECEIPT"), el("h2", undefined, "Restored copy verified"));
      heading.append(title, statusBadge(reviewed.disposition));
      const metrics = el("section", "metric-grid");
      for (const [name, value] of [
        ["Restored tasks", String(receipt.post_restore_job_count)],
        ["Task events", String(receipt.post_restore_job_event_count)],
        ["Archived tasks", String(receipt.handoff.readiness.archived_job_count)],
        ["External results verified", String(receipt.handoff.result_payloads_verified)]
      ]) {
        const card = el("article", "metric-card");
        card.append(el("span", undefined, name), el("strong", undefined, value));
        metrics.append(card);
      }
      const identity = el("dl", "definition-list");
      identity.append(
        definition("Rehearsal ID", receipt.rehearsal_id, true),
        definition("Review ID", reviewed.review_id, true),
        definition("Imported receipt SHA-256", reviewed.source_receipt_sha256, true),
        definition("Root backup SHA-256", receipt.handoff.readiness.backup_sha256, true),
        definition("Candidate database", `${receipt.candidate_store.sha256} · ${receipt.candidate_store.size_bytes} bytes`, true),
        definition("Job database", `${receipt.job_store.sha256} · ${receipt.job_store.size_bytes} bytes`, true),
        definition("Post-restore inspection", receipt.post_restore_inspection_fingerprint, true),
        definition("Completed", formatDate(receipt.completed_at)),
        definition("Restore mode", receipt.restore_mode),
        definition("Archived payload handling", receipt.archived_payloads)
      );
      const boundary = el("p", "command-boundary", "This page validated a completed local rehearsal receipt. It did not read a server path, execute recovery, upload database or backup bytes, rehydrate archived results, switch the live workspace, check continuing availability, run queued tasks, authenticate producers, or control hardware.");
      rehearsalStatus.replaceChildren(heading, metrics, identity, boundary);
      rehearsalStatus.setAttribute("tabindex", "-1");
      rehearsalStatus.focus();
    } catch (error) {
      if (!active()) return;
      const normalized = error instanceof RequestProblem ? error : new RequestProblem(422, "DASHBOARD_REHEARSAL_IMPORT_INVALID", error instanceof Error ? error.message : "The selected receipt is invalid.", "browser-side", null, "browser");
      showProblem(rehearsalStatus, normalized, "Select the exact REHEARSAL.json from a completed new-directory rehearsal.");
      rehearsalReview.disabled = false;
    }
  });
  input.focus();
}

function jobsHash(projectId: string, candidateId = "", after = "", jobId = "", archiveFilter = "all"): string {
  const params = new URLSearchParams({ project_id: projectId });
  if (candidateId) params.set("candidate_id", candidateId);
  if (after) params.set("after_job_id", after);
  if (jobId) params.set("job_id", jobId);
  if (archiveFilter !== "all") params.set("archive_filter", archiveFilter);
  return `#/jobs?${params.toString()}`;
}

async function renderJobs(): Promise<void> {
  const generation = ++jobsViewGeneration;
  const owner = session;
  const route = window.location.hash;
  const active = () => generation === jobsViewGeneration && session === owner && window.location.hash === route;
  const main = page("Collection jobs", "DURABLE LOCAL TASKS", "Inspect retained report tasks. Completion is not a policy PASS. Refresh to observe external progress.");
  if (owner?.principal.role !== "operator") {
    main.append(emptyState("Operator session required", "Job results and management require an authorized operator. No job request was sent."));
    shell(main);
    return;
  }
  const scopes = owner.principal.project_ids;
  const query = new URLSearchParams(route.split("?", 2)[1] ?? "");
  const projectId = query.get("project_id") ?? scopes[0] ?? "";
  const candidateId = query.get("candidate_id") ?? "";
  const after = query.get("after_job_id") ?? "";
  const jobId = query.get("job_id") ?? "";
  const archiveFilter = query.get("archive_filter") ?? "all";
  if (!scopes.includes(projectId) || (candidateId !== "" && !/^cand-[0-9a-f]{24}$/.test(candidateId)) ||
      [after, jobId].some(value => value !== "" && !/^job-[0-9a-f]{32}$/.test(value)) ||
      !["all", "current", "archived"].includes(archiveFilter)) {
    main.append(emptyState("Invalid job selection", "Choose an authorized project and complete candidate/job identifiers."));
    const reset = el("a", "button secondary", "Reset job filters");
    reset.href = "#/jobs";
    main.append(reset);
    shell(main);
    return;
  }
  const form = el("form", "toolbar audit-filters");
  const projectLabel = el("label", "field");
  projectLabel.append(el("span", undefined, "Job project"));
  const selector = el("select");
  for (const scope of scopes) {
    const option = el("option", undefined, scope);
    option.value = scope;
    selector.append(option);
  }
  selector.value = projectId;
  projectLabel.append(selector);
  const candidateLabel = el("label", "field");
  candidateLabel.append(el("span", undefined, "Candidate ID (optional)"));
  const candidateInput = el("input");
  candidateInput.value = candidateId;
  candidateInput.pattern = "cand-[0-9a-f]{24}";
  candidateInput.maxLength = 29;
  candidateLabel.append(candidateInput);
  const archiveLabel = el("label", "field");
  archiveLabel.append(el("span", undefined, "Archive status"));
  const archiveSelector = el("select");
  for (const [value, label] of [["all", "All tasks"], ["current", "Current tasks"], ["archived", "Archived tasks"]] as const) {
    const option = el("option", undefined, label);
    option.value = value;
    archiveSelector.append(option);
  }
  archiveSelector.value = archiveFilter;
  archiveLabel.append(archiveSelector);
  selector.addEventListener("change", () => { candidateInput.value = ""; });
  const apply = button("Apply job filters", "button primary");
  apply.type = "submit";
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (candidateInput.value && !/^cand-[0-9a-f]{24}$/.test(candidateInput.value)) { candidateInput.reportValidity(); return; }
    const next = jobsHash(selector.value, candidateInput.value, "", "", archiveSelector.value);
    if (window.location.hash === next) void renderJobs();
    else window.location.hash = next;
  });
  const refresh = button("Refresh jobs", "button secondary");
  refresh.addEventListener("click", () => void renderJobs());
  form.append(projectLabel, candidateLabel, archiveLabel, apply, refresh);
  main.append(form, el("p", "command-boundary", "Submit from an unbound COLLECTING candidate, then separately review execution here. Execution parses retained reports; it does not run project tests. No automatic worker, evidence binding, hardware access or release decision occurs here. Pending raw reports stay in the configured local store; logical release is not secure erasure."));
  const results = el("section", "job-results");
  results.setAttribute("aria-live", "polite");
  results.append(el("p", "muted", "Loading retained tasks…"));
  main.append(results);
  shell(main);
  try {
    if (jobId) {
      const review = await api<JobReview>(`/app/api/jobs/${jobId}?${new URLSearchParams({ project_id: projectId })}`);
      if (!active()) return;
      results.replaceChildren();
      const back = el("a", "button quiet", "Back to project jobs");
      back.href = jobsHash(projectId, candidateId, after, "", archiveFilter);
      results.append(back, renderJobDetail(main, review));
      return;
    }
    const params = new URLSearchParams({ project_id: projectId, limit: "25" });
    if (candidateId) params.set("candidate_id", candidateId);
    if (after) params.set("after_job_id", after);
    params.set("archive_filter", archiveFilter);
    const page = await api<JobPage>(`/app/api/jobs?${params}`);
    if (!active()) return;
    results.replaceChildren();
    if (!page.enabled) {
      results.append(emptyState("Job store not enabled", "Start an isolated or explicitly approved Dashboard with --job-store pointing to an existing v2 store. No file was created or migrated. Existing services do not gain this capability automatically."));
      return;
    }
    if (page.project_usage) {
      const usage = page.project_usage;
      const capacity = el("section", "panel");
      capacity.append(el("h2", undefined, "Project task storage"));
      const metrics = el("div", "metric-grid");
      const values: Array<[string, number]> = [["Current tasks", usage.current_jobs], ["Archived tasks", usage.archived_jobs], ["Pending input bytes", usage.pending_input_bytes], ["Live result bytes", usage.live_result_bytes]];
      for (const [label, value] of values) {
        const metric = el("div", "metric-card");
        metric.append(el("span", undefined, label), el("strong", undefined, String(value)));
        metrics.append(metric);
      }
      capacity.append(metrics, el("p", "muted", `Project-scoped usage in job store v${usage.store_version}; archiving is ${usage.archiving_enabled ? "enabled" : "not enabled"}. Store-wide remaining capacity is intentionally not disclosed in the browser.`));
      if (usage.external_backup_dependencies.length) {
        capacity.append(el("h3", undefined, "External archive dependencies"),
          el("p", "command-boundary", `${usage.external_backup_dependencies.length} original backup${usage.external_backup_dependencies.length === 1 ? " is" : "s are"} required. Availability was not checked by this page; retain and verify them with the owner CLI.`));
        for (const dependency of usage.external_backup_dependencies.slice(0, 5)) capacity.append(el("p", "mono", dependency));
        if (usage.external_backup_dependencies.length > 5) capacity.append(el("p", "muted", "Only the first 5 hashes are shown. Use jobs capacity for the complete store-wide list."));
      } else {
        capacity.append(el("p", "muted", "No external archive dependency is recorded for this project. This does not prove backup availability or recovery readiness."));
      }
      results.append(capacity);
    }
    results.append(el("p", "pager-status", `${page.jobs.length} jobs shown · ${page.has_more ? "More jobs available" : "End of matching jobs"} · Read at ${formatDate(page.observed_at)}`));
    if (!page.jobs.length) results.append(emptyState("No matching jobs", "Submit a report task from a candidate or the local CLI, or change the filter. Empty results do not prove successful collection."));
    for (const job of page.jobs) {
      const item = el("article", "panel job-card");
      const link = el("a", "button quiet", `Inspect ${job.job_id}`);
      link.href = jobsHash(projectId, candidateId, after, job.job_id, archiveFilter);
      const storage = page.archived_job_ids.includes(job.job_id) ? statusBadge("ARCHIVED") : statusBadge("CURRENT");
      item.append(statusBadge(job.state), storage, el("p", "mono", job.candidate_id), el("p", "muted", `Revision ${job.revision} · Updated ${formatDate(job.updated_at)}`), link);
      results.append(item);
    }
    const pager = el("nav", "pager");
    pager.setAttribute("aria-label", "Job pages");
    const first = el("a", "button quiet", "First job page");
    first.href = jobsHash(projectId, candidateId, "", "", archiveFilter);
    pager.append(first);
    if (page.has_more && page.next_after_job_id) {
      const next = el("a", "button secondary", "Next job page");
      next.href = jobsHash(projectId, candidateId, page.next_after_job_id, "", archiveFilter);
      pager.append(next);
    }
    pager.append(el("p", "muted", "Sorted by job ID, not time. Browser Back restores filters; no snapshot total is claimed."));
    results.append(pager);
  } catch (error) {
    if (active()) handleProtectedProblem(results, error, "Refresh jobs to inspect authoritative state. Do not automatically retry a write.");
  }
}

function renderJobDetail(main: HTMLElement, review: JobReview): HTMLElement {
  const job = review.record;
  const panel = el("section", "panel job-detail");
  panel.append(el("h2", undefined, "Retained task"), statusBadge(job.state));
  const details = el("dl", "definition-list");
  for (const [label, value] of Object.entries({
    "Job ID": job.job_id, "Project": job.project_id, "Candidate": job.candidate_id,
    "Revision": String(job.revision), "Updated": formatDate(job.updated_at),
    "Lease expires": job.lease_expires_at ? formatDate(job.lease_expires_at) : "No active lease",
    "Execution owner": job.execution_owner_id ?? "No execution owner recorded",
    "Lease renewals": String(job.lease_renewal_count ?? 0),
    "Creation authority": job.authority, "Source bytes": job.source_bytes,
    "Request fingerprint": job.request_fingerprint, "Result fingerprint": job.result_fingerprint ?? "No result",
    "Error code": job.error_code ?? "None recorded"
  })) details.append(definition(label, value, true));
  panel.append(details);
  if (review.archive) {
    const archive = el("section", "notice");
    archive.append(el("h3", undefined, "Archived result — external backup required"),
      el("p", undefined, "The task identity, state history and duplicate-request protection are retained. Result bytes are no longer available in this workspace. Use the owner CLI with the original backup to retrieve them; this page cannot restore or bind an archived result."));
    const metadata = el("dl", "definition-list");
    metadata.append(definition("Archived", formatDate(review.archive.archived_at)),
      definition("Original backup SHA-256", review.archive.plan.backup_sha256, true),
      definition("Reviewed plan", review.archive.plan_fingerprint, true),
      definition("Result bytes moved logically", String(review.archive.plan.result_size_bytes)));
    archive.append(metadata, el("p", "muted", "Archival is not a new test result, policy decision, secure erasure or proof of reduced disk usage. Keep the original backup private and available."));
    panel.append(archive);
  }
  const candidate = el("a", "button secondary", "Review candidate evidence separately");
  candidate.href = candidateReviewHash("evidence", job.candidate_id);
  panel.append(candidate);
  if (session?.principal.role === "operator" && job.state === "SUCCEEDED" && review.result?.assembly !== null && review.result?.assembly !== undefined) {
    const download = button("Review assembly download", "button secondary");
    download.addEventListener("click", () => reviewJobAssemblyDownload(main, review, download));
    const bind = button("Review evidence binding from task", "button primary");
    bind.addEventListener("click", () => void reviewJobEvidenceBinding(main, review, bind));
    panel.append(download, bind);
  }
  if (job.state === "QUEUED") {
    const run = button("Review execution", "button primary");
    run.addEventListener("click", () => reviewJobAction(main, job, "run", run));
    panel.append(run);
  }
  if (["QUEUED", "RUNNING"].includes(job.state)) {
    const cancel = button("Review cancellation", "button secondary");
    cancel.addEventListener("click", () => reviewJobAction(main, job, "cancel", cancel));
    panel.append(cancel);
  }
  if (job.state === "RUNNING") {
    const recover = button("Review interruption recovery", "button secondary");
    recover.addEventListener("click", () => reviewJobAction(main, job, "recover", recover));
    panel.append(recover, el("p", "muted", "Recovery is accepted only after the server lease expires. It records INTERRUPTED; it does not restart execution."));
  }
  panel.append(el("h3", undefined, "State history and recorded actors"));
  for (const event of review.events) {
    panel.append(el("p", "job-event", `Revision ${event.record.revision} · ${event.record.state} · ${formatDate(event.record.updated_at)} · ${event.actor ? `${event.actor.display_name} (${event.actor.role}) · ${event.actor.identity_id}` : "Actor not recorded — no identity inferred"}`));
  }
  panel.append(el("h3", undefined, "Collection output — not a policy decision"));
  if (review.result === null) {
    panel.append(el("p", "muted", review.archive ? "Result archived externally. No new collection or policy decision was performed." : "No retained collection result. This is not an empty successful test run."));
  } else {
    panel.append(el("p", "mono", `Assembly: ${review.result.assembly?.assembly_id ?? "Not available"}`), el("p", "muted", "Source report bytes are not embedded. Binding requires a separate reviewed operation; this page cannot promote a result to PASS."));
    for (const collection of review.result.collections) {
      const item = el("section", "job-output");
      item.append(el("h4", undefined, collection.collector_name), statusBadge(collection.status), el("p", "muted", `Showing first ${Math.min(25, collection.evidence.length)} of ${collection.evidence.length} normalized records. Use jobs result CLI for the complete exact document.`));
      for (const evidence of collection.evidence.slice(0, 25)) {
        item.append(el("p", "mono", `${evidence.kind} · ${evidence.scope} · ${evidence.trust} / ${evidence.verification_level}`), el("pre", "job-values", JSON.stringify(evidence.value, null, 2)));
      }
      const issues = [...collection.warnings, ...collection.rejected_records];
      item.append(el("p", "muted", `${issues.length} issues; first ${Math.min(25, issues.length)} shown.`));
      for (const issue of issues.slice(0, 25)) item.append(el("p", undefined, `${issue.code}: ${issue.message}`));
      panel.append(item);
    }
  }
  return panel;
}

function reviewJobAssemblyDownload(main: HTMLElement, review: JobReview, returnFocus: HTMLElement): void {
  const owner = session;
  const assembly = review.result?.assembly;
  const job = review.record;
  if (owner?.principal.role !== "operator" || assembly === null || assembly === undefined || job.result_fingerprint === null) return;
  const route = window.location.hash;
  const generation = jobsViewGeneration;
  const dialog = el("dialog", "review-dialog");
  dialog.setAttribute("aria-labelledby", "job-assembly-export-title");
  const active = () => dialog.open && dialog.isConnected && session === owner && window.location.hash === route && generation === jobsViewGeneration;
  const heading = el("h2", undefined, "Confirm exact assembly download");
  heading.id = "job-assembly-export-title";
  const details = el("dl", "definition-list");
  details.append(
    definition("Job", job.job_id, true),
    definition("Candidate", job.candidate_id, true),
    definition("Job revision", String(job.revision)),
    definition("Result fingerprint", job.result_fingerprint, true),
    definition("Assembly ID", assembly.assembly_id, true),
    definition("Evidence records", String(assembly.bundle.evidence.length)),
    definition("Collector receipts", String(assembly.collections.length)),
    definition("Warning disposition", assembly.warning_disposition)
  );
  const status = el("div", "dialog-status");
  status.setAttribute("aria-live", "polite");
  const controls = el("div", "dialog-actions");
  const close = button("Cancel", "button quiet");
  close.addEventListener("click", () => dialog.close());
  const confirm = button("Download canonical assembly", "button primary");
  let busy = false;
  confirm.addEventListener("click", async () => {
    if (!active() || busy) return;
    busy = true;
    close.disabled = confirm.disabled = true;
    status.replaceChildren(el("p", "muted", "Retrieving and verifying the reviewed canonical bytes…"));
    try {
      const download = await downloadJobAssembly(job, assembly.assembly_id);
      if (!active()) return;
      saveLocalDownload(download);
      heading.textContent = "Download requested";
      status.replaceChildren(statusBadge("Exact bytes verified"), el("p", undefined, `${download.filename} was handed to the browser after SHA-256 verification: ${download.fingerprint}.`));
      const done = button("Done", "button primary");
      done.addEventListener("click", () => dialog.close());
      controls.replaceChildren(done);
      done.focus();
    } catch (error) {
      if (!active()) return;
      if (handleProtectedProblem(status, error, "Close and refresh the task before reviewing a new export. No automatic retry occurs.")) return;
      close.disabled = false;
      close.textContent = "Close and refresh";
      controls.replaceChildren(close);
      close.focus();
    } finally {
      busy = false;
    }
  });
  controls.append(close, confirm);
  dialog.append(
    el("p", "eyebrow", "REVIEWED LOCAL EXPORT"),
    heading,
    el("p", "command-boundary", "This downloads the canonical assembly already retained in the terminal job. It excludes original source-report bytes, changes no state, starts no test, binds no candidate and makes no policy decision."),
    details,
    status,
    controls
  );
  dialog.addEventListener("cancel", event => { event.preventDefault(); if (!busy) dialog.close(); });
  dialog.addEventListener("keydown", event => keepFocusInsideDialog(dialog, event));
  dialog.addEventListener("close", () => { dialog.remove(); if (returnFocus.isConnected) returnFocus.focus(); });
  main.append(dialog);
  dialog.showModal();
  close.focus();
}

async function reviewJobEvidenceBinding(main: HTMLElement, review: JobReview, returnFocus: HTMLElement): Promise<void> {
  const owner = session;
  const assembly = review.result?.assembly;
  const job = review.record;
  if (owner?.principal.role !== "operator" || assembly === null || assembly === undefined || job.result_fingerprint === null) return;
  const route = window.location.hash;
  const generation = jobsViewGeneration;
  const dialog = el("dialog", "review-dialog");
  dialog.setAttribute("aria-labelledby", "job-evidence-bind-title");
  let busy = false;
  const active = () => dialog.open && dialog.isConnected && session === owner && window.location.hash === route && generation === jobsViewGeneration;
  const heading = el("h2", undefined, "Review evidence binding from task");
  heading.id = "job-evidence-bind-title";
  const content = el("section", "review-panel");
  content.append(el("p", "eyebrow", "REVIEWED EVIDENCE WRITE"), heading, el("p", "muted", "Loading the current candidate before any write…"));
  dialog.append(content);
  dialog.addEventListener("cancel", event => { event.preventDefault(); if (!busy) dialog.close(); });
  dialog.addEventListener("keydown", event => keepFocusInsideDialog(dialog, event));
  dialog.addEventListener("close", () => { dialog.remove(); if (returnFocus.isConnected) returnFocus.focus(); });
  main.append(dialog);
  dialog.showModal();
  try {
    const candidateReview = await api<CandidateAssuranceReview>(`/app/api/candidates/${encodeURIComponent(job.candidate_id)}/assurance-review`);
    if (!active()) return;
    const candidate = candidateReview.candidate;
    if (candidate.candidate_id !== job.candidate_id || candidate.project_id !== job.project_id || assembly.bundle.candidate_commit !== candidate.commit_sha) {
      throw new RequestProblem(0, "DASHBOARD_BINDING_REVIEW_INVALID", "The task and current candidate identities do not match.", "not issued", null, "browser");
    }
    if (candidateReview.evidence_binding !== null || candidate.status !== "COLLECTING" || candidate.revision !== 1) {
      content.replaceChildren(el("p", "eyebrow", "NO WRITE AVAILABLE"), heading, el("p", "command-boundary", candidateReview.evidence_binding === null ? "The candidate is no longer an unbound revision-one COLLECTING candidate. No binding request was sent." : "The candidate already has an immutable evidence binding. Compare its assembly identity on the Evidence page; no replacement request was sent."));
      const inspect = el("a", "button primary", "Review current candidate evidence");
      inspect.href = candidateReviewHash("evidence", candidate.candidate_id);
      content.append(inspect);
      inspect.focus();
      return;
    }
    const boundAt = new Date().toISOString();
    const body = {
      expected_job_revision: job.revision,
      expected_result_fingerprint: job.result_fingerprint,
      expected_assembly_id: assembly.assembly_id,
      expected_candidate_revision: candidate.revision,
      expected_candidate_fingerprint: job.candidate_fingerprint,
      bound_at: boundAt
    };
    const details = el("dl", "definition-list");
    details.append(
      definition("Job", job.job_id, true),
      definition("Result fingerprint", job.result_fingerprint, true),
      definition("Assembly ID", assembly.assembly_id, true),
      definition("Candidate", candidate.candidate_id, true),
      definition("Candidate revision", String(candidate.revision)),
      definition("Candidate fingerprint", job.candidate_fingerprint, true),
      definition("Candidate commit", candidate.commit_sha, true),
      definition("Evidence records", String(assembly.bundle.evidence.length)),
      definition("Collector receipts", String(assembly.collections.length)),
      definition("Warning disposition", assembly.warning_disposition),
      definition("Bound at", formatDate(boundAt))
    );
    const status = el("div", "dialog-status");
    status.setAttribute("aria-live", "polite");
    const controls = el("div", "dialog-actions");
    const close = button("Back without binding", "button quiet");
    close.addEventListener("click", () => { if (!busy) dialog.close(); });
    const confirm = button("Confirm evidence binding", "button primary");
    const key = `dashboard:job-bind:${crypto.randomUUID()}`;
    confirm.addEventListener("click", async () => {
      if (!active() || busy) return;
      busy = true;
      close.disabled = confirm.disabled = true;
      status.replaceChildren(el("p", "muted", "Submitting the frozen job, result, assembly and candidate identities once…"));
      try {
        const response = await api<DashboardJobEvidenceBindingResult>(`/app/api/jobs/${encodeURIComponent(job.job_id)}/bind-evidence?${new URLSearchParams({project_id: job.project_id})}`, {method: "POST", headers: {"X-ForgeGate-CSRF": owner.csrf_token, "Idempotency-Key": key}, body: JSON.stringify(body)});
        if (!active()) return;
        if (
          response.schema_version !== "forgegate.dashboard-job-evidence-binding.v1"
          || response.job_id !== job.job_id
          || response.result_fingerprint !== job.result_fingerprint
          || response.assembly_id !== assembly.assembly_id
          || response.binding.assembly.assembly_id !== assembly.assembly_id
          || response.binding.candidate_fingerprint !== job.candidate_fingerprint
          || response.binding.assembly_fingerprint !== response.assembly_fingerprint
          || response.candidate_transition !== "NOT_PERFORMED"
          || response.policy_decision !== "NOT_PERFORMED"
          || response.source_artifact_bytes !== "not_embedded"
        ) throw new Error("Unexpected binding response identity; inspect candidate evidence before any new write.");
        heading.textContent = "Evidence binding retained";
        status.replaceChildren(statusBadge("Binding completed"), el("p", undefined, `Binding ${response.binding.binding_id} now retains assembly fingerprint ${response.assembly_fingerprint}. The candidate was not advanced to READY and no policy decision was made.`));
        const inspect = el("a", "button primary", "Review bound evidence");
        inspect.href = candidateReviewHash("evidence", candidate.candidate_id);
        controls.replaceChildren(inspect);
        inspect.focus();
      } catch (error) {
        if (!active()) return;
        if (handleProtectedProblem(status, error, "Inspect current candidate evidence before attempting any new binding. No automatic retry occurs.")) return;
        const inspect = el("a", "button secondary", "Inspect candidate evidence");
        inspect.href = candidateReviewHash("evidence", candidate.candidate_id);
        controls.replaceChildren(inspect);
        inspect.focus();
      } finally {
        busy = false;
      }
    });
    controls.append(close, confirm);
    content.replaceChildren(
      el("p", "eyebrow", "REVIEWED EVIDENCE WRITE"),
      heading,
      el("p", "command-boundary", "This binds the terminal job's existing assembly to this candidate. It does not rerun parsing, embed raw source reports, authenticate their producer, advance the candidate to READY, evaluate policy, publish or access hardware."),
      details,
      status,
      controls
    );
    close.focus();
  } catch (error) {
    if (!active()) return;
    if (handleProtectedProblem(content, error, "Close, refresh the task and inspect current candidate state.")) return;
    const close = button("Close", "button primary");
    close.addEventListener("click", () => dialog.close());
    content.append(close);
    close.focus();
  }
}

function reviewJobAction(main: HTMLElement, job: CollectionJob, action: "cancel" | "recover" | "run", returnFocus: HTMLElement): void {
  const owner = session;
  if (owner?.principal.role !== "operator") return;
  const route = window.location.hash;
  const generation = jobsViewGeneration;
  const dialog = el("dialog", "review-dialog");
  dialog.setAttribute("aria-labelledby", "job-action-title");
  const active = () => dialog.open && dialog.isConnected && session === owner && window.location.hash === route && generation === jobsViewGeneration;
  let busy = false;
  const heading = el("h2", undefined, action === "run" ? "Confirm report parsing" : action === "cancel" ? "Confirm task cancellation" : "Confirm interruption recovery");
  heading.id = "job-action-title";
  dialog.append(heading, el("p", "command-boundary", action === "run" ? "Parse this retained report selection once in the foreground. No test commands, plugins, device access or binding. The run records a non-credential owner and renews its lease at bounded parser checkpoints. Closing the page or losing the response does not stop parsing by itself: inspect the retained job before retrying." : action === "cancel" ? "This persists cancellation, revokes result publication and logically releases pending input. A running parser checks that state between bounded stages; it is not forcibly killed mid-parser. This does not securely erase bytes or change candidate evidence." : "Only an expired running lease can become INTERRUPTED. No retry or execution is started; no takeover is performed."));
  const details = el("dl", "definition-list");
  details.append(definition("Job", job.job_id, true), definition("Project", job.project_id), definition("Reviewed revision", String(job.revision)), definition("Operator", owner.principal.display_name));
  if (action === "run") details.append(definition("Retained request fingerprint", job.request_fingerprint, true));
  const status = el("div", "dialog-status");
  status.setAttribute("aria-live", "polite");
  const controls = el("div", "dialog-actions");
  const close = button("Back without changes", "button quiet");
  close.addEventListener("click", () => dialog.close());
  const confirm = button(action === "run" ? "Confirm execution" : action === "cancel" ? "Confirm cancellation" : "Confirm recovery", "button primary");
  confirm.addEventListener("click", async () => {
    if (!active() || busy || confirm.disabled) return;
    busy = true;
    confirm.disabled = true;
    close.disabled = true;
    status.replaceChildren(el("p", "muted", "Submitting the reviewed command once…"));
    try {
      const result = await api<CollectionJob>(`/app/api/jobs/${job.job_id}/${action}?${new URLSearchParams({ project_id: job.project_id })}`, { method: "POST", headers: { "X-ForgeGate-CSRF": owner.csrf_token }, body: JSON.stringify({ expected_revision: job.revision }) });
      if (!active()) return;
      status.replaceChildren(el("p", undefined, action === "run" ? `Observed ${result.state} at revision ${result.revision}. Inspect the retained output and actors. Parsing completion is not a policy PASS.` : `Recorded ${result.state} at revision ${result.revision}. The authenticated operator was retained with this event.`));
    } catch (error) {
      if (!active()) return;
      if (handleProtectedProblem(status, error, "Outcome may be uncertain. Close and refresh before creating another command; no automatic retry occurs.")) return;
    } finally {
      busy = false;
      if (active()) {
        const reload = button("Close and refresh jobs", "button primary");
        reload.addEventListener("click", () => { dialog.close(); void renderJobs(); });
        controls.replaceChildren(reload);
        reload.focus();
      }
    }
  });
  controls.append(close, confirm);
  dialog.append(details, status, controls);
  dialog.addEventListener("cancel", event => { event.preventDefault(); if (!busy) dialog.close(); });
  dialog.addEventListener("keydown", event => keepFocusInsideDialog(dialog, event));
  dialog.addEventListener("close", () => { dialog.remove(); if (returnFocus.isConnected) returnFocus.focus(); });
  main.append(dialog);
  dialog.showModal();
  close.focus();
}

function emptyState(title: string, description: string): HTMLElement {
  const state = el("section", "empty-state");
  state.append(el("span", "empty-mark", "—"), el("h2", undefined, title), el("p", undefined, description));
  return state;
}

async function renderCandidates(): Promise<void> {
  const owner = session;
  const hash = window.location.hash;
  const generation = ++candidatesViewGeneration;
  const current = (): boolean => owner !== null && session === owner && window.location.hash === hash && generation === candidatesViewGeneration;
  loadingPage("Candidates");
  const main = page(
    "Release candidates",
    "PROJECT-SCOPED WORK",
    "Choose individual reviewed commands or Quick assessment to process a reviewed report batch through evaluation and attestation."
  );
  try {
    const visible = await ensureProjects();
    if (!current()) return;
    if (visible.length === 0) {
      main.append(emptyState("No project available", "Register a project through the established CLI/API before creating a candidate."));
      shell(main);
      return;
    }
    if (!visible.some(project => project.project_id === selectedProjectId)) selectedProjectId = visible[0]!.project_id;
    const toolbar = el("section", "toolbar");
    const selectorWrap = el("label", "field compact-field");
    selectorWrap.append(el("span", undefined, "Project"));
    const selector = el("select");
    for (const project of visible) {
      const option = el("option", undefined, `${project.config.project.name} · ${project.project_id}`);
      option.value = project.project_id;
      option.selected = project.project_id === selectedProjectId;
      selector.append(option);
    }
    selector.addEventListener("change", () => {
      if (!current()) return;
      selectedProjectId = selector.value;
      candidateSearch = "";
      candidateStatusFilter = "ALL";
      resetCandidatePagination();
      void renderCandidates();
    });
    selectorWrap.append(selector);
    toolbar.append(selectorWrap);
    if (session?.principal.role === "operator") {
      const create = button("Create candidate", "button secondary");
      create.addEventListener("click", () => openCandidateDialog(main, create));
      toolbar.append(create);
      const quick = button("Quick assessment", "button primary");
      quick.addEventListener("click", () => openCandidateDialog(main, quick, undefined, true));
      toolbar.append(quick);
    } else {
      const readOnly = el("p", "muted", "Producer sessions are read-only.");
      toolbar.append(readOnly);
    }
    const refresh = button("Refresh candidates", "button quiet");
    refresh.addEventListener("click", () => { if (current()) void renderCandidates(); });
    toolbar.append(refresh);
    main.append(toolbar);
    if (projectListTruncated) main.append(el("p", "muted", "Showing the first 100 authorized projects. Narrow your activation scope to reach an unlisted project."));

    const projectId = selectedProjectId ?? visible[0]?.project_id;
    if (projectId === undefined) return;
    selectedProjectId = projectId;
    const query = new URLSearchParams({ limit: "25" });
    if (candidateCursor !== null) query.set("after_candidate_id", candidateCursor);
    const result = await api<CandidatePage>(
      `/app/api/projects/${encodeURIComponent(projectId)}/candidates?${query.toString()}`
    );
    if (!current()) return;
    if (result.candidates.length === 0) {
      main.append(
        emptyState(
          candidateCursor === null ? "No candidates yet" : "No candidates on this page",
          candidateCursor === null
            ? "Create the first reviewed candidate request for this project."
            : "Return to the previous page and reload the authoritative list."
        )
      );
    } else {
      main.append(candidateFilters(result.candidates, main));
    }
    main.append(el("p", "muted", "Browse by candidate ID, 25 at a time. Search and status filters apply only to the loaded page; use Next page to check further candidates."));
    main.append(candidatePager(result));
  } catch (error) {
    if (!current()) return;
    if (handleProtectedProblem(main, error, "Reload the candidate list and confirm the selected project scope.")) return;
    const retry = button("Refresh candidates", "button secondary");
    retry.addEventListener("click", () => { if (current()) void renderCandidates(); });
    main.append(retry);
  }
  shell(main);
}

function candidateFilters(candidates: Candidate[], main: HTMLElement): HTMLElement {
  const panel = el("section", "candidate-browser");
  const controls = el("div", "toolbar candidate-filters");
  const searchLabel = el("label", "field");
  searchLabel.append(el("span", undefined, "Search this page"));
  const search = el("input");
  search.type = "search";
  search.placeholder = "Version, commit, branch, track or candidate ID";
  search.maxLength = 255;
  search.value = candidateSearch;
  searchLabel.append(search);
  const statusLabel = el("label", "field compact-field");
  statusLabel.append(el("span", undefined, "State on this page"));
  const status = el("select");
  for (const name of ["ALL", ...Array.from(new Set(candidates.map(item => item.status))).sort()]) {
    const option = el("option", undefined, name === "ALL" ? "All states" : name);
    option.value = name;
    status.append(option);
  }
  if (candidateStatusFilter !== "ALL" && !candidates.some(item => item.status === candidateStatusFilter)) candidateStatusFilter = "ALL";
  status.value = candidateStatusFilter;
  statusLabel.append(status);
  const clear = button("Clear filters", "button quiet");
  controls.append(searchLabel, statusLabel, clear);
  const count = el("p", "muted");
  count.setAttribute("role", "status");
  const table = el("div");
  const apply = (): void => {
    candidateSearch = search.value;
    candidateStatusFilter = status.value;
    const term = candidateSearch.trim().toLowerCase();
    const found = candidates.filter(candidate => (candidateStatusFilter === "ALL" || candidate.status === candidateStatusFilter) &&
      [candidate.version, candidate.commit_sha, candidate.candidate_id, candidate.source_branch, candidate.release_track].some(value => value.toLowerCase().includes(term)));
    count.textContent = `${found.length} of ${candidates.length} loaded candidates match.`;
    table.replaceChildren(found.length === 0
      ? emptyState("No matches on this page", "Clear filters or move to another page. No project-wide search was performed.")
      : candidateTable(found, main));
  };
  search.addEventListener("input", apply);
  status.addEventListener("change", apply);
  clear.addEventListener("click", () => { search.value = ""; status.value = "ALL"; apply(); search.focus(); });
  panel.append(controls, count, table);
  apply();
  return panel;
}

function candidatePager(result: CandidatePage): HTMLElement {
  const pager = el("nav", "pager");
  pager.setAttribute("aria-label", "Candidate pages");
  const status = el(
    "p",
    "pager-status",
    `Page ${candidateCursorHistory.length + 1} · ${result.candidates.length} candidates shown`
  );
  status.setAttribute("aria-live", "polite");
  const controls = el("div", "pager-actions");
  const previous = button("Previous page", "button quiet");
  previous.disabled = candidateCursorHistory.length === 0;
  previous.addEventListener("click", () => {
    previous.disabled = true;
    next.disabled = true;
    candidateCursor = candidateCursorHistory.pop() ?? null;
    void renderCandidates();
  });
  const next = button("Next page", "button secondary");
  next.disabled = !result.has_more || result.next_after_candidate_id === null;
  next.addEventListener("click", () => {
    if (result.next_after_candidate_id === null) return;
    previous.disabled = true;
    next.disabled = true;
    candidateCursorHistory.push(candidateCursor);
    candidateCursor = result.next_after_candidate_id;
    void renderCandidates();
  });
  controls.append(previous, next);
  pager.append(status, controls);
  return pager;
}

function candidateTable(candidates: Candidate[], main: HTMLElement): HTMLElement {
  const wrapper = el("div", "table-wrap");
  const table = el("table");
  const caption = el("caption", "sr-only", "Release candidates");
  const head = el("thead");
  const headRow = el("tr");
  for (const label of ["Version", "State", "Commit", "Track", "Revision", "Updated", "Action"]) headRow.append(el("th", undefined, label));
  head.append(headRow);
  const body = el("tbody");
  for (const candidate of candidates) {
    const row = el("tr");
    const stateCell = el("td");
    stateCell.append(statusBadge(candidate.status));
    const actionCell = el("td");
    const inspect = button("Inspect", "button quiet compact-button");
    inspect.addEventListener("click", () => void showCandidateDetail(main, candidate.candidate_id));
    actionCell.append(inspect);
    row.append(
      el("td", "strong-cell", candidate.version),
      stateCell,
      el("td", "mono", shortHash(candidate.commit_sha)),
      el("td", undefined, candidate.release_track),
      el("td", undefined, String(candidate.revision)),
      el("td", undefined, formatDate(candidate.updated_at)),
      actionCell
    );
    body.append(row);
  }
  table.append(caption, head, body);
  wrapper.append(table);
  return wrapper;
}

function openCandidateDialog(
  main: HTMLElement,
  returnFocus?: HTMLElement,
  initialValues?: Record<string, string>,
  quick = false
): void {
  const dialog = el("dialog", "review-dialog");
  dialog.setAttribute("aria-labelledby", "candidate-dialog-title");
  const form = el("form", "candidate-form");
  form.method = "dialog";
  const heading = el("h2", undefined, "Create release candidate");
  heading.id = "candidate-dialog-title";
  form.append(el("p", "eyebrow", "DRAFT REQUEST"), heading, el("p", "muted", "Client checks guide this draft. ForgeGate remains authoritative."));
  const selectedProject = projects.find(project => project.project_id === selectedProjectId);
  if (selectedProject !== undefined) form.append(el("p", "muted", `Project: ${selectedProject.config.project.name} · ${selectedProject.project_id}`));
  if (initialValues !== undefined) {
    form.append(el("p", "muted", "Draft values restored for review; no request has been submitted."));
  }
  const version = field("Version", "version", "1.0.0", "text", true);
  const commit = field("Commit SHA", "commit", "40 or 64 lowercase hexadecimal characters", "text", true);
  commit.input.addEventListener("input", () => commit.input.setCustomValidity(""));
  const branch = field("Source branch", "branch", "main", "text", true);
  const track = field("Release track", "track", "pull-request", "text", true);
  version.input.value = initialValues?.version ?? "";
  commit.input.value = initialValues?.commit_sha ?? "";
  branch.input.value = initialValues?.source_branch ?? selectedProject?.config.project.default_branch ?? branch.input.value;
  const tracks = Object.keys(selectedProject?.config.release_tracks ?? {});
  track.input.value = initialValues?.release_track ?? (tracks.includes("pull-request") ? "pull-request" : tracks[0]) ?? track.input.value;
  form.append(version.wrapper, commit.wrapper, branch.wrapper, track.wrapper);
  const controls = el("div", "dialog-actions");
  const cancel = button("Cancel", "button quiet");
  cancel.addEventListener("click", () => dialog.close());
  const review = button("Review request", "button primary");
  review.addEventListener("click", () => {
    if (!form.reportValidity()) return;
    const values = {
      project_id: selectedProjectId ?? "",
      version: version.input.value.trim(),
      commit_sha: commit.input.value.trim(),
      source_branch: branch.input.value.trim(),
      release_track: track.input.value.trim(),
      created_at: new Date().toISOString()
    };
    if (!/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(values.commit_sha)) {
      commit.input.setCustomValidity("Use exactly 40 or 64 lowercase hexadecimal characters.");
      commit.input.reportValidity();
      return;
    }
    commit.input.setCustomValidity("");
    renderCandidateReview(dialog, values, returnFocus, quick);
  });
  controls.append(cancel, review);
  form.append(controls);
  dialog.append(form);
  main.append(dialog);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    dialog.close();
  });
  dialog.addEventListener("keydown", (event) => keepFocusInsideDialog(dialog, event));
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (returnFocus?.isConnected) returnFocus.focus();
  }, { once: true });
  dialog.showModal();
  version.input.focus();
}

function field(label: string, name: string, placeholder: string, type: string, required: boolean): { wrapper: HTMLLabelElement; input: HTMLInputElement } {
  const wrapper = el("label", "field");
  const input = el("input");
  input.name = name;
  input.type = type;
  input.placeholder = placeholder;
  input.required = required;
  input.autocomplete = "off";
  input.maxLength = name === "branch" ? 255 : 120;
  if (name === "commit") input.maxLength = 64;
  if (name === "branch") input.value = "main";
  if (name === "track") input.value = "pull-request";
  wrapper.append(el("span", undefined, label), input);
  return { wrapper, input };
}

function renderCandidateReview(
  dialog: HTMLDialogElement,
  values: Record<string, string>,
  returnFocus?: HTMLElement,
  quick = false
): void {
  const review = el("section", "review-panel");
  const heading = el("h2", undefined, "Confirm one durable write");
  heading.id = "candidate-dialog-title";
  review.append(el("p", "eyebrow", "REVIEWED COMMAND"), heading, el("p", "muted", "A successful request creates one DRAFT candidate and one append-only audit event. It does not collect evidence or make a release decision."));
  const details = el("dl", "definition-list");
  details.append(
    definition("Project", values.project_id ?? ""),
    definition("Version", values.version ?? ""),
    definition("Commit", values.commit_sha ?? "", true),
    definition("Branch", values.source_branch ?? ""),
    definition("Track", values.release_track ?? ""),
    definition("Created at", formatDate(values.created_at ?? ""))
  );
  const status = el("div", "dialog-status");
  status.setAttribute("aria-live", "polite");
  const controls = el("div", "dialog-actions");
  const back = button("Back to edit", "button quiet");
  back.addEventListener("click", () => {
    dialog.close();
    const workspace = document.querySelector<HTMLElement>("#workspace");
    if (workspace !== null) openCandidateDialog(workspace, returnFocus, values, quick);
  });
  const confirm = button("Confirm creation", "button primary");
  const idempotencyKey = `dashboard:candidate:${crypto.randomUUID()}`;
  confirm.addEventListener("click", async () => {
    if (session === null) return;
    back.disabled = true;
    confirm.disabled = true;
    status.replaceChildren(el("p", "muted", "Submitting one idempotent command…"));
    try {
      const created = await api<Candidate>("/app/api/candidates", {
        method: "POST",
        headers: {
          "X-ForgeGate-CSRF": session.csrf_token,
          "Idempotency-Key": idempotencyKey
        },
        body: JSON.stringify(values)
      });
      heading.textContent = "Request completed";
      const eyebrow = review.querySelector<HTMLElement>(".eyebrow");
      if (eyebrow !== null) eyebrow.textContent = "DRAFT CREATED";
      status.replaceChildren(statusBadge("Request completed"), el("p", undefined, `Candidate ${created.candidate_id} is ${created.status}. No policy decision has been made.`));
      const done = button(quick ? "Select reports and assess" : "Inspect candidate", "button primary");
      done.addEventListener("click", async () => {
        const parent = document.querySelector<HTMLElement>("#workspace");
        dialog.close();
        if (quick && parent !== null) { openQuickAssessment(parent, created); return; }
        resetCandidatePagination();
        await renderCandidates();
        const workspace = document.querySelector<HTMLElement>("#workspace");
        if (workspace !== null) void showCandidateDetail(workspace, created.candidate_id);
      });
      controls.replaceChildren(done);
      done.focus();
    } catch (error) {
      showProblem(status, error, "Return to the draft, reload current state if needed, and review before trying again.");
      back.disabled = false;
      if (error instanceof RequestProblem) {
        if (holdRateLimitedAction(dialog, confirm, error)) return;
        if ([409, 413, 500].includes(error.status)) return;
      }
      confirm.disabled = false;
    }
  });
  controls.append(back, confirm);
  review.append(details, status, controls);
  dialog.replaceChildren(review);
  confirm.focus();
}

function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function sha256Hex(content: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", content);
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

function openReviewedMutation(
  main: HTMLElement,
  candidate: Candidate,
  mutation: ReviewedMutation,
  returnFocus?: HTMLElement
): void {
  const dialog = el("dialog", "review-dialog");
  dialog.setAttribute("aria-labelledby", "candidate-command-dialog-title");
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    dialog.close();
  });
  dialog.addEventListener("keydown", (event) => keepFocusInsideDialog(dialog, event));
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (returnFocus?.isConnected) returnFocus.focus();
  }, { once: true });
  main.append(dialog);
  dialog.showModal();
  renderReviewedMutation(dialog, candidate, mutation);
}

function renderReviewedMutation(
  dialog: HTMLDialogElement,
  candidate: Candidate,
  mutation: ReviewedMutation
): void {
  const review = el("section", "review-panel");
  const heading = el("h2", undefined, mutation.title);
  heading.id = "candidate-command-dialog-title";
  review.append(
    el("p", "eyebrow", mutation.eyebrow),
    heading,
    el("p", "muted", mutation.summary)
  );
  const details = el("dl", "definition-list");
  for (const [label, value, mono] of mutation.details) {
    details.append(definition(label, value, mono ?? false));
  }
  const boundary = el("p", "command-boundary");
  boundary.textContent = "This command changes local retained state only. It does not publish, deploy, control hardware, or authenticate imported evidence.";
  const status = el("div", "dialog-status");
  status.setAttribute("aria-live", "polite");
  const controls = el("div", "dialog-actions");
  const cancel = button("Cancel", "button quiet");
  cancel.addEventListener("click", () => dialog.close());
  const confirm = button(mutation.confirmLabel, "button primary");
  const idempotencyKey = mutation.idempotencyPrefix === null
    ? null
    : `${mutation.idempotencyPrefix}:${crypto.randomUUID()}`;
  confirm.addEventListener("click", async () => {
    if (session === null) return;
    cancel.disabled = true;
    confirm.disabled = true;
    status.replaceChildren(el("p", "muted", "Submitting the frozen reviewed command once…"));
    const headers: Record<string, string> = { "X-ForgeGate-CSRF": session.csrf_token };
    if (idempotencyKey !== null) headers["Idempotency-Key"] = idempotencyKey;
    try {
      const response = await api<unknown>(mutation.endpoint, {
        method: "POST",
        headers,
        body: mutation.serializedBody ?? JSON.stringify(mutation.body)
      });
      heading.textContent = "Authoritative state updated";
      const eyebrow = review.querySelector<HTMLElement>(".eyebrow");
      if (eyebrow !== null) eyebrow.textContent = "WRITE COMPLETED";
      status.replaceChildren(
        statusBadge("Request completed"),
        el("p", undefined, mutation.completed(response))
      );
      const inspect = button("Reload authoritative state", "button primary");
      inspect.addEventListener("click", async () => {
        dialog.close();
        await reloadCandidateWorkspace(candidate.candidate_id);
      });
      controls.replaceChildren(inspect);
      inspect.focus();
    } catch (error) {
      showProblem(
        status,
        error,
        "Close this review, reload the candidate, and create a new reviewed command."
      );
      cancel.disabled = false;
      cancel.textContent = "Close and reload";
      cancel.addEventListener("click", () => void reloadCandidateWorkspace(candidate.candidate_id), { once: true });
      if (error instanceof RequestProblem && holdRateLimitedAction(dialog, confirm, error)) return;
    }
  });
  controls.append(cancel, confirm);
  review.append(details, boundary, status, controls);
  dialog.replaceChildren(review);
  confirm.focus();
}

async function reloadCandidateWorkspace(candidateId: string): Promise<void> {
  await renderCandidates();
  const workspace = document.querySelector<HTMLElement>("#workspace");
  if (workspace !== null) await showCandidateDetail(workspace, candidateId);
}

function transitionMutation(candidate: Candidate, toStatus: string): ReviewedMutation {
  const occurredAt = new Date().toISOString();
  const purpose: Record<string, string> = {
    COLLECTING: "Open the immutable candidate for retained evidence binding.",
    READY: "Record that the required evidence assembly is bound and ready for evaluation.",
    EVALUATING: "Freeze the transition into policy evaluation readiness."
  };
  return {
    title: `Advance candidate to ${toStatus}`,
    eyebrow: "REVIEWED LIFECYCLE COMMAND",
    summary: `${purpose[toStatus] ?? "Advance the candidate lifecycle."} The expected revision prevents stale writes.`,
    confirmLabel: `Confirm ${toStatus}`,
    endpoint: `/app/api/candidates/${encodeURIComponent(candidate.candidate_id)}/transitions`,
    body: {
      to_status: toStatus,
      expected_revision: candidate.revision,
      occurred_at: occurredAt,
      reason: `Dashboard reviewed transition to ${toStatus}`
    },
    idempotencyPrefix: `dashboard:transition:${candidate.candidate_id}:${toStatus.toLowerCase()}`,
    details: [
      ["Candidate", candidate.candidate_id, true],
      ["Current state", candidate.status],
      ["Target state", toStatus],
      ["Expected revision", String(candidate.revision)],
      ["Occurred at", formatDate(occurredAt)]
    ],
    completed: (response) => {
      if (!isJsonObject(response) || !isJsonObject(response.candidate)) {
        return "The command completed; reload to inspect the authoritative candidate.";
      }
      return `Candidate is now ${String(response.candidate.status)} at revision ${String(response.candidate.revision)}.`;
    }
  };
}

function attestMutation(candidate: Candidate): ReviewedMutation {
  const issuedAt = new Date().toISOString();
  return {
    title: "Generate durable release attestation",
    eyebrow: "REVIEWED ATTESTATION COMMAND",
    summary: "ForgeGate will bind the terminal candidate, transition chain, retained evidence, and exact policy evaluation into one immutable local attestation.",
    confirmLabel: "Confirm attestation",
    endpoint: `/app/api/candidates/${encodeURIComponent(candidate.candidate_id)}/attestation`,
    body: { issued_at: issuedAt },
    idempotencyPrefix: null,
    details: [
      ["Candidate", candidate.candidate_id, true],
      ["Terminal decision", candidate.status],
      ["Candidate revision", String(candidate.revision)],
      ["Issued at", formatDate(issuedAt)],
      ["Assurance", "unsigned_local"]
    ],
    completed: (response) => isJsonObject(response) && typeof response.attestation_id === "string"
      ? `Attestation ${shortHash(response.attestation_id)} is retained locally.`
      : "The attestation is retained locally; reload to inspect it."
  };
}

function openJsonCommandImport(
  main: HTMLElement,
  candidate: Candidate,
  kind: "evidence" | "policy",
  returnFocus?: HTMLElement
): void {
  const dialog = el("dialog", "review-dialog");
  dialog.setAttribute("aria-labelledby", "candidate-command-dialog-title");
  const form = el("form", "candidate-form");
  form.method = "dialog";
  const title = kind === "evidence" ? "Import evidence assembly" : "Import policy material";
  const heading = el("h2", undefined, title);
  heading.id = "candidate-command-dialog-title";
  const explanation = kind === "evidence"
    ? "Select one forgegate.evidence-bundle-assembly.v1 JSON document. Live device status is not accepted as release evidence."
    : "Select one forgegate.policy-material.v1 JSON document previously materialized from the candidate's frozen project profile.";
  form.append(el("p", "eyebrow", "LOCAL JSON IMPORT"), heading, el("p", "muted", explanation));
  const fieldWrap = el("label", "field file-field");
  fieldWrap.append(el("span", undefined, kind === "evidence" ? "Evidence assembly JSON" : "Policy material JSON"));
  const input = el("input");
  input.type = "file";
  input.accept = ".json,application/json";
  input.required = true;
  fieldWrap.append(input);
  const status = el("div", "dialog-status");
  status.setAttribute("aria-live", "polite");
  const controls = el("div", "dialog-actions");
  const cancel = button("Cancel", "button quiet");
  cancel.addEventListener("click", () => dialog.close());
  const review = button("Review imported document", "button primary");
  review.addEventListener("click", async () => {
    const file = input.files?.[0];
    if (file === undefined) {
      input.setCustomValidity("Select one JSON document.");
      input.reportValidity();
      return;
    }
    input.setCustomValidity("");
    if (file.size > MAX_DASHBOARD_IMPORT_BYTES) {
      showProblem(status, new RequestProblem(413, "DASHBOARD_IMPORT_TOO_LARGE", "The selected JSON document leaves insufficient room inside the 4 MiB request envelope.", "browser-side", null, "browser"), "Choose a JSON document no larger than 3,900,000 bytes.");
      return;
    }
    review.disabled = true;
    status.replaceChildren(el("p", "muted", "Parsing and fingerprinting the selected local document…"));
    try {
      const bytes = await file.arrayBuffer();
      const originalJson = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      const parsed: unknown = JSON.parse(originalJson);
      if (!isJsonObject(parsed)) throw new Error("The JSON root must be an object.");
      const fingerprint = await sha256Hex(bytes);
      const mutation = kind === "evidence"
        ? evidenceImportMutation(candidate, parsed, file, fingerprint)
        : policyImportMutation(candidate, parsed, file, fingerprint);
      const documentField = kind === "evidence" ? "assembly" : "policy_material";
      mutation.serializedBody = exactDocumentBody(mutation.body, documentField, originalJson);
      renderReviewedMutation(dialog, candidate, mutation);
    } catch (error) {
      const message = error instanceof Error ? error.message : "The selected file is not valid UTF-8 JSON.";
      showProblem(status, new RequestProblem(422, "DASHBOARD_IMPORT_INVALID", message, "browser-side", null, "browser"), "Choose the exact versioned JSON document and review it again.");
      review.disabled = false;
    }
  });
  controls.append(cancel, review);
  form.append(fieldWrap, el("p", "muted import-limit", "Maximum import size: 3,900,000 bytes. The browser reads the file locally and sends only the reviewed JSON document."), status, controls);
  dialog.append(form);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    dialog.close();
  });
  dialog.addEventListener("keydown", (event) => keepFocusInsideDialog(dialog, event));
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (returnFocus?.isConnected) returnFocus.focus();
  }, { once: true });
  main.append(dialog);
  dialog.showModal();
  input.focus();
}

function exactDocumentBody(body: Record<string, unknown>, field: string, originalJson: string): string {
  return `{${Object.entries(body).map(([key, value]) => `${JSON.stringify(key)}:${key === field ? originalJson : JSON.stringify(value)}`).join(",")}}`;
}

function sortedJsonValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortedJsonValue);
  if (isJsonObject(value)) return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, sortedJsonValue(item)]));
  return value;
}

type QuickReportFormat = "junit" | "coverage_xml" | "lcov" | "sarif" | "benchmark_json";

function detectQuickReport(content: ArrayBuffer): QuickReportFormat {
  const text = new TextDecoder("utf-8", {fatal: true}).decode(content).trim();
  // Routing only. The existing server collectors validate the complete original bytes.
  if (text.startsWith("{")) {
    const value: unknown = JSON.parse(text);
    if (isJsonObject(value)) {
      const sarif = value.version === "2.1.0" && "runs" in value;
      const benchmark = value.schema_version === "forgegate.benchmark.v1";
      if (sarif && benchmark) throw new Error("Ambiguous JSON report family.");
      if (sarif) return "sarif";
      if (benchmark) return "benchmark_json";
    }
  }
  const xml = text.replace(/^(?:\s|<\?xml[\s\S]*?\?>|<!--[\s\S]*?-->)+/, "");
  if (/^<testsuites?(?:\s|\/?>)/.test(xml)) return "junit";
  if (/^<coverage(?:\s|\/?>)/.test(xml)) return "coverage_xml";
  if (/^(?:TN:[^\r\n]*\r?\n)?SF:/m.test(text) && !text.startsWith("<")) return "lcov";
  throw new Error("Unsupported report. Select JUnit, Cobertura/LCOV, SARIF 2.1.0 or ForgeGate benchmark JSON.");
}

interface QuickReport {
  file: File;
  bytes: ArrayBuffer;
  format: QuickReportFormat;
  fingerprint: string;
  content_base64: string;
}

async function readQuickReports(files: File[]): Promise<QuickReport[]> {
  if (!files.length || files.length > 4) throw new Error("Select 1–4 report files; keep policy and unrelated files outside the report folder.");
  if (files.some(file => file.size < 1 || file.size > 1048576) || files.reduce((sum, file) => sum + file.size, 0) > 2097152) throw new Error("Reports allow 1 MiB per file and 2 MiB total.");
  const reports: QuickReport[] = [];
  const families = new Set<string>();
  for (const file of files) {
    const bytes = await file.arrayBuffer();
    if (bytes.byteLength !== file.size) throw new Error("Report changed while reading; select the files again.");
    const format = detectQuickReport(bytes);
    const family = format === "lcov" ? "coverage_xml" : format;
    const fingerprint = await sha256Hex(bytes);
    if (families.has(family) || reports.some(report => report.fingerprint === fingerprint)) throw new Error("Duplicate report family or bytes. Select one report per family, including only one coverage format.");
    families.add(family);
    let binary = "";
    for (const byte of new Uint8Array(bytes)) binary += String.fromCharCode(byte);
    reports.push({file, bytes, format, fingerprint, content_base64: btoa(binary)});
  }
  return reports;
}

async function quickReplayFiles(reports: QuickReport[], result: Record<string, unknown>): Promise<File[]> {
  const invalid = () => new Error("Exact original reports and receipts are unavailable for replay. Keep the original files and use the individual source-replay workflow.");
  if (!Array.isArray(result.collection_json) || result.collection_json.length !== reports.length || !isJsonObject(result.assembly) || !Array.isArray(result.assembly.collections)) throw invalid();
  const required = new Map<string, number>();
  for (const receipt of result.assembly.collections) {
    if (!isJsonObject(receipt) || !isJsonObject(receipt.source) || !Array.isArray(receipt.artifacts)) throw invalid();
    for (const ref of [receipt.source, ...receipt.artifacts]) {
      if (!isJsonObject(ref) || typeof ref.sha256 !== "string" || typeof ref.size_bytes !== "number") throw invalid();
      required.set(ref.sha256, ref.size_bytes);
    }
  }
  const files = [...reports.map(report => new File([report.bytes], report.file.name)), ...result.collection_json.map((text, index) => {
    if (typeof text !== "string") throw invalid();
    return new File([text], `collection-${index + 1}.json`, {type:"application/json"});
  })];
  const seen = new Set<string>();
  for (const file of files) {
    const digest = await sha256Hex(await file.arrayBuffer());
    if (required.get(digest) !== file.size || seen.has(digest)) throw invalid();
    seen.add(digest);
  }
  if (seen.size !== required.size || files.some(file => file.size > 1048576) || files.reduce((sum, file) => sum + file.size, 0) > 2097152) throw invalid();
  return files;
}

function openQuickAssessment(main: HTMLElement, initialCandidate: Candidate, returnFocus?: HTMLElement): void {
  const owner = session;
  if (owner?.principal.role !== "operator" || !["DRAFT", "COLLECTING"].includes(initialCandidate.status)) return;
  const route = window.location.hash;
  let candidate = initialCandidate;
  let busy = false;
  const dialog = el("dialog", "review-dialog");
  const form = el("form", "candidate-form");
  form.addEventListener("submit", event => event.preventDefault());
  const title = el("h2", undefined, "Quick assessment");
  title.id = "quick-assessment-title";
  dialog.setAttribute("aria-labelledby", title.id);
  const addField = (label: string, name: string, type: string, required = true) => {
    const item = field(label, name, "", type, required);
    form.append(item.wrapper);
    return item.input;
  };
  form.append(title, el("p", "muted", `${candidate.version} · ${candidate.project_id} · ${candidate.commit_sha}`),
    el("p", "muted", "1. Select reports → 2. Review parsed evidence → 3. Confirm assessment → 4. Download assurance."),
    el("p", "command-boundary", "Choose files or a folder containing only reports (1–4 files, 1 MiB each, 2 MiB total). Formats are detected from content. ZIP input is not supported. Source bytes remain declared evidence; keep originals for later replay."));
  const filesInput = addField("Report files", "quick-files", "file", false);
  filesInput.multiple = true;
  const folderInput = addField("Or select report folder", "quick-folder", "file", false);
  folderInput.multiple = true;
  folderInput.setAttribute("webkitdirectory", "");
  filesInput.addEventListener("change", () => { folderInput.value = ""; });
  folderInput.addEventListener("change", () => { filesInput.value = ""; });
  const policyInput = addField("Profile-authorized policy material JSON", "quick-policy", "file");
  policyInput.accept = ".json";
  const policyChoices = el("select"); policyChoices.id = "quick-policy-choice";
  policyChoices.append(Object.assign(el("option", undefined, "Choose a policy file"), {value:""}));
  const policyLabel = el("label", "field-label", "Saved policy for this profile and track"); policyLabel.htmlFor = policyChoices.id;
  const loadPolicies = button("Load saved policies");
  const policyNote = el("p", "muted", "Reuse a previously evaluated policy with this exact project profile and release track, or select a policy file.");
  form.append(policyLabel, policyChoices, loadPolicies, policyNote);
  const savedPolicies = new Map<string, File>();
  policyChoices.addEventListener("change", () => {
    policyInput.disabled = !!policyChoices.value;
    policyInput.required = !policyChoices.value;
  });
  const source = addField("JUnit / coverage source tool (same run)", "quick-tool", "text");
  const version = addField("JUnit / coverage tool version", "quick-tool-version", "text");
  const collected = addField("Original report time for this run (UTC offset)", "quick-time", "text");
  collected.placeholder = "2026-09-08T12:00:00Z";
  form.append(el("p", "muted", "Shared metadata is the default. For different tools or report times, expand the overrides below. SARIF and benchmark tool identities come from their reports."));
  const overrides = el("details");
  overrides.append(el("summary", undefined, "Per-report metadata overrides (optional)"));
  const overrideField = (label: string, name: string) => {
    const item = field(label, name, "", "text", false);
    item.input.value = "";
    overrides.append(item.wrapper);
    return item.input;
  };
  const coverageTool = overrideField("Coverage source tool override", "quick-coverage-tool");
  const coverageVersion = overrideField("Coverage tool version override", "quick-coverage-version");
  const reportTimes = {
    coverage: overrideField("Coverage report time override", "quick-coverage-time"),
    sarif: overrideField("SARIF report time override", "quick-sarif-time"),
    benchmark: overrideField("Benchmark report time override", "quick-benchmark-time")
  };
  form.append(overrides);
  const status = el("div", "dialog-status");
  status.setAttribute("aria-live", "polite");
  const controls = el("div", "dialog-actions");
  const close = button("Close", "button quiet");
  close.addEventListener("click", () => dialog.close());
  const preview = button(candidate.status === "DRAFT" ? "Start collection and preview" : "Preview batch", "button primary");
  controls.append(close, preview);
  form.append(status, controls);
  dialog.append(form);
  const current = () => dialog.open && dialog.isConnected && session === owner && window.location.hash === route;
  loadPolicies.addEventListener("click", async () => {
    if (busy || !current() || loadPolicies.disabled) return;
    loadPolicies.disabled = true;
    try {
      const response = await api<{candidate_id:string;choices:Array<{material:Record<string, unknown>;material_json:string}>;truncated:boolean}>(`/app/api/candidates/${encodeURIComponent(candidate.candidate_id)}/policy-choices`);
      if (!current()) return;
      if (response.candidate_id !== candidate.candidate_id || !Array.isArray(response.choices) || response.choices.length > 10) throw new Error("Policy choices do not match this candidate.");
      for (const choice of response.choices) {
        if (typeof choice.material_json !== "string" || JSON.stringify(sortedJsonValue(JSON.parse(choice.material_json))) !== JSON.stringify(sortedJsonValue(choice.material))) throw new Error("Saved policy bytes do not match their preview.");
        const file = new File([choice.material_json], "saved-policy.json", {type:"application/json"});
        if (file.size > 1048576) continue;
        policyImportMutation(candidate, choice.material, file, await sha256Hex(await file.arrayBuffer()));
        if (!current()) return;
        const id = String(choice.material.material_id);
        if (savedPolicies.has(id)) continue;
        savedPolicies.set(id, file);
        policyChoices.append(Object.assign(el("option", undefined, `${candidate.release_track} · ${id.slice(7, 19)}`), {value:id}));
      }
      policyNote.textContent = `${savedPolicies.size} reusable policies loaded. Select one and review its rules before assessment.${response.truncated ? " More exist; use an exact policy file for an unlisted material." : ""}${savedPolicies.size ? "" : " No compatible material is saved yet; select a policy file for this first run."}`;
    } catch (error) {
      if (current()) policyNote.textContent = `Saved policies could not be loaded. Select a policy file or try again. ${error instanceof RequestProblem ? error.code : ""}`;
    } finally { if (current() && !busy) loadPolicies.disabled = false; }
  });
  const assertCurrent = () => { if (!current()) throw new Error("Assessment stopped because the page or session changed. Inspect the candidate before continuing."); };
  const post = async <T>(endpoint: string, body: string, key: string | null = null): Promise<T> => {
    assertCurrent();
    const headers: Record<string, string> = {"X-ForgeGate-CSRF": owner.csrf_token};
    if (key !== null) headers["Idempotency-Key"] = key;
    const result = await api<T>(endpoint, {method: "POST", headers, body});
    assertCurrent();
    return result;
  };
  const path = `/app/api/candidates/${encodeURIComponent(candidate.candidate_id)}`;
  const inspect = () => {
    const link = el("a", "button secondary", "Inspect retained candidate");
    link.href = candidateReviewHash("evidence", candidate.candidate_id);
    controls.append(link);
  };
  const stop = (error: unknown) => {
    busy = false;
    if (!current()) return;
    close.disabled = false;
    controls.replaceChildren(close);
    inspect();
    status.append(el("p", "command-boundary", "Processing stopped. Completed steps remain retained; inspect the candidate before another attempt. No automatic retry occurs."));
    const problem = el("div"); status.append(problem);
    showProblem(problem, error, "Inspect retained candidate state before continuing.");
  };
  const advance = async (target: string) => {
    const prior = candidate;
    const mutation = transitionMutation(candidate, target);
    const result = await post<{candidate: Candidate}>(mutation.endpoint, JSON.stringify(mutation.body), `${mutation.idempotencyPrefix}:${crypto.randomUUID()}`);
    if (result.candidate?.candidate_id !== prior.candidate_id || result.candidate.commit_sha !== prior.commit_sha || result.candidate.project_id !== prior.project_id || result.candidate.status !== target || result.candidate.revision !== prior.revision + 1) throw new Error("Unexpected transition response. Inspect retained candidate state.");
    candidate = result.candidate;
    status.append(el("p", undefined, `Completed: ${target} · revision ${candidate.revision}`));
  };
  preview.addEventListener("click", async () => {
    if (busy || !current() || !form.reportValidity()) return;
    busy = true;
    preview.disabled = true;
    const inputs = [filesInput, folderInput, policyInput, policyChoices, loadPolicies, source, version, collected, coverageTool, coverageVersion, ...Object.values(reportTimes)];
    inputs.forEach(input => { input.disabled = true; });
    status.replaceChildren(el("p", "muted", "Reading and identifying selected files…"));
    try {
      const direct = Array.from(filesInput.files ?? []), folder = Array.from(folderInput.files ?? []);
      if (direct.length && folder.length) throw new Error("Select files or a folder, not both.");
      const reports = await readQuickReports(direct.length ? direct : folder);
      const policyFile = savedPolicies.get(policyChoices.value) ?? policyInput.files?.[0];
      if (!policyFile || policyFile.size < 1 || policyFile.size > 1048576) throw new Error("Select policy material JSON up to 1 MiB.");
      const policyBytes = await policyFile.arrayBuffer();
      if (policyBytes.byteLength !== policyFile.size) throw new Error("Policy file changed while reading.");
      const policyText = new TextDecoder("utf-8", {fatal: true}).decode(policyBytes);
      const policy: unknown = JSON.parse(policyText);
      if (!isJsonObject(policy)) throw new Error("Policy material must be a JSON object.");
      const policyHash = await sha256Hex(policyBytes);
      policyImportMutation(candidate, policy, policyFile, policyHash);
      if (!source.value.trim() || !version.value.trim()) throw new Error("Provide the source tool and version for this run.");
      if (!/(Z|[+-]\d{2}:\d{2})$/i.test(collected.value) || !Number.isFinite(Date.parse(collected.value)) || Date.parse(collected.value) > Date.now()) throw new Error("Provide the original report time with a UTC offset, not a future time.");
      if (!!coverageTool.value.trim() !== !!coverageVersion.value.trim()) throw new Error("Provide both coverage tool and version overrides, or leave both blank.");
      const requestReports = reports.map(report => {
        const coverage = ["coverage_xml", "lcov"].includes(report.format);
        const embedded = ["sarif", "benchmark_json"].includes(report.format);
        const override = coverage ? reportTimes.coverage : report.format === "sarif" ? reportTimes.sarif : report.format === "benchmark_json" ? reportTimes.benchmark : null;
        const time = override?.value.trim() || collected.value;
        if (!/(Z|[+-]\d{2}:\d{2})$/i.test(time) || !Number.isFinite(Date.parse(time)) || Date.parse(time) > Date.now()) throw new Error("Every report time must include a UTC offset and must not be in the future.");
        return {format: report.format, content_base64: report.content_base64,
          source_tool: embedded ? "report-embedded" : coverage && coverageTool.value.trim() ? coverageTool.value.trim() : source.value.trim(),
          source_version: embedded ? "report-embedded" : coverage && coverageVersion.value.trim() ? coverageVersion.value.trim() : version.value.trim(), collected_at: time};
      });
      assertCurrent();
      status.replaceChildren(el("h3", undefined, "Detected reports"));
      const table = el("table");
      const head = el("tr");
      for (const label of ["File", "Format", "Bytes", "SHA-256"]) head.append(el("th", undefined, label));
      table.append(head);
      for (const report of reports) {
        const row = el("tr");
        for (const value of [report.file.name, report.format, String(report.file.size), report.fingerprint]) row.append(el("td", "mono", value));
        table.append(row);
      }
      for (const report of requestReports) status.append(el("p", "muted", `${report.format} · ${report.source_tool} ${report.source_version} · ${report.collected_at}`));
      const wrap = el("div", "table-wrap"); wrap.append(table); status.append(wrap);
      status.append(el("p", "muted", `Policy SHA-256: ${policyHash}`));
      if (isJsonObject(policy.policy) && Array.isArray(policy.policy.rules)) {
        status.append(el("h3", undefined, `Selected policy: ${String(policy.policy.name)} · ${policy.policy.rules.length} rules`));
        for (const rule of policy.policy.rules.slice(0, 25)) if (isJsonObject(rule)) {
          const where = isJsonObject(rule.where) ? rule.where : {};
          status.append(el("p", undefined, `${String(rule.id)} · ${String(rule.evidence_kind)} / ${String(where.field ?? rule.aggregation)} ${String(rule.operator).replaceAll("_", " ")} ${JSON.stringify(rule.expected)} · missing: ${String(rule.on_missing)}`));
        }
        if (policy.policy.rules.length > 25) status.append(el("p", "muted", "Showing first 25 rules. Review the selected policy file for the full rule set."));
      }
      if (candidate.status === "DRAFT") await advance("COLLECTING");
      const command = {expected_revision: candidate.revision, reported_commit: candidate.commit_sha,
        reports: requestReports, retain_warnings: false};
      const result = await post<Record<string, unknown>>(`${path}/collection-preview`, JSON.stringify(command));
      const finishPreview = async (result: Record<string, unknown>, warningsReviewed = false): Promise<void> => {
      assertCurrent();
      if (result.candidate_id !== candidate.candidate_id || result.expected_revision !== candidate.revision || !Array.isArray(result.collections) || result.collections.length !== reports.length) throw new Error("Unexpected preview identity or report count.");
      let warningCount = 0;
      for (const [index, raw] of result.collections.entries()) {
        const report = reports[index];
        if (!report || !isJsonObject(raw) || !Array.isArray(raw.artifacts) || !raw.artifacts.some(item => isJsonObject(item) && item.sha256 === report.fingerprint && item.size_bytes === report.file.size)) throw new Error("Preview source hash does not match the selected bytes.");
        status.append(el("h3", undefined, `${report.format}: ${String(raw.status)}`));
        for (const issue of [...(Array.isArray(raw.warnings) ? raw.warnings : []), ...(Array.isArray(raw.rejected_records) ? raw.rejected_records : [])].slice(0, 25)) {
          if (isJsonObject(issue)) status.append(el("p", "command-boundary", `${String(issue.code)}: ${String(issue.message)}`));
        }
        if (Array.isArray(raw.evidence)) for (const record of raw.evidence.slice(0, 25)) {
          if (isJsonObject(record)) status.append(el("p", "mono", `${String(record.kind)} · ${String(record.scope)} · ${JSON.stringify(record.value)}`));
        }
        if (raw.status !== "COMPLETE" || !Array.isArray(raw.warnings) || !Array.isArray(raw.rejected_records) || raw.rejected_records.length || raw.warnings.length > 25) {
          throw new RequestProblem(
            422,
            "DASHBOARD_QUICK_REPORT_REVIEW_REQUIRED",
            "A report was rejected or its warning list exceeds the review limit. No partial selection will be bound; use the individual workflow or CLI.",
            "browser-side",
            null,
            "browser"
          );
        }
        warningCount += raw.warnings.length;
      }
      if (warningCount && !warningsReviewed) {
        status.append(el("p", "command-boundary", `${warningCount} collector warning(s) require explicit review. Retaining them preserves their limitations; it does not fix them or change policy thresholds.`));
        const consentLabel = el("label", "field");
        const consent = el("input"); consent.type = "checkbox";
        consentLabel.append(consent, el("span", undefined, "I reviewed these collector warnings and want to retain them unchanged."));
        status.append(consentLabel);
        const retain = button("Retain reviewed warnings and preview", "button primary");
        controls.replaceChildren(close, retain);
        busy = false;
        retain.addEventListener("click", async () => {
          if (busy || retain.disabled || !current()) return;
          if (!consent.checked) { consent.setCustomValidity("Review and acknowledge the displayed warnings first."); consent.reportValidity(); return; }
          consent.setCustomValidity(""); busy = true; retain.disabled = consent.disabled = true;
          try {
            const reviewed = await post<Record<string, unknown>>(`${path}/collection-preview`, JSON.stringify({...command, retain_warnings:true}));
            if (JSON.stringify(sortedJsonValue(reviewed.collections)) !== JSON.stringify(sortedJsonValue(result.collections)) || JSON.stringify(reviewed.collection_json) !== JSON.stringify(result.collection_json)) throw new Error("Collection results changed after warning review. Inspect the candidate and start a new review.");
            await finishPreview(reviewed, true);
          } catch (error) { stop(error); }
        });
        consent.focus(); return;
      }
      const assembly = result.assembly;
      if (!isJsonObject(assembly) || typeof result.assembly_json !== "string" || JSON.stringify(sortedJsonValue(JSON.parse(result.assembly_json))) !== JSON.stringify(sortedJsonValue(assembly))) throw new Error("Missing or inconsistent exact assembly JSON.");
      const assemblyText = result.assembly_json;
      evidenceImportMutation(candidate, assembly, reports[0]!.file, reports[0]!.fingerprint);
      let originals: File[] | undefined;
      try {
        originals = await quickReplayFiles(reports, result);
        assertCurrent();
        status.append(el("p", "muted", `${originals.length} original source files (reports plus exact collection receipts) are held for this dialog. After assessment, save the private replay ZIP before closing to retain them.`));
      } catch {
        status.append(el("p", "command-boundary", "Automatic source handoff is unavailable: exact receipts and reports must fit 1 MiB per file / 2 MiB total. Assessment can continue; retain originals for the individual replay workflow."));
      }
      status.append(el("p", "command-boundary", "Confirming will bind this complete selection immutably, mark it READY, evaluate the selected policy, and generate an unsigned local attestation for the actual decision. Missing policy evidence can produce REVIEW. Review included reports before continuing."));
      const confirm = button("Confirm assessment and attestation", "button primary");
      controls.replaceChildren(close, confirm);
      busy = false;
      let submitted = false;
      confirm.addEventListener("click", async () => {
        if (busy || submitted || !current()) return;
        busy = submitted = true;
        confirm.disabled = close.disabled = true;
        try {
          const binding = evidenceImportMutation(candidate, assembly, reports[0]!.file, reports[0]!.fingerprint);
          await post(binding.endpoint, exactDocumentBody(binding.body, "assembly", assemblyText), `${binding.idempotencyPrefix}:${crypto.randomUUID()}`);
          status.append(el("p", undefined, "Completed: immutable evidence binding"));
          await advance("READY");
          await advance("EVALUATING");
          const evaluation = policyImportMutation(candidate, policy, policyFile, policyHash);
          await post(evaluation.endpoint, exactDocumentBody(evaluation.body, "policy_material", policyText), `${evaluation.idempotencyPrefix}:${crypto.randomUUID()}`);
          const review = await api<CandidateAssuranceReview>(`${path}/assurance-review`);
          assertCurrent();
          if (review.candidate.candidate_id !== candidate.candidate_id || review.candidate.commit_sha !== candidate.commit_sha || review.candidate.revision !== candidate.revision + 1 || !["PASS", "FAIL", "REVIEW", "ERROR"].includes(review.candidate.status)) throw new Error("Evaluation readback did not match this candidate.");
          candidate = review.candidate;
          status.append(el("h3", undefined, `Engineering decision: ${candidate.status}`));
          for (const rule of review.policy_evaluation?.rule_results ?? []) {
            status.append(el("p", undefined, `${rule.rule_id}: ${rule.decision} · actual ${JSON.stringify(rule.actual)} / expected ${JSON.stringify(rule.expected)} · ${rule.explanation}`));
          }
          const attestation = attestMutation(candidate);
          await post(attestation.endpoint, JSON.stringify(attestation.body));
          const completed = await api<CandidateAssuranceReview>(`${path}/assurance-review`);
          assertCurrent();
          if (completed.candidate.candidate_id !== candidate.candidate_id || completed.candidate.commit_sha !== candidate.commit_sha || completed.candidate.evaluation_id !== candidate.evaluation_id || !completed.attestation || !completed.assurance_bundle_id) throw new Error("Attestation readback unavailable; inspect Assurance.");
          status.append(el("p", undefined, "Completed: attestation retained. The assurance package is ready to review and download."));
          const download = button("Review assurance download", "button primary");
          download.addEventListener("click", () => { openAssuranceExportDialog(main, completed, download); });
          controls.replaceChildren(close, download);
          if (originals) {
            const replay = button("Save originals for offline replay", "button primary");
            replay.addEventListener("click", () => openReplayExportDialog(main, completed, replay, originals));
            controls.append(replay);
          }
          inspect(); close.disabled = false; busy = false; download.focus();
        } catch (error) { stop(error); }
      });
      confirm.focus();
      };
      await finishPreview(result);
    } catch (error) { stop(error); }
  });
  dialog.addEventListener("cancel", event => { event.preventDefault(); if (!busy) dialog.close(); });
  dialog.addEventListener("keydown", event => keepFocusInsideDialog(dialog, event));
  dialog.addEventListener("close", () => { dialog.remove(); if (returnFocus?.isConnected) returnFocus.focus(); }, {once: true});
  main.append(dialog); dialog.showModal(); filesInput.focus();
}

function openJUnitImport(main: HTMLElement, candidate: Candidate, returnFocus?: HTMLElement, multi = false, durable = false): void {
  const invalid = (message: string): RequestProblem => new RequestProblem(422, multi ? "DASHBOARD_COLLECTION_INVALID" : "DASHBOARD_JUNIT_INVALID", message, "browser-side", null, "browser");
  const dialog = el("dialog", "review-dialog");
  dialog.setAttribute("aria-labelledby", "candidate-command-dialog-title");
  const heading = el("h2", undefined, durable ? "Prepare durable report task" : multi ? "Collect standard CI reports" : "Collect JUnit report");
  heading.id = "candidate-command-dialog-title";
  const form = el("form", "candidate-form");
  form.addEventListener("submit", (event) => event.preventDefault());
  form.append(el("p", "eyebrow", "BOUNDED RAW REPORT PREVIEW"), heading,
    el("p", "muted", durable ? "Preview first, then separately confirm durable submission. Maximum 1 MiB per report. Submission retains raw bytes in the configured private job store until a terminal state; no encryption or secure erasure is promised. Execution needs another confirmation. Evidence stays unsigned_local / declared." : "Select reports, then review before binding. Maximum 1 MiB per report. No server path, device access, or test execution. Uploaded results remain unsigned_local / declared; source bytes are not retained."),
    el("p", "command-boundary", durable ? "The complete selection must pass preview before browser submission. The queued task will parse these same bytes again only after separate execution confirmation. Matching source-commit declarations are not authenticated provenance." : multi ? "Select one JUnit and one coverage report. All reports must parse successfully; no partial selection is bound. Matching source-commit declarations are not authenticated provenance." : "Binding is immutable and contains only this report. Policies requiring other reports or stronger verification may reject it. Use combined test + coverage collection or CLI assembly when needed."));
  const field = (label: string, type: string, value = ""): HTMLInputElement => {
    const wrap = el("label", "field");
    const input = el("input");
    input.type = type;
    input.required = true;
    input.value = value;
    wrap.append(el("span", undefined, label), input);
    form.append(wrap);
    return input;
  };
  const fileInput = field("JUnit XML report", "file");
  fileInput.accept = ".xml,application/xml,text/xml";
  const commit = field("Reported source commit — confirm association", "text", candidate.commit_sha);
  const tool = field("Reported source tool", "text");
  const version = field("Reported source version", "text");
  tool.maxLength = version.maxLength = 120;
  const time = field("Original report collection time (ISO 8601 with UTC offset)", "text");
  time.placeholder = "2026-09-06T12:00:00Z";
  const coverage = multi ? {
    file: field("Coverage report (Cobertura XML or LCOV)", "file"),
    tool: field("Coverage source tool", "text"),
    version: field("Coverage source version", "text"),
    time: field("Original coverage collection time (ISO 8601 with UTC offset)", "text")
  } : null;
  const format = el("select");
  if (coverage !== null) {
    coverage.file.accept = ".xml,.info,.lcov,text/plain";
    coverage.tool.maxLength = coverage.version.maxLength = 120;
    const wrap = el("label", "field");
    for (const [value, label] of [["coverage_xml", "Cobertura XML"], ["lcov", "LCOV"]] as const) {
      const option = el("option", undefined, label);
      option.value = value;
      format.append(option);
    }
    format.value = "coverage_xml";
    wrap.append(el("span", undefined, "Coverage format — select explicitly"), format);
    form.append(wrap);
  }
  const supplements = multi ? [
    {format: "sarif", label: "Security scan — SARIF 2.1.0", accept: ".sarif,.json,application/json"},
    {format: "benchmark_json", label: "Performance — ForgeGate benchmark JSON", accept: ".json,application/json"}
  ].map((item) => {
    const file = field(`${item.label} (optional)`, "file");
    file.accept = item.accept;
    file.required = false;
    const time = field(`${item.label}: original collection time (UTC offset)`, "text");
    time.required = false;
    return {...item, file, time};
  }) : [];
  if (multi) form.append(el("p", "command-boundary", "Include security and performance reports here when your policy requires them: binding cannot be extended later. Maximum 2 MiB for the complete selection. SARIF and benchmark tool identities come from the report itself, not the test/coverage fields. A successful parser does not mean a passing scan or benchmark."));
  const status = el("div", "dialog-status");
  status.setAttribute("aria-live", "polite");
  const controls = el("div", "dialog-actions");
  const cancel = button("Close preview", "button quiet");
  cancel.addEventListener("click", () => dialog.close());
  const collect = button(multi ? "Preview reports — no binding" : "Preview report — no binding", "button primary");
  controls.append(cancel, collect);
  form.append(status, controls);
  dialog.append(form);
  dialog.addEventListener("cancel", (event) => { event.preventDefault(); dialog.close(); });
  dialog.addEventListener("keydown", (event) => keepFocusInsideDialog(dialog, event));
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (returnFocus?.isConnected) returnFocus.focus();
  }, { once: true });
  const owner = session;
  const route = window.location.hash;
  const current = (): boolean => dialog.open && dialog.isConnected && session === owner && window.location.hash === route;
  collect.addEventListener("click", async () => {
    if (!form.reportValidity() || session === null || !current()) return;
    collect.disabled = true;
    for (const input of [fileInput, commit, tool, version, time]) input.disabled = true;
    if (coverage !== null) for (const input of Object.values(coverage)) input.disabled = true;
    for (const item of supplements) { item.file.disabled = true; item.time.disabled = true; }
    format.disabled = true;
    status.replaceChildren(el("p", "muted", "Reading the selected report. Closing discards the preview; an already submitted server request may finish."));
    const file = fileInput.files?.[0];
    try {
      const selectedFiles = [file, coverage?.file.files?.[0], ...supplements.map(item => item.file.files?.[0])];
      if (selectedFiles.reduce((total, item) => total + (item?.size ?? 0), 0) > 2097152) throw invalid("The complete report selection must not exceed 2 MiB.");
      if (file === undefined || file.size === 0 || file.size > 1048576) throw invalid("Choose one non-empty XML file no larger than 1 MiB.");
      if (commit.value !== candidate.commit_sha) throw invalid("Reported commit must match this candidate. A matching declaration does not authenticate the report.");
      if (!/(Z|[+-]\d{2}:\d{2})$/i.test(time.value) || !Number.isFinite(Date.parse(time.value)) || Date.parse(time.value) > Date.now()) throw invalid("Provide the original collection time with a UTC offset, not a future time.");
      const bytes = await file.arrayBuffer();
      const fingerprint = await sha256Hex(bytes);
      if (!current()) return;
      let binary = "";
      for (const byte of new Uint8Array(bytes)) binary += String.fromCharCode(byte);
      const command = {
        expected_revision: candidate.revision, reported_commit: commit.value,
        content_base64: btoa(binary), source_tool: tool.value, source_version: version.value,
        collected_at: time.value, retain_warnings: false
      };
      const sources = [{file, fingerprint, size: bytes.byteLength, format: "junit"}];
      const reports = [{format: "junit", content_base64: command.content_base64, source_tool: tool.value, source_version: version.value, collected_at: time.value}];
      if (coverage !== null) {
        const coverageFile = coverage.file.files?.[0];
        if (coverageFile === undefined || coverageFile.size === 0 || coverageFile.size > 1048576) throw invalid("Choose one non-empty coverage file no larger than 1 MiB.");
        if (!["coverage_xml", "lcov"].includes(format.value)) throw invalid("Select a supported coverage format.");
        if (!/(Z|[+-]\d{2}:\d{2})$/i.test(coverage.time.value) || !Number.isFinite(Date.parse(coverage.time.value)) || Date.parse(coverage.time.value) > Date.now()) throw invalid("Provide the original coverage collection time with a UTC offset, not a future time.");
        const coverageBytes = await coverageFile.arrayBuffer();
        const coverageHash = await sha256Hex(coverageBytes);
        if (!current()) return;
        if (coverageHash === fingerprint) throw invalid("Duplicate report bytes cannot be used as test and coverage evidence.");
        let encoded = "";
        for (const byte of new Uint8Array(coverageBytes)) encoded += String.fromCharCode(byte);
        reports.push({format: format.value, content_base64: btoa(encoded), source_tool: coverage.tool.value, source_version: coverage.version.value, collected_at: coverage.time.value});
        sources.push({file: coverageFile, fingerprint: coverageHash, size: coverageBytes.byteLength, format: format.value});
      }
      for (const item of supplements) {
        const selected = item.file.files?.[0];
        if (selected === undefined) {
          if (item.time.value.trim()) throw invalid(`Select the ${item.label} report or clear its collection time.`);
          continue;
        }
        if (selected.size === 0 || selected.size > 1048576) throw invalid(`${item.label} must contain 1 byte to 1 MiB.`);
        if (!/(Z|[+-]\d{2}:\d{2})$/i.test(item.time.value) || !Number.isFinite(Date.parse(item.time.value)) || Date.parse(item.time.value) > Date.now()) throw invalid(`Provide the original ${item.label} time with a UTC offset, not a future time.`);
        const content = await selected.arrayBuffer();
        if (content.byteLength !== selected.size) throw invalid("Selected report size changed; reopen the selection.");
        const digest = await sha256Hex(content);
        if (!current()) return;
        if (sources.some(source => source.fingerprint === digest)) throw invalid("Duplicate report bytes are not allowed.");
        let encoded = "";
        for (const byte of new Uint8Array(content)) encoded += String.fromCharCode(byte);
        reports.push({format: item.format, content_base64: btoa(encoded), source_tool: "report-embedded", source_version: "report-embedded", collected_at: item.time.value});
        sources.push({file: selected, fingerprint: digest, size: content.byteLength, format: item.format});
      }
      const preview = async (retainWarnings: boolean): Promise<void> => {
        if (!current() || owner === null) return;
        controls.replaceChildren(cancel);
        status.replaceChildren(el("p", "muted", "Parsing with the bounded server collector; no candidate state is being changed…"));
        try {
          const result = await api<Record<string, unknown>>(`/app/api/candidates/${encodeURIComponent(candidate.candidate_id)}/${multi || durable ? "collection-preview" : "junit-preview"}`, {
            method: "POST", headers: { "X-ForgeGate-CSRF": owner.csrf_token },
            body: JSON.stringify(multi || durable ? {expected_revision: candidate.revision, reported_commit: command.reported_commit, reports, retain_warnings: retainWarnings} : { ...command, retain_warnings: retainWarnings })
          });
          if (!current()) return;
          if (result.schema_version !== (multi || durable ? "forgegate.dashboard-collection-preview.v1" : "forgegate.dashboard-junit-preview.v1") || result.candidate_id !== candidate.candidate_id || result.expected_revision !== candidate.revision) throw invalid("Unexpected preview identity; nothing was bound.");
          const collections = multi || durable ? result.collections : [result.collection];
          if (!Array.isArray(collections) || collections.length !== sources.length || !collections.every(isJsonObject)) throw invalid("Unexpected preview report count; nothing was bound.");
          status.replaceChildren(el("p", "muted", "Preview only — not retained. Original report time and caller-declared source metadata are preserved."));
          let allComplete = true;
          let warningCount = 0;
          let allIssuesVisible = true;
          for (const [index, collection] of collections.entries()) {
            const source = sources[index];
            if (source === undefined) throw invalid("Missing source association; nothing was bound.");
            const artifacts = Array.isArray(collection.artifacts) ? collection.artifacts : [];
            if (artifacts.length !== 1 || !isJsonObject(artifacts[0]) || artifacts[0].sha256 !== source.fingerprint || artifacts[0].size_bytes !== source.size) throw invalid("Preview report hash or size mismatch; nothing was bound.");
            status.append(el("h3", undefined, `${source.format}: Collection ${String(collection.status)} — not a release decision`),
              definition("Selected report", source.file.name), definition("Report SHA-256", source.fingerprint, true));
            const records = Array.isArray(collection.evidence) ? collection.evidence : [];
            for (const record of records.slice(0, 25)) {
              if (isJsonObject(record)) status.append(
                el("h4", undefined, `${String(record.kind ?? "Evidence")} · ${String(record.scope ?? "unspecified scope")}`),
                el("pre", "mono", JSON.stringify(record.value, null, 2))
              );
            }
            if (records.length > 25) status.append(el("p", "muted", `Showing 25 of ${records.length} records. The assembly includes all records.`));
            const warnings = Array.isArray(collection.warnings) ? collection.warnings : [];
            const rejected = Array.isArray(collection.rejected_records) ? collection.rejected_records : [];
            allComplete = allComplete && collection.status === "COMPLETE";
            warningCount += warnings.length;
            const issues = [...warnings, ...rejected];
            allIssuesVisible = allIssuesVisible && issues.length <= 25;
            for (const issue of issues.slice(0, 25)) {
              if (isJsonObject(issue)) status.append(el("p", "command-boundary", `${String(issue.code)}: ${String(issue.message)}`));
            }
            if (issues.length > 25) status.append(el("p", "muted", `Showing 25 of ${issues.length} issues. Use the CLI to inspect all issues before retaining warnings.`));
          }
          if (isJsonObject(result.assembly) && allComplete && (warningCount === 0 || retainWarnings)) {
            const assembly = result.assembly;
            const assemblyJson = result.assembly_json;
            if (typeof assemblyJson !== "string" || JSON.stringify(sortedJsonValue(JSON.parse(assemblyJson))) !== JSON.stringify(sortedJsonValue(assembly))) throw invalid("Missing or mismatched exact assembly JSON; nothing was bound.");
            const review = button(durable ? "Review durable submission" : "Review immutable binding", "button primary");
            review.addEventListener("click", () => {
              if (!current()) return;
              if (durable) {
                renderJobSubmission(dialog, candidate, {
                  expected_revision: candidate.revision, reported_commit: command.reported_commit,
                  reports, retain_warnings: retainWarnings
                }, sources, warningCount);
                return;
              }
              const mutation = evidenceImportMutation(candidate, assembly, file, fingerprint);
              mutation.serializedBody = exactDocumentBody(mutation.body, "assembly", assemblyJson);
              mutation.summary = `Bind this ${multi ? "standard CI report" : "single-report"} assembly. Source bytes are not retained, reported metadata is unverified, and evidence stays unsigned_local / declared. This does not mark the candidate READY or PASS.`;
              mutation.details = mutation.details.map(([label, value, mono]) => [label === "Selected file SHA-256" ? "Original report SHA-256" : label, value, mono ?? false]);
              for (const source of sources.slice(1)) {
                const label = ["lcov", "coverage_xml"].includes(source.format) ? "Coverage report" : source.format;
                mutation.details.push([label, `${source.file.name} · ${source.size} bytes`], [`${label} SHA-256`, source.fingerprint, true]);
              }
              renderReviewedMutation(dialog, candidate, mutation);
            });
            controls.append(review);
            review.focus();
          } else if (allComplete && allIssuesVisible && warningCount > 0 && !retainWarnings) {
            const retain = button("Retain these warnings and preview again", "button primary");
            retain.addEventListener("click", () => { retain.disabled = true; void preview(true); });
            controls.append(retain);
            retain.focus();
          }
        } catch (error) {
          if (!current()) return;
          handleProtectedProblem(status, error, "Close and reopen collection to retry manually. Nothing was bound by this preview.");
        }
      };
      await preview(false);
    } catch (error) {
      if (!current()) return;
      showProblem(status, error, "Close and reopen collection with a valid report and source metadata.");
    }
  });
  main.append(dialog);
  dialog.showModal();
  fileInput.focus();
}

function renderJobSubmission(
  dialog: HTMLDialogElement, candidate: Candidate, collection: Record<string, unknown>,
  sources: Array<{file: File; fingerprint: string; size: number; format: string}>, warningCount: number
): void {
  const owner = session;
  if (owner?.principal.role !== "operator") return;
  const route = window.location.hash;
  const current = () => dialog.open && dialog.isConnected && session === owner && window.location.hash === route;
  const body = JSON.stringify({candidate_id: candidate.candidate_id, collection});
  const key = `dashboard:job:${crypto.randomUUID()}`;
  const panel = el("section", "review-panel");
  const heading = el("h2", undefined, "Confirm durable task submission");
  heading.id = "candidate-command-dialog-title";
  panel.append(heading, el("p", "command-boundary", "This writes one QUEUED task and retains the exact report bytes in the configured private job store. It does not execute, bind evidence or change the candidate. Raw bytes are not encrypted; terminal logical release is not secure erasure. A lost response may still mean the task was created; inspect Jobs before making another submission."));
  const details = el("dl", "definition-list");
  details.append(definition("Project", candidate.project_id), definition("Candidate", candidate.candidate_id, true), definition("Reviewed candidate revision", String(candidate.revision)), definition("Reported commit", candidate.commit_sha, true), definition("Warnings explicitly retained", String(warningCount)), definition("Idempotency key", key, true));
  for (const source of sources) details.append(definition("Report", `${source.format} · ${source.file.name} · ${source.size} bytes`), definition("Exact report SHA-256", source.fingerprint, true));
  if (Array.isArray(collection.reports)) for (const report of collection.reports) {
    if (isJsonObject(report)) details.append(definition("Declared source", `${report.source_tool} · ${report.source_version}`), definition("Declared collection time", String(report.collected_at)));
  }
  const status = el("div", "dialog-status");
  status.setAttribute("aria-live", "polite");
  const controls = el("div", "dialog-actions");
  const back = button("Back without submission", "button quiet");
  back.addEventListener("click", () => dialog.close());
  const confirm = button("Confirm task submission", "button primary");
  let submitted = false;
  confirm.addEventListener("click", async () => {
    if (!current() || submitted) return;
    submitted = true;
    confirm.disabled = back.disabled = true;
    status.replaceChildren(el("p", "muted", "Submitting the frozen report selection once…"));
    try {
      const result = await api<CollectionJob>(`/app/api/jobs?${new URLSearchParams({project_id: candidate.project_id})}`, {
        method: "POST", headers: {"X-ForgeGate-CSRF": owner.csrf_token, "Idempotency-Key": key}, body
      });
      if (!current()) return;
      if (!/^job-[0-9a-f]{32}$/.test(result.job_id) || result.candidate_id !== candidate.candidate_id || result.project_id !== candidate.project_id) throw new Error("Unexpected submission identity; inspect Jobs before any new write.");
      status.replaceChildren(el("p", undefined, `Retained ${result.state} at revision ${result.revision}. No execution was started by submission.`));
      const inspect = el("a", "button primary", "Inspect submitted task");
      inspect.href = jobsHash(candidate.project_id, candidate.candidate_id, "", result.job_id);
      controls.replaceChildren(inspect);
      inspect.focus();
    } catch (error) {
      if (!current()) return;
      handleProtectedProblem(status, error, "Outcome may be uncertain. Inspect Jobs before submitting again. No automatic retry occurs.");
      const close = button("Close and inspect Jobs", "button secondary");
      close.addEventListener("click", () => { dialog.close(); window.location.hash = jobsHash(candidate.project_id, candidate.candidate_id); });
      controls.replaceChildren(close);
      close.focus();
    }
  });
  controls.append(back, confirm);
  panel.append(details, status, controls);
  dialog.replaceChildren(panel);
  back.focus();
}

function evidenceImportMutation(
  candidate: Candidate,
  assembly: Record<string, unknown>,
  file: File,
  fingerprint: string
): ReviewedMutation {
  if (assembly.schema_version !== "forgegate.evidence-bundle-assembly.v1") {
    throw new Error("Expected schema_version forgegate.evidence-bundle-assembly.v1.");
  }
  const bundle = assembly.bundle;
  if (!isJsonObject(bundle) || bundle.candidate_commit !== candidate.commit_sha) {
    throw new Error("The assembly candidate_commit must exactly match this candidate.");
  }
  const evidence = Array.isArray(bundle.evidence) ? bundle.evidence : [];
  const collections = Array.isArray(assembly.collections) ? assembly.collections : [];
  const warningDisposition = typeof assembly.warning_disposition === "string"
    ? assembly.warning_disposition
    : "unavailable";
  const boundAt = new Date().toISOString();
  return {
    title: "Bind immutable evidence assembly",
    eyebrow: "REVIEWED EVIDENCE WRITE",
    summary: "ForgeGate will validate every nested fingerprint, receipt, artifact reference, evidence ID, and candidate commit before retaining one immutable binding.",
    confirmLabel: "Confirm evidence binding",
    endpoint: `/app/api/candidates/${encodeURIComponent(candidate.candidate_id)}/evidence`,
    body: { assembly, bound_at: boundAt },
    idempotencyPrefix: `dashboard:evidence:${candidate.candidate_id}`,
    details: [
      ["Candidate", candidate.candidate_id, true],
      ["Candidate commit", candidate.commit_sha, true],
      ["Assembly ID", String(assembly.assembly_id ?? "missing"), true],
      ["Evidence records", String(evidence.length)],
      ["Collector receipts", String(collections.length)],
      ["Warning disposition", warningDisposition],
      ["Selected file", `${file.name} · ${file.size} bytes`],
      ["Selected file SHA-256", fingerprint, true],
      ["Bound at", formatDate(boundAt)]
    ],
    completed: () => "The evidence binding is retained. Candidate revision is unchanged until the READY transition is separately reviewed."
  };
}

function policyImportMutation(
  candidate: Candidate,
  material: Record<string, unknown>,
  file: File,
  fingerprint: string
): ReviewedMutation {
  if (material.schema_version !== "forgegate.policy-material.v1") {
    throw new Error("Expected schema_version forgegate.policy-material.v1.");
  }
  if (material.release_track !== candidate.release_track) {
    throw new Error("The policy material release_track must exactly match this candidate.");
  }
  if (material.project_profile_id !== candidate.project_profile_id) {
    throw new Error("The policy material project_profile_id must match this candidate.");
  }
  if (material.project_profile_version !== candidate.project_profile_version) {
    throw new Error("The policy material project_profile_version must match this candidate.");
  }
  const policy = material.policy;
  const rules = isJsonObject(policy) && Array.isArray(policy.rules) ? policy.rules : [];
  const evaluatedAt = new Date().toISOString();
  return {
    title: "Evaluate retained evidence",
    eyebrow: "REVIEWED POLICY WRITE",
    summary: "ForgeGate will evaluate the exact retained evidence against these embedded policy bytes, retain the result, and transition the candidate to PASS, FAIL, REVIEW, or ERROR.",
    confirmLabel: "Confirm evaluation",
    endpoint: `/app/api/candidates/${encodeURIComponent(candidate.candidate_id)}/evaluate`,
    body: {
      policy_material: material,
      policy: null,
      expected_revision: candidate.revision,
      evaluated_at: evaluatedAt,
      reason: "Dashboard reviewed policy evaluation"
    },
    idempotencyPrefix: `dashboard:evaluate:${candidate.candidate_id}`,
    details: [
      ["Candidate", candidate.candidate_id, true],
      ["Expected revision", String(candidate.revision)],
      ["Policy material ID", String(material.material_id ?? "missing"), true],
      ["Policy name", isJsonObject(policy) ? String(policy.name ?? "missing") : "missing"],
      ["Policy rules", String(rules.length)],
      ["Selected file", `${file.name} · ${file.size} bytes`],
      ["Selected file SHA-256", fingerprint, true],
      ["Evaluated at", formatDate(evaluatedAt)]
    ],
    completed: (response) => {
      if (!isJsonObject(response) || !isJsonObject(response.evaluation)) {
        return "Evaluation is retained; reload to inspect the authoritative decision.";
      }
      return `Engineering decision: ${String(response.evaluation.decision)}. Review the rule explanations before using the result.`;
    }
  };
}

function candidateWorkflowPanel(
  main: HTMLElement,
  review: CandidateAssuranceReview
): HTMLElement {
  const panel = el("section", "workflow-panel");
  panel.append(
    el("p", "eyebrow", "CONTROLLED WRITE WORKFLOW"),
    el("h3", undefined, "Next authorized command")
  );
  if (session?.principal.role !== "operator") {
    panel.append(el("p", "muted", "Producer sessions can inspect candidate state but cannot issue write commands."));
    return panel;
  }
  const candidate = review.candidate;
  if (["DRAFT", "COLLECTING"].includes(candidate.status) && review.evidence_binding === null) {
    const quick = button("Quick assessment", "button primary");
    quick.addEventListener("click", () => openQuickAssessment(main, candidate, quick));
    panel.append(quick, el("p", "muted", "Select a batch of reports, review the parsed evidence, then run binding, evaluation and attestation together."));
  }
  let label = "";
  let explanation = "";
  let action: ((buttonNode: HTMLButtonElement) => void) | null = null;
  if (candidate.status === "DRAFT") {
    label = "Start evidence collection";
    explanation = "Advances DRAFT to COLLECTING with optimistic revision control.";
    action = (buttonNode) => openReviewedMutation(main, candidate, transitionMutation(candidate, "COLLECTING"), buttonNode);
  } else if (candidate.status === "COLLECTING" && review.evidence_binding === null) {
    label = "Import and bind evidence";
    explanation = "Imports one versioned evidence assembly and binds it immutably to this candidate.";
    action = (buttonNode) => openJsonCommandImport(main, candidate, "evidence", buttonNode);
  } else if (candidate.status === "COLLECTING") {
    label = "Mark evidence ready";
    explanation = "Advances COLLECTING to READY after the retained binding is visible above.";
    action = (buttonNode) => openReviewedMutation(main, candidate, transitionMutation(candidate, "READY"), buttonNode);
  } else if (candidate.status === "READY") {
    label = "Begin evaluation";
    explanation = "Advances READY to EVALUATING as a separately reviewed lifecycle write.";
    action = (buttonNode) => openReviewedMutation(main, candidate, transitionMutation(candidate, "EVALUATING"), buttonNode);
  } else if (candidate.status === "EVALUATING") {
    label = "Import policy and evaluate";
    explanation = "Imports exact profile-authorized policy material and records the terminal decision.";
    action = (buttonNode) => openJsonCommandImport(main, candidate, "policy", buttonNode);
  } else if (["PASS", "FAIL", "REVIEW", "ERROR"].includes(candidate.status) && review.attestation === null) {
    label = "Generate attestation";
    explanation = "Creates an immutable unsigned-local attestation for the terminal candidate.";
    action = (buttonNode) => openReviewedMutation(main, candidate, attestMutation(candidate), buttonNode);
  }
  if (action === null) {
    panel.append(statusBadge("Workflow complete"), el("p", "muted", "No further candidate write is required. Review Evidence, Decision, and Assurance before export or publication."));
    return panel;
  }
  panel.append(el("p", "muted", explanation));
  const next = button(label, "button primary");
  next.addEventListener("click", () => action?.(next));
  panel.append(next);
  if (candidate.status === "COLLECTING" && review.evidence_binding === null) {
    const collect = button("Collect JUnit report", "button quiet");
    collect.addEventListener("click", () => openJUnitImport(main, candidate, collect));
    const combined = button("Collect standard CI reports", "button quiet");
    combined.addEventListener("click", () => openJUnitImport(main, candidate, combined, true));
    const queue = button("Prepare JUnit task", "button quiet");
    queue.addEventListener("click", () => openJUnitImport(main, candidate, queue, false, true));
    const queueCombined = button("Prepare standard CI task", "button quiet");
    queueCombined.addEventListener("click", () => openJUnitImport(main, candidate, queueCombined, true, true));
    panel.append(collect, combined, queue, queueCombined);
  }
  return panel;
}

async function showCandidateDetail(main: HTMLElement, candidateId: string): Promise<void> {
  const content = el("section", "detail-panel");
  content.setAttribute("aria-live", "polite");
  content.append(el("p", "muted", "Loading candidate and audit history…"));
  const existing = main.querySelector(".detail-panel");
  if (existing !== null) existing.remove();
  main.append(content);
  try {
    const candidate = await api<Candidate>(`/app/api/candidates/${encodeURIComponent(candidateId)}`);
    const review = await api<CandidateAssuranceReview>(
      `/app/api/candidates/${encodeURIComponent(candidateId)}/assurance-review`
    );
    let audit: AuditPage | null = null;
    if (session?.principal.role === "operator") {
      audit = await api<AuditPage>(`/app/api/audit-events?project_id=${encodeURIComponent(candidate.project_id)}&candidate_id=${encodeURIComponent(candidateId)}&limit=100`);
    }
    const heading = el("div", "card-heading");
    heading.append(el("div", undefined), statusBadge(candidate.status));
    heading.firstElementChild?.append(el("p", "eyebrow", "CANDIDATE DETAIL"), el("h2", undefined, candidate.version));
    const details = el("dl", "definition-list detail-grid");
    details.append(
      definition("Candidate ID", candidate.candidate_id, true),
      definition("Project", candidate.project_id),
      definition("Commit", candidate.commit_sha, true),
      definition("Track", candidate.release_track),
      definition("Candidate revision", String(candidate.revision)),
      definition("Engineering decision", candidate.evaluation_id === null ? "NOT_EVALUATED" : candidate.evaluation_id),
      definition("Profile version", String(candidate.project_profile_version ?? "unbound")),
      definition("Hardware claim", "NOT_PERFORMED")
    );
    const reviewLinks = el("nav", "review-links");
    reviewLinks.setAttribute("aria-label", "Candidate assurance review");
    for (const [route, label] of [
      ["evidence", "Review evidence"],
      ["decision", "Review decision"],
      ["assurance", "Review assurance"]
    ] as const) {
      const link = el("a", "button secondary", label);
      link.href = candidateReviewHash(route, candidateId);
      reviewLinks.append(link);
    }
    const auditSection = el("section", "audit-section");
    auditSection.append(el("h3", undefined, "Append-only audit history"));
    if (audit === null) {
      auditSection.append(el("p", "muted", "Audit history requires an operator session. Candidate fields remain available in this read-only view."));
    } else if (audit.events.length === 0) {
      auditSection.append(el("p", "muted", "No visible audit event."));
    } else {
      const timeline = el("ol", "timeline");
      for (const event of audit.events) {
        const item = el("li");
        item.append(el("strong", undefined, event.event_type), el("span", undefined, formatDate(event.occurred_at)), el("code", undefined, `sequence ${event.sequence} · ${shortHash(event.subject_fingerprint)}`));
        timeline.append(item);
      }
      auditSection.append(timeline);
    }
    if (audit !== null) {
      auditSection.append(el("p", "muted", audit.has_more ? "Only the first 100 events are shown here. Open the audit workspace for paginated history." : "Open the audit workspace for filters and full event identities."));
      const fullAudit = el("a", "button secondary", "Open candidate audit");
      fullAudit.href = auditHash(candidate.project_id, candidateId);
      auditSection.append(fullAudit);
    }
    content.replaceChildren(heading, details, candidateWorkflowPanel(main, review), reviewLinks, auditSection);
    content.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    handleProtectedProblem(content, error, "Return to the candidate list and retry the inspection.");
  }
}

async function loadCandidateAssuranceReview(): Promise<CandidateAssuranceReview | null> {
  const candidateId = candidateIdFromHash();
  if (candidateId === null) return null;
  return api<CandidateAssuranceReview>(
    `/app/api/candidates/${encodeURIComponent(candidateId)}/assurance-review`
  );
}

function reviewSelectionState(title: string): HTMLElement {
  const state = emptyState(
    `Select a candidate for ${title.toLowerCase()}`,
    "Open Candidates, inspect one release candidate, then choose the corresponding review action."
  );
  const open = el("a", "button primary", "Open candidates");
  open.href = "#/candidates";
  state.append(open);
  return state;
}

function reviewHeader(review: CandidateAssuranceReview, label: string): HTMLElement {
  const panel = el("section", "review-context");
  const heading = el("div", "card-heading");
  const title = el("div");
  title.append(el("p", "eyebrow", label), el("h2", undefined, review.candidate.version));
  heading.append(title, statusBadge(review.candidate.status));
  const details = el("dl", "definition-list detail-grid");
  details.append(
    definition("Candidate ID", review.candidate.candidate_id, true),
    definition("Project", review.candidate.project_id),
    definition("Commit", review.candidate.commit_sha, true),
    definition("Release track", review.candidate.release_track)
  );
  const links = el("nav", "review-tabs");
  links.setAttribute("aria-label", "Assurance review sections");
  for (const [route, text] of [
    ["evidence", "Evidence"],
    ["decision", "Decision"],
    ["assurance", "Assurance"]
  ] as const) {
    const link = el("a", currentRoute === route ? "review-tab active" : "review-tab", text);
    link.href = candidateReviewHash(route, review.candidate.candidate_id);
    if (currentRoute === route) link.setAttribute("aria-current", "page");
    links.append(link);
  }
  panel.append(heading, details, links);
  return panel;
}

function textValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null) return "null";
  try {
    return JSON.stringify(value);
  } catch {
    return "unavailable";
  }
}

function paginatedReviewTable(
  caption: string,
  headings: readonly string[],
  rowFactories: ReadonlyArray<() => HTMLElement>
): HTMLElement {
  const pageSize = 25;
  let pageIndex = 0;
  const region = el("section", "review-table-region");
  const wrapper = el("div", "table-wrap");
  const table = el("table");
  table.append(el("caption", "sr-only", caption));
  const head = el("thead");
  const headingRow = el("tr");
  for (const label of headings) headingRow.append(el("th", undefined, label));
  head.append(headingRow);
  const body = el("tbody");
  table.append(head, body);
  wrapper.append(table);

  const pager = el("nav", "pager review-pager");
  pager.setAttribute("aria-label", `${caption} pages`);
  const status = el("p", "pager-status");
  status.setAttribute("aria-live", "polite");
  const actions = el("div", "pager-actions");
  const previous = button("Previous page", "button quiet");
  const next = button("Next page", "button secondary");

  const renderPage = (): void => {
    const start = pageIndex * pageSize;
    const end = Math.min(start + pageSize, rowFactories.length);
    body.replaceChildren(...rowFactories.slice(start, end).map((createRow) => createRow()));
    status.textContent = `Showing ${start + 1}–${end} of ${rowFactories.length}`;
    previous.disabled = pageIndex === 0;
    next.disabled = end >= rowFactories.length;
  };
  previous.addEventListener("click", () => {
    if (pageIndex === 0) return;
    pageIndex -= 1;
    renderPage();
  });
  next.addEventListener("click", () => {
    if ((pageIndex + 1) * pageSize >= rowFactories.length) return;
    pageIndex += 1;
    renderPage();
  });
  actions.append(previous, next);
  pager.append(status, actions);
  region.append(wrapper, pager);
  renderPage();
  return region;
}

async function renderEvidence(): Promise<void> {
  loadingPage("Evidence");
  const main = page(
    "Bound evidence",
    "RETAINED INPUTS",
    "Inspect the immutable evidence binding, collector receipts, trust labels, and artifact references used by one candidate."
  );
  try {
    const review = await loadCandidateAssuranceReview();
    if (review === null) {
      main.append(reviewSelectionState("Evidence"));
      shell(main);
      return;
    }
    main.append(reviewHeader(review, "CANDIDATE EVIDENCE"));
    const binding = review.evidence_binding;
    if (binding === null) {
      main.append(
        emptyState(
          review.evidence_binding_required ? "Evidence not bound" : "No binding required for this legacy record",
          "This candidate has no retained evidence assembly. No rule input is inferred from live status or other projects."
        )
      );
    } else {
      const metrics = el("section", "metric-grid");
      for (const [label, value] of [
        ["Records", String(binding.assembly.bundle.evidence.length)],
        ["Collections", String(binding.assembly.collections.length)],
        ["Warnings", binding.assembly.warning_disposition],
        ["Bound", formatDate(binding.bound_at)]
      ]) {
        const card = el("article", "metric-card");
        card.append(el("span", undefined, label), el("strong", undefined, value));
        metrics.append(card);
      }
      const identity = el("section", "panel");
      identity.append(el("p", "eyebrow", "CONTENT IDENTITY"), el("h3", undefined, "Binding and assembly"));
      const ids = el("dl", "definition-list");
      ids.append(
        definition("Binding ID", binding.binding_id, true),
        definition("Assembly ID", binding.assembly.assembly_id, true),
        definition("Assembly fingerprint", binding.assembly_fingerprint, true),
        definition("Producer", binding.assembly.bundle.producer),
        definition("Bundle generated", formatDate(binding.assembly.bundle.generated_at))
      );
      identity.append(ids);

      const evidenceTable = paginatedReviewTable(
        "Bound evidence records",
        ["Evidence ID", "Kind", "Scope", "Value", "Status", "Trust", "Verification", "Artifact"],
        binding.assembly.bundle.evidence.map((record) => () => {
          const evidenceRow = el("tr");
          evidenceRow.append(
            el("td", "mono", record.evidence_id),
            el("td", undefined, record.kind),
            el("td", undefined, record.scope),
            el("td", "mono", `${textValue(record.value)}${record.unit === null ? "" : ` ${record.unit}`}`),
            el("td", undefined, record.status),
            el("td", undefined, record.trust),
            el("td", undefined, record.verification_level),
            el("td", "mono", shortHash(record.artifact.sha256))
          );
          return evidenceRow;
        })
      );
      const boundary = el("section", "panel warning-panel");
      boundary.append(
        el("p", "eyebrow", "EVIDENCE BOUNDARY"),
        el("h3", undefined, "Integrity is narrower than authenticity"),
        el("p", undefined, review.limitations[1] ?? "Artifact hashes do not establish producer authenticity.")
      );
      main.append(metrics, identity, evidenceTable, boundary);
    }
  } catch (error) {
    if (handleProtectedProblem(main, error, "Return to Candidates and confirm the selected candidate is in scope.")) return;
  }
  shell(main);
}

interface DecisionComparison {
  blockers: string[];
  rows: Array<{ before: RuleEvaluation; after: RuleEvaluation; change: string }>;
}

function compareDecisions(baseline: CandidateAssuranceReview, current: CandidateAssuranceReview): DecisionComparison {
  const blockers: string[] = [];
  const a = baseline.candidate, b = current.candidate;
  if (a.candidate_id === b.candidate_id) blockers.push("Choose two different candidates.");
  for (const key of ["project_id", "release_track", "project_profile_id", "project_profile_version"] as const) {
    if (a[key] !== b[key] || a[key] === null) blockers.push(`Different or unavailable ${key}.`);
  }
  for (const [label, review] of [["Baseline", baseline], ["Current", current]] as const) {
    const { candidate, policy_evaluation: evaluation, policy_material: material } = review;
    if (!evaluation || !material) {
      blockers.push(`${label}: retained evaluation and policy material are required.`);
      continue;
    }
    if (evaluation.candidate_commit !== candidate.commit_sha || evaluation.evaluation_id !== candidate.evaluation_id ||
        evaluation.decision !== candidate.status || evaluation.policy_fingerprint !== material.policy_fingerprint ||
        evaluation.policy_material_id !== material.material_id || material.project_profile_id !== candidate.project_profile_id ||
        material.project_profile_version !== candidate.project_profile_version || material.release_track !== candidate.release_track ||
        evaluation.project_profile_id !== candidate.project_profile_id || evaluation.project_profile_version !== candidate.project_profile_version) {
      blockers.push(`${label}: retained candidate, evaluation and policy references do not agree.`);
    }
    const ruleIds = evaluation.rule_results.map(rule => rule.rule_id).sort();
    const materialIds = material.policy.rules.map(rule => rule.id).sort();
    if (new Set(ruleIds).size !== ruleIds.length || JSON.stringify(ruleIds) !== JSON.stringify(materialIds)) {
      blockers.push(`${label}: rule results do not match the retained policy rule set.`);
    }
  }
  const oldEvaluation = baseline.policy_evaluation, evaluation = current.policy_evaluation;
  const oldMaterial = baseline.policy_material, material = current.policy_material;
  if (oldMaterial && material && (oldMaterial.policy_fingerprint !== material.policy_fingerprint ||
      oldMaterial.artifact.sha256 !== material.artifact.sha256)) blockers.push("Policy fingerprint or source bytes changed.");
  if (blockers.length || !oldEvaluation || !evaluation) return { blockers, rows: [] };
  const previous = new Map(oldEvaluation.rule_results.map(rule => [rule.rule_id, rule]));
  const rows: DecisionComparison["rows"] = [];
  for (const after of evaluation.rule_results) {
    const before = previous.get(after.rule_id);
    if (!before || before.claim !== after.claim || before.mandatory !== after.mandatory ||
        JSON.stringify(sortedJsonValue(before.expected)) !== JSON.stringify(sortedJsonValue(after.expected))) {
      blockers.push("Rule identity or expected value changed despite matching policy references.");
      break;
    }
    let change = "Unchanged";
    if (after.decision === "FAIL" && before.decision !== "FAIL") change = "New failure";
    else if (before.decision === "FAIL" && after.decision === "PASS") change = "Rule restored to PASS";
    else if (before.decision !== after.decision) change = `Now ${after.decision}`;
    else if (before.reason_code !== after.reason_code || JSON.stringify(sortedJsonValue(before.actual)) !== JSON.stringify(sortedJsonValue(after.actual))) change = "Changed result";
    rows.push({ before, after, change });
  }
  if (rows.length !== oldEvaluation.rule_results.length && !blockers.length) blockers.push("Rule sets differ.");
  return { blockers, rows: blockers.length ? [] : rows };
}

function decisionComparisonPanel(current: CandidateAssuranceReview): HTMLElement {
  const panel = el("section", "panel");
  panel.setAttribute("aria-label", "Compare evaluations");
  panel.append(el("p", "eyebrow", "READ-ONLY COMPARISON"), el("h2", undefined, "Compare evaluations"),
    el("p", "muted", "Choose a baseline explicitly. Current means the candidate on this page, not the newest run. Matching policy/profile authority is required; no candidate or release decision is changed."));
  const owner = session, route = window.location.hash;
  let generation = 0, busy = false, cursor: string | null = null;
  const active = () => session === owner && window.location.hash === route && panel.isConnected;
  const choices = new Map<string, Candidate>();
  const pickerLabel = el("label", "field");
  const picker = el("select");
  picker.value = "";
  const placeholder = el("option", undefined, "Select an evaluated baseline"); placeholder.value = "";
  picker.append(placeholder); pickerLabel.append(el("span", undefined, "Baseline evaluation"), picker);
  const load = button("Load baseline choices");
  const compare = button("Compare with current", "button primary"); compare.disabled = true;
  const status = el("p", "muted"); status.setAttribute("role", "status");
  const output = el("div");
  const controls = el("div", "toolbar"); controls.append(load, pickerLabel, compare);
  panel.append(controls, status, output);
  picker.addEventListener("change", () => {
    generation++; output.replaceChildren(); status.textContent = "Baseline changed. Compare to load its retained evaluation.";
    compare.disabled = busy || !choices.has(picker.value);
  });
  load.addEventListener("click", async () => {
    if (busy || !active()) return;
    busy = true; load.disabled = true; compare.disabled = true;
    const token = ++generation; output.replaceChildren(); status.textContent = "Loading candidate page…";
    try {
      const query = new URLSearchParams({limit: "100"});
      if (cursor !== null) query.set("after_candidate_id", cursor);
      const page = await api<CandidatePage>(`/app/api/projects/${encodeURIComponent(current.candidate.project_id)}/candidates?${query}`);
      if (!active() || token !== generation) return;
      for (const candidate of page.candidates) {
        if (candidate.project_id !== current.candidate.project_id || candidate.candidate_id === current.candidate.candidate_id || !candidate.evaluation_id || choices.has(candidate.candidate_id)) continue;
        choices.set(candidate.candidate_id, candidate);
        const option = el("option", undefined, `${candidate.version} · ${candidate.status} · ${shortHash(candidate.commit_sha)} · ${candidate.candidate_id}`);
        option.value = candidate.candidate_id; picker.append(option);
      }
      if (page.has_more && (!page.next_after_candidate_id || page.next_after_candidate_id === cursor)) throw new Error("Candidate pagination did not advance.");
      cursor = page.has_more ? page.next_after_candidate_id : null;
      load.textContent = page.has_more ? "Load more baseline choices" : "Refresh baseline choices";
      status.textContent = `${choices.size} evaluated baseline choices loaded. ${page.has_more ? "More candidates are available; load the next page if needed." : "End of candidate list."} No baseline is selected automatically.`;
    } catch (error) {
      if (active() && token === generation) { status.textContent = "Could not load baseline choices."; handleProtectedProblem(output, error, "Retry loading baseline choices."); }
    } finally {
      busy = false; load.disabled = false; compare.disabled = !choices.has(picker.value);
    }
  });
  compare.addEventListener("click", async () => {
    if (busy || !active() || !choices.has(picker.value)) return;
    busy = true; compare.disabled = true; load.disabled = true;
    const token = ++generation, baselineId = picker.value;
    output.replaceChildren(); status.textContent = "Loading both retained evaluations…";
    try {
      const [baseline, fresh] = await Promise.all([baselineId, current.candidate.candidate_id].map(id =>
        api<CandidateAssuranceReview>(`/app/api/candidates/${encodeURIComponent(id)}/assurance-review`)));
      if (!active() || token !== generation) return;
      if (!baseline || !fresh || baseline.candidate.candidate_id !== baselineId || fresh.candidate.candidate_id !== current.candidate.candidate_id ||
          baseline.candidate.project_id !== current.candidate.project_id || fresh.candidate.project_id !== current.candidate.project_id) throw new Error("Unexpected candidate identity in comparison response.");
      const result = compareDecisions(baseline, fresh);
      const identities = el("dl", "definition-list");
      for (const [label, review] of [["Baseline", baseline], ["Current", fresh]] as const) {
        identities.append(definition(label, `${review.candidate.version} · ${review.candidate.candidate_id}`),
          definition(`${label} commit`, review.candidate.commit_sha, true),
          definition(`${label} evaluation`, `${review.policy_evaluation?.evaluation_id ?? "unavailable"} · ${review.policy_evaluation?.evaluated_at ?? "unavailable"}`, true));
      }
      output.append(identities);
      if (result.blockers.length) {
        status.textContent = "NOT COMPARABLE — no regression or recovery conclusion.";
        output.append(el("p", "command-boundary", result.blockers.join(" ")));
        return;
      }
      const count = (change: string) => result.rows.filter(row => row.change === change).length;
      const missing = result.rows.filter(row => row.after.reason_code === "EVIDENCE_MISSING").length;
      const newMissing = result.rows.filter(row => row.after.reason_code === "EVIDENCE_MISSING" && row.before.reason_code !== "EVIDENCE_MISSING").length;
      status.textContent = `COMPARABLE · ${count("New failure")} new failures · ${count("Rule restored to PASS")} rules restored to PASS · ${missing} current missing-evidence rules (${newMissing} newly missing).`;
      output.append(el("p", "command-boundary", "Rule-level comparison of retained results only. A restored rule does not prove an individual defect was fixed. Missing evidence means EVIDENCE_MISSING; permitted absence, stale data and insufficient assurance are separate reasons. This is not producer authentication, policy re-execution, hardware verification or release approval."));
      output.append(paginatedReviewTable("Evaluation changes", ["Rule / claim", "Change", "Baseline → current", "Expected", "Actual: baseline → current", "Evidence / reason: baseline → current"], result.rows.map(({before, after, change}) => () => {
        const row = el("tr");
        row.append(el("td", "strong-cell", `${after.rule_id} · ${after.claim}`), el("td", undefined, change),
          el("td", undefined, `${before.decision} → ${after.decision}`), el("td", "mono", textValue(after.expected)),
          el("td", "mono", `${textValue(before.actual)} → ${textValue(after.actual)}`),
          el("td", undefined, `${before.reason_code}: ${before.explanation} [${before.evidence_ids.join(", ") || "none"}] → ${after.reason_code}: ${after.explanation} [${after.evidence_ids.join(", ") || "none"}]`));
        return row;
      })));
    } catch (error) {
      if (active() && token === generation) { status.textContent = "Comparison unavailable. No prior comparison is shown."; handleProtectedProblem(output, error, "Check session/project access and retry comparison."); }
    } finally {
      busy = false; load.disabled = false; compare.disabled = !choices.has(picker.value);
    }
  });
  return panel;
}

async function renderDecision(): Promise<void> {
  loadingPage("Decision");
  const main = page(
    "Policy decision",
    "EXPLAINABLE RULES",
    "Trace the candidate decision to exact policy material, rule results, expected values, actual values, and evidence IDs."
  );
  try {
    const review = await loadCandidateAssuranceReview();
    if (review === null) {
      main.append(reviewSelectionState("Decision"));
      shell(main);
      return;
    }
    main.append(reviewHeader(review, "ENGINEERING DECISION"));
    const evaluation = review.policy_evaluation;
    if (evaluation === null) {
      main.append(emptyState("Not evaluated", "No durable policy evaluation exists for this candidate. Its current status is not a release decision."));
    } else {
      const summary = el("section", "decision-hero");
      const title = el("div");
      title.append(el("p", "eyebrow", "AGGREGATED RESULT"), el("h2", undefined, evaluation.decision));
      summary.append(title, statusBadge(evaluation.decision));
      const columns = el("div", "content-columns");
      const evaluationPanel = el("section", "panel");
      evaluationPanel.append(el("p", "eyebrow", "EVALUATION IDENTITY"), el("h3", undefined, evaluation.policy_name));
      const evaluationDetails = el("dl", "definition-list");
      evaluationDetails.append(
        definition("Evaluation ID", evaluation.evaluation_id, true),
        definition("Evaluated", formatDate(evaluation.evaluated_at)),
        definition("Evidence fingerprint", evaluation.evidence_fingerprint, true),
        definition("Evidence referenced", String(evaluation.evaluated_evidence_ids.length))
      );
      evaluationPanel.append(evaluationDetails);
      const policyPanel = el("section", "panel");
      policyPanel.append(el("p", "eyebrow", "POLICY AUTHORITY"), el("h3", undefined, review.policy_material?.release_track ?? "Legacy or unavailable"));
      const policyDetails = el("dl", "definition-list");
      policyDetails.append(
        definition("Material ID", review.policy_material?.material_id ?? "NOT_RETAINED", true),
        definition("Policy fingerprint", evaluation.policy_fingerprint, true),
        definition("Profile version", String(review.policy_material?.project_profile_version ?? "unbound")),
        definition("Policy path", review.policy_material?.artifact.path_or_uri ?? "not available", true)
      );
      policyPanel.append(policyDetails);
      columns.append(evaluationPanel, policyPanel);

      const ruleTable = paginatedReviewTable(
        "Policy rule results",
        ["Rule", "Claim", "Decision", "Expected", "Actual", "Evidence", "Explanation"],
        evaluation.rule_results.map((rule) => () => {
          const result = el("tr");
          const decision = el("td");
          decision.append(statusBadge(rule.decision));
          result.append(
            el("td", "strong-cell", rule.rule_id),
            el("td", undefined, rule.claim),
            decision,
            el("td", "mono", textValue(rule.expected)),
            el("td", "mono", textValue(rule.actual)),
            el("td", "mono", rule.evidence_ids.join(", ") || "none"),
            el("td", undefined, `${rule.reason_code}: ${rule.explanation}`)
          );
          return result;
        })
      );
      main.append(summary, decisionComparisonPanel(review), columns, ruleTable);
    }
  } catch (error) {
    if (handleProtectedProblem(main, error, "Return to Candidates and confirm the selected candidate is in scope.")) return;
  }
  shell(main);
}

function openAssuranceExportDialog(
  main: HTMLElement,
  review: CandidateAssuranceReview,
  returnFocus?: HTMLElement
): void {
  const bundleId = review.assurance_bundle_id;
  if (bundleId === null) return;
  const dialog = el("dialog", "review-dialog");
  dialog.setAttribute("aria-labelledby", "assurance-export-dialog-title");
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    dialog.close();
  });
  dialog.addEventListener("keydown", (event) => keepFocusInsideDialog(dialog, event));
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (returnFocus?.isConnected) returnFocus.focus();
  }, { once: true });

  const panel = el("section", "review-panel");
  const heading = el("h2", undefined, "Confirm portable assurance download");
  heading.id = "assurance-export-dialog-title";
  panel.append(
    el("p", "eyebrow", "REVIEWED LOCAL EXPORT"),
    heading,
    el("p", "muted", "ForgeGate will render the exact retained bundle as one deterministic ZIP. The server receives no output path and writes no export file.")
  );
  const details = el("dl", "definition-list");
  details.append(
    definition("Candidate", review.candidate.candidate_id, true),
    definition("Candidate revision", String(review.candidate.revision)),
    definition("Bundle ID", bundleId, true),
    definition("Archive members", "README.md · assurance-bundle.json · manifest.json"),
    definition("Assurance", review.assurance ?? "unsigned_local"),
    definition("Source artifact bytes", review.source_artifact_bytes ?? "not_embedded")
  );
  const boundary = el(
    "p",
    "command-boundary",
    "This creates a browser download only. It does not change retained state, publish to GitHub, authenticate producers, embed referenced source artifacts, deploy software, or control hardware."
  );
  const status = el("div", "dialog-status");
  status.setAttribute("aria-live", "polite");
  const controls = el("div", "dialog-actions");
  const cancel = button("Cancel", "button quiet");
  cancel.addEventListener("click", () => dialog.close());
  const confirm = button("Download verified ZIP", "button primary");
  confirm.addEventListener("click", async () => {
    cancel.disabled = true;
    confirm.disabled = true;
    status.replaceChildren(el("p", "muted", "Rendering the candidate-bound archive…"));
    try {
      const download = await downloadAssuranceArchive(
        review.candidate.candidate_id,
        review.candidate.revision,
        bundleId
      );
      saveLocalDownload(download);
      heading.textContent = "Download requested";
      const eyebrow = panel.querySelector<HTMLElement>(".eyebrow");
      if (eyebrow !== null) eyebrow.textContent = "EXPORT COMPLETED";
      status.replaceChildren(
        statusBadge("Archive ready"),
        el("p", undefined, `${download.filename} was handed to the browser. Verify the extracted directory with forgegate verify-assurance before relying on it.`)
      );
      const done = button("Done", "button primary");
      done.addEventListener("click", () => dialog.close());
      controls.replaceChildren(done);
      done.focus();
    } catch (error) {
      showProblem(
        status,
        error,
        "Close this review, reload Assurance, and confirm the current bundle identity before trying again."
      );
      cancel.disabled = false;
      cancel.textContent = "Close and reload";
      cancel.addEventListener("click", () => void renderAssurance(), { once: true });
    }
  });
  controls.append(cancel, confirm);
  panel.append(details, boundary, status, controls);
  dialog.append(panel);
  main.append(dialog);
  dialog.showModal();
  confirm.focus();
}

function openReplayExportDialog(main: HTMLElement, review: CandidateAssuranceReview, returnFocus?: HTMLElement, preparedFiles?: File[]): void {
  if (!review.evidence_binding || !review.assurance_bundle_id) return;
  const owner = session, route = window.location.hash;
  const invalid = (message: string): RequestProblem => new RequestProblem(422, "DASHBOARD_REPLAY_SELECTION_INVALID", message, "browser-side", null, "browser");
  const required = new Map<string, number>();
  for (const receipt of review.evidence_binding.assembly.collections) {
    for (const ref of [receipt.source, ...receipt.artifacts]) required.set(ref.sha256, ref.size_bytes);
  }
  const dialog = el("dialog", "review-dialog"), panel = el("section", "review-panel");
  dialog.setAttribute("aria-labelledby", "replay-export-title");
  const heading = el("h2", undefined, "Export original evidence for offline replay");
  heading.id = "replay-export-title";
  const label = el("label", "field-label", "Original reports and collection results");
  const input = el("input"); input.type = "file"; input.multiple = true;
  if (preparedFiles) input.disabled = true;
  input.id = "replay-source-files"; label.htmlFor = input.id;
  const warning = el("p", "command-boundary", "Original bytes are preserved. Reports may contain private paths or data. Keep this archive private; review its contents before sharing. Replay checks report parsing and policy results; it does not rerun producer tests or authenticate their origin.");
  const consentLabel = el("label", "field-label", "I reviewed the source-data privacy boundary");
  const consent = el("input"); consent.type = "checkbox"; consent.id = "replay-private-consent";
  consentLabel.htmlFor = consent.id;
  const status = el("div", "dialog-status"); status.setAttribute("aria-live", "polite");
  const controls = el("div", "dialog-actions");
  const close = button("Cancel", "button quiet"), inspect = button("Review selected originals", "button primary");
  let generation = 0;
  const isCurrent = (active: number) => active === generation && dialog.open && dialog.isConnected && session === owner && window.location.hash === route;
  const end = () => { generation++; dialog.close(); };
  close.addEventListener("click", end);
  dialog.addEventListener("cancel", e => { e.preventDefault(); end(); });
  dialog.addEventListener("keydown", e => keepFocusInsideDialog(dialog, e));
  dialog.addEventListener("close", () => { generation++; dialog.remove(); if (returnFocus?.isConnected) returnFocus.focus(); }, {once:true});
  inspect.addEventListener("click", async () => {
    const active = ++generation;
    inspect.disabled = true; input.disabled = true;
    try {
      const selected = preparedFiles ?? Array.from(input.files ?? []);
      if (selected.length !== required.size || selected.length > 32 || selected.some(f => f.size > 1048576)
          || selected.reduce((sum, f) => sum + f.size, 0) > 2097152) throw invalid(`Select all ${required.size} required report and receipt files once: at most 1 MiB per file and 2 MiB total.`);
      const files: Array<{sha256:string;content_base64:string}> = [];
      const seen = new Set<string>();
      for (const file of selected) {
        const content = await file.arrayBuffer();
        if (!isCurrent(active)) return;
        const digest = await sha256Hex(content);
        if (!isCurrent(active)) return;
        if (content.byteLength !== file.size || required.get(digest) !== content.byteLength || seen.has(digest)) throw invalid("A selected file is duplicated, changed or does not match a retained source hash. Use the original report and collection-result bytes.");
        seen.add(digest);
        let binary = "";
        for (const value of new Uint8Array(content)) binary += String.fromCharCode(value);
        files.push({sha256:digest,content_base64:btoa(binary)});
      }
      const details = el("dl", "definition-list");
      details.append(definition("Candidate", review.candidate.candidate_id, true), definition("Commit", review.candidate.commit_sha, true), definition("Matching source files", String(files.length)));
      status.replaceChildren(details, el("p", undefined, "All selected hashes match. The service will reparse these exact bytes and recompute the retained policy before export."));
      const download = button("Confirm private replay download", "button primary");
      controls.replaceChildren(close, download);
      let submitted = false;
      download.addEventListener("click", async () => {
        if (submitted || !isCurrent(active)) return;
        if (!consent.checked) { status.append(el("p", "command-boundary", "Review and acknowledge the source-data privacy boundary first.")); return; }
        submitted = true;
        download.disabled = true; consent.disabled = true;
        try {
          if (session === null) throw new Error("Dashboard session is unavailable");
          const response = await fetch(`/app/api/candidates/${encodeURIComponent(review.candidate.candidate_id)}/evidence-replay-export`, {
            method:"POST", credentials:"same-origin", cache:"no-store",
            headers:{"Content-Type":"application/json","Accept":"application/zip","X-ForgeGate-CSRF":session.csrf_token,"X-Request-ID":requestId()},
            body:JSON.stringify({expected_revision:review.candidate.revision,expected_bundle_id:review.assurance_bundle_id,files,acknowledge_private_sources:true})
          });
          if (!isCurrent(active)) return;
          if (!response.ok) throw requestProblem(response, await response.json().catch(()=>({})));
          const filename = response.headers.get("X-ForgeGate-Replay-Archive") ?? "";
          if (response.headers.get("X-ForgeGate-Assurance-Bundle") !== review.assurance_bundle_id || response.headers.get("Content-Type")?.split(";",1)[0] !== "application/zip" || !/^replay-[0-9a-f]{64}\.zip$/.test(filename)) throw new Error("Replay response identity or media type is invalid.");
          const blob = await response.blob();
          if (blob.size === 0 || blob.size > 20971520) throw new Error("Replay archive exceeds the response size limit.");
          const digest = await sha256Hex(await blob.arrayBuffer());
          if (!isCurrent(active)) return;
          if (digest !== response.headers.get("X-ForgeGate-Archive-SHA256")) throw new Error("Replay archive response hash does not match.");
          saveLocalDownload({blob,filename});
          heading.textContent = "Private replay archive downloaded";
          status.replaceChildren(el("p", undefined, `${files.length} original files included. Retained engineering decision: ${review.candidate.status}.`), el("code", "mono", `forgegate evidence-replay verify ${filename} --expected-commit ${review.candidate.commit_sha}`));
          close.textContent = "Done"; controls.replaceChildren(close); close.focus();
        } catch (error) { if (active === generation) { showProblem(status,error,"Close and reopen this review before retrying."); controls.replaceChildren(close); } }
      });
      download.focus();
    } catch (error) { if (active === generation) { showProblem(status,error,"Select the complete original files and review again."); input.disabled = false; inspect.disabled = false; } }
  });
  controls.append(close,inspect);
  panel.append(heading,el("p","muted",preparedFiles ? `${preparedFiles.length} original source files (reports plus exact collection receipts) from this assessment are already selected. Review them, then download to save permanently.` : `Select ${required.size} original report and collection-result files. Files are matched by SHA-256 regardless of filename.`),label,input,warning,consent,consentLabel,status,controls);
  dialog.append(panel); main.append(dialog); dialog.showModal(); input.focus();
}

async function renderAssurance(): Promise<void> {
  loadingPage("Assurance");
  const main = page(
    "Release assurance",
    "PORTABLE REVIEW",
    "Inspect the retained attestation, transition chain, portable bundle identity, and explicit assurance limitations."
  );
  try {
    const review = await loadCandidateAssuranceReview();
    if (review === null) {
      main.append(reviewSelectionState("Assurance"));
      shell(main);
      return;
    }
    main.append(reviewHeader(review, "ASSURANCE ARTIFACT"));
    if (review.attestation === null) {
      main.append(emptyState("Attestation not generated", "This candidate has no durable release attestation. No portable assurance bundle is claimed."));
    } else {
      const summary = el("section", "assurance-hero");
      const title = el("div");
      title.append(el("p", "eyebrow", "ATTESTED DECISION"), el("h2", undefined, review.candidate.status));
      summary.append(title, statusBadge(review.assurance ?? review.attestation.assurance));
      const columns = el("div", "content-columns");
      const identity = el("section", "panel");
      identity.append(el("p", "eyebrow", "PORTABLE IDENTITY"), el("h3", undefined, "Attestation and bundle"));
      const details = el("dl", "definition-list");
      details.append(
        definition("Attestation ID", review.attestation.attestation_id, true),
        definition("Bundle ID", review.assurance_bundle_id ?? "NOT_AVAILABLE", true),
        definition("Issued", formatDate(review.attestation.issued_at)),
        definition("Generator", `ForgeGate ${review.attestation.generator_version}`),
        definition("Transition chain", review.attestation.transition_chain_fingerprint, true),
        definition("Verification scope", review.verification_scope ?? "not available"),
        definition("Source bytes", review.source_artifact_bytes ?? "not available")
      );
      identity.append(details);
      const boundaries = el("section", "panel warning-panel");
      boundaries.append(el("p", "eyebrow", "ASSURANCE LIMITS"), el("h3", undefined, "Read the claim boundary first"));
      const list = el("ul", "limitation-list");
      for (const limitation of review.limitations) list.append(el("li", undefined, limitation));
      boundaries.append(list);
      columns.append(identity, boundaries);

      const exportPanel = el("section", "workflow-panel");
      exportPanel.append(
        el("p", "eyebrow", "PORTABLE DELIVERY"),
        el("h3", undefined, "Download an offline-verifiable bundle"),
        el("p", "muted", "The ZIP uses the content-derived bundle ID as its filename and contains only the canonical three-file portable contract.")
      );
      if (session?.principal.role === "operator" && review.assurance_bundle_id !== null) {
        const exportButton = button("Review assurance download", "button primary");
        exportButton.addEventListener("click", () => openAssuranceExportDialog(main, review, exportButton));
        exportPanel.append(exportButton);
        const replayButton = button("Export original evidence", "button quiet");
        replayButton.addEventListener("click", () => openReplayExportDialog(main, review, replayButton));
        exportPanel.append(replayButton);
      } else {
        exportPanel.append(el("p", "command-boundary", "An operator session is required to export this complete assurance artifact. Producer sessions remain read-only review sessions."));
      }

      const transitions = el("section", "panel transition-panel");
      transitions.append(el("p", "eyebrow", "IMMUTABLE LIFECYCLE"), el("h3", undefined, "Candidate transition chain"));
      const timeline = el("ol", "timeline");
      for (const transition of review.transitions) {
        const item = el("li");
        item.append(
          el("strong", undefined, `${transition.from_status} → ${transition.to_status}`),
          el("span", undefined, `${formatDate(transition.occurred_at)} · revision ${transition.to_revision}`),
          el("code", undefined, shortHash(transition.transition_id))
        );
        timeline.append(item);
      }
      transitions.append(timeline);
      main.append(summary, columns, exportPanel, transitions);
    }
  } catch (error) {
    if (handleProtectedProblem(main, error, "Return to Candidates and confirm the selected candidate is in scope.")) return;
  }
  shell(main);
}

function handleProtectedProblem(container: HTMLElement, error: unknown, recovery: string): boolean {
  if (error instanceof RequestProblem && error.status === 401) {
    renderActivation("Your Dashboard session ended or expired. Start a new local activation to continue.");
    return true;
  }
  showProblem(container, error, recovery);
  return false;
}

window.addEventListener("hashchange", () => void renderRoute());
window.addEventListener("beforeunload", () => {
  clearActivationTimer();
  clearSessionExpiryTimer();
  clearLiveStatusTimer();
});
void loadSession();
