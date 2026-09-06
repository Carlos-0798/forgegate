import "./styles.css";

type Role = "operator" | "producer";
type Route = "overview" | "devices" | "projects" | "candidates" | "evidence" | "decision" | "assurance";

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
  assembly_fingerprint: string;
  assembly: {
    assembly_id: string;
    warning_disposition: string;
    bundle: { generated_at: string; producer: string; evidence: EvidenceRecord[] };
    collections: Array<{ collector_name: string; collector_version: string; warnings: Array<{ code: string; message: string }> }>;
  };
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

interface AssuranceDownload {
  blob: Blob;
  filename: string;
}

class RequestProblem extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId: string,
    readonly retryAfterSeconds: number | null
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
let sessionExpiryTimer: number | null = null;
let liveStatusTimer: number | null = null;
let liveStatusGeneration = 0;
let lastLiveAnnouncement = "";

const MAX_DASHBOARD_IMPORT_BYTES = 3_900_000;

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
    candidate === "evidence" || candidate === "decision" || candidate === "assurance"
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
): Promise<AssuranceDownload> {
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

function saveLocalDownload(download: AssuranceDownload): void {
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
  const panel = el("section", "problem-panel");
  panel.setAttribute("role", "alert");
  panel.setAttribute("aria-live", "assertive");
  panel.tabIndex = -1;
  panel.append(
    el("p", "problem-code", `ERROR [${problem?.code ?? "DASHBOARD_UNEXPECTED_ERROR"}]`),
    el("h2", undefined, "The request did not complete"),
    el("p", "problem-status", `HTTP status: ${problem?.status ?? "unavailable"}`),
    el("p", undefined, problem?.message ?? "An unexpected browser-side error occurred."),
    el("p", "recovery", `Safe next step: ${problemRecovery(problem, recovery)}`),
    el("p", "request-id", `Request ID: ${problem?.requestId ?? "not available"}`)
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
  for (const [route, label, detail] of [
    ["overview", "Overview", "Service and authority"],
    ["devices", "Devices", "Live read-only status"],
    ["projects", "Projects", "Immutable profiles"],
    ["candidates", "Candidates", "Release work and audit"],
    ["evidence", "Evidence", "Bound records and sources"],
    ["decision", "Decision", "Rules and explanations"],
    ["assurance", "Assurance", "Attestation and limits"]
  ] as const) {
    const link = el("a", currentRoute === route ? "nav-link active" : "nav-link");
    link.href = reviewCandidateId !== null && ["evidence", "decision", "assurance"].includes(route)
      ? candidateReviewHash(route as "evidence" | "decision" | "assurance", reviewCandidateId)
      : `#/${route}`;
    if (currentRoute === route) link.setAttribute("aria-current", "page");
    link.append(el("strong", undefined, label), el("span", undefined, detail));
    nav.append(link);
  }
  const planned = el("section", "planned-nav");
  planned.append(el("p", "eyebrow", "LATER GATES"));
  for (const label of ["Plugins", "Security"]) {
    const row = el("div", "planned-row");
    row.append(el("span", undefined, label), el("span", "badge neutral", "Planned"));
    planned.append(row);
  }
  nav.append(planned);

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
  clearActivationTimer();
  clearSessionExpiryTimer();
  clearLiveStatusTimer();
  session = null;
  projects = [];
  selectedProjectId = null;
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
  const actions = card.querySelector<HTMLElement>(".activation-actions");
  if (actions === null) return;
  actions.replaceChildren(el("p", "muted", "Creating a one-time browser-bound request…"));
  try {
    const activation = await api<ActivationStart>("/app/api/activations", {
      method: "POST",
      body: "{}"
    });
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
      `forgegate dashboard-activate ${activation.activation_code} --identity IDENTITY.json --private-key KEY.pem --role ROLE --project PROJECT_ID`
    );
    panel.append(
      command,
      el("p", "muted", "Replace ROLE with producer or operator. The terminal will display and authorize the exact role and project scopes.")
    );
    actions.replaceChildren(panel);
    pollActivation(Math.max(activation.poll_after_seconds, 1));
  } catch (error) {
    showProblem(actions, error, "Retry activation. If it repeats, restart the local Dashboard service.");
  }
}

function pollActivation(delaySeconds: number): void {
  activationTimer = window.setTimeout(async () => {
    try {
      const state = await api<ActivationStatus>("/app/api/activation");
      if (state.status === "AUTHENTICATED" && state.principal !== null && state.csrf_token !== null) {
        clearActivationTimer();
        session = { status: "AUTHENTICATED", principal: state.principal, csrf_token: state.csrf_token };
        scheduleSessionExpiry();
        await renderRoute();
        return;
      }
      pollActivation(delaySeconds);
    } catch (error) {
      clearActivationTimer();
      if (error instanceof RequestProblem && [401, 404, 410].includes(error.status)) {
        renderActivation();
        return;
      }
      const main = page("Activation interrupted", "LOCAL CONTROL PLANE", "The browser could not complete the local activation handshake.");
      showProblem(main, error, "Start a new activation request.");
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
  if (session === null) {
    renderActivation();
    return;
  }
  clearLiveStatusTimer();
  currentRoute = routeFromHash();
  if (currentRoute === "overview") await renderOverview();
  if (currentRoute === "devices") await renderDevices();
  if (currentRoute === "projects") await renderProjects();
  if (currentRoute === "candidates") await renderCandidates();
  if (currentRoute === "evidence") await renderEvidence();
  if (currentRoute === "decision") await renderDecision();
  if (currentRoute === "assurance") await renderAssurance();
}

async function renderDevices(): Promise<void> {
  const generation = liveStatusGeneration;
  const main = page(
    "Live devices",
    "READ-ONLY OBSERVATION",
    "Connection, heartbeat freshness, and device-reported health are independent signals. No serial command is sent."
  );
  const toolbar = el("section", "toolbar live-toolbar");
  const refresh = button("Refresh now", "button secondary");
  const cadence = statusBadge("Live · every 1 s");
  refresh.addEventListener("click", () => void refreshLiveStatus(main, generation));
  toolbar.append(cadence, refresh);
  const announcement = el("p", "sr-only");
  announcement.setAttribute("aria-live", "polite");
  announcement.setAttribute("aria-atomic", "true");
  const content = el("section", "live-status-region");
  content.setAttribute("aria-label", "Live device status");
  content.setAttribute("aria-busy", "true");
  content.append(el("p", "muted", "Loading the current read-only device status…"));
  main.append(toolbar, announcement, content);
  shell(main);
  await refreshLiveStatus(main, generation);
}

async function refreshLiveStatus(main: HTMLElement, generation: number): Promise<void> {
  if (generation !== liveStatusGeneration || currentRoute !== "devices" || session === null) return;
  if (liveStatusTimer !== null) window.clearTimeout(liveStatusTimer);
  liveStatusTimer = null;
  const content = main.querySelector<HTMLElement>(".live-status-region");
  const announcement = main.querySelector<HTMLElement>("[aria-live='polite']");
  if (content === null || !main.isConnected) return;
  try {
    const result = await api<LiveStatusPage>("/app/api/live-status");
    if (generation !== liveStatusGeneration || currentRoute !== "devices" || !main.isConnected) return;
    content.setAttribute("aria-busy", "false");
    content.replaceChildren(renderLiveStatus(result));
    const signature = result.sources
      .map((source) => `${source.display_name}: ${source.connection}, heartbeat ${source.heartbeat}, device ${source.device_health}`)
      .join(". ");
    if (announcement !== null && signature !== lastLiveAnnouncement) {
      announcement.textContent = signature || "No live device monitor is configured.";
      lastLiveAnnouncement = signature;
    }
    liveStatusTimer = window.setTimeout(
      () => void refreshLiveStatus(main, generation),
      Math.max(1, result.refresh_after_seconds) * 1000
    );
  } catch (error) {
    if (handleProtectedProblem(content, error, "Confirm the local monitor is running, then retry.")) return;
    liveStatusTimer = window.setTimeout(() => void refreshLiveStatus(main, generation), 2000);
  }
}

function renderLiveStatus(result: LiveStatusPage): HTMLElement {
  const wrapper = el("div", "live-status-stack");
  if (result.sources.length === 0) {
    wrapper.append(
      emptyState(
        "No live monitor configured",
        "Restart the Dashboard with --msp430-port COM4 to enable the optional read-only MSP430 UART v1 monitor."
      )
    );
    return wrapper;
  }
  for (const source of result.sources) wrapper.append(renderLiveSource(source));
  wrapper.append(el("p", "live-sampled-at muted", `Status sampled ${formatDate(result.observed_at)}`));
  return wrapper;
}

function renderLiveSource(source: LiveSourceStatus): HTMLElement {
  const sourcePanel = el("article", "live-source-panel");
  const heading = el("div", "card-heading");
  const title = el("div");
  title.append(el("p", "eyebrow", "LIVE SOURCE"), el("h2", undefined, source.display_name));
  heading.append(title, statusBadge(source.access_mode));

  const stateGrid = el("section", "device-state-grid");
  stateGrid.setAttribute("aria-label", `${source.display_name} current states`);
  stateGrid.append(
    liveStateCard("Connection", source.connection, connectionDescription(source.connection)),
    liveStateCard("Heartbeat", source.heartbeat, heartbeatDescription(source)),
    liveStateCard("Device health", source.device_health, healthDescription(source))
  );

  const detail = el("section", "live-detail-banner");
  detail.append(statusBadge(source.detail_code), el("p", undefined, source.detail_message));

  const columns = el("div", "content-columns");
  const telemetry = el("section", "panel");
  telemetry.append(el("p", "eyebrow", "LATEST VALID TEL FRAME"), el("h3", undefined, "Telemetry position"));
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
    issues.append(el("h4", undefined, "Decoded firmware reports"));
    const list = el("ul", "issue-list");
    for (const issue of source.reported_issues) {
      const item = el("li");
      item.append(el("code", undefined, issue.mask), el("span", undefined, issue.label));
      list.append(item);
    }
    issues.append(list, el("p", "muted", "Decoded from the versioned MSP430 UART v1 adapter; these are device reports, not ForgeGate diagnoses."));
    telemetry.append(issues);
  }

  const monitor = el("section", "panel");
  monitor.append(el("p", "eyebrow", "MONITOR DIAGNOSTICS"), el("h3", undefined, "Read-only transport"));
  const monitorValues = el("dl", "definition-list");
  monitorValues.append(
    definition("Endpoint", source.endpoint, true),
    definition("Protocol", source.protocol, true),
    definition("Baud", String(source.baud_rate)),
    definition("Stale after", `${source.stale_after_seconds.toFixed(1)} s`),
    definition("Valid frames", String(source.frames_received)),
    definition("Protocol errors", String(source.protocol_errors)),
    definition("Sequence gaps", String(source.sequence_gaps)),
    definition("Reconnects", String(source.reconnects))
  );
  monitor.append(monitorValues);
  columns.append(telemetry, monitor);

  const boundary = el("p", "live-boundary mono", `${source.evidence_boundary} · hardware_control=${source.hardware_control}`);
  sourcePanel.append(heading, stateGrid, detail, columns, boundary);
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
  loadingPage("Overview");
  const main = page("Assurance overview", "CURRENT AUTHORITY", "Service health, authenticated scope, and evidence limitations remain visible together.");
  try {
    const overview = await api<Overview>("/app/api/overview");
    const metrics = el("section", "metric-grid");
    for (const [label, value, tone] of [
      ["Service", "Healthy", "positive"],
      ["Version", overview.forgegate_version, "neutral"],
      ["API", overview.api_version, "neutral"],
      ["Database", `schema v${overview.database_schema_version}`, "neutral"]
    ]) {
      const card = el("article", "metric-card");
      card.append(el("span", undefined, label), el("strong", undefined, value), el("i", `metric-dot ${tone}`));
      metrics.append(card);
    }

    const columns = el("div", "content-columns");
    const authority = el("section", "panel");
    authority.append(el("p", "eyebrow", "AUTHENTICATED PRINCIPAL"), el("h2", undefined, overview.principal.display_name));
    const list = el("dl", "definition-list");
    list.append(
      definition("Role", overview.principal.role),
      definition("Project scopes", overview.principal.project_ids.join(", ")),
      definition("Identity", overview.principal.identity_id, true),
      definition("Trust store", overview.principal.trust_store_id, true),
      definition("Session expires", formatDate(overview.principal.expires_at))
    );
    authority.append(list);

    const boundaries = el("section", "panel warning-panel");
    boundaries.append(el("p", "eyebrow", "CURRENT LIMITATIONS"), el("h2", undefined, "This is not a release decision"));
    const items = el("ul", "limitation-list");
    for (const limitation of overview.limitations) items.append(el("li", undefined, limitation));
    boundaries.append(items, statusBadge(`Hardware ${overview.hardware_access}`));
    columns.append(authority, boundaries);
    main.append(metrics, columns);
  } catch (error) {
    if (handleProtectedProblem(main, error, "Reload the Overview page.")) return;
  }
  shell(main);
}

async function ensureProjects(): Promise<RegisteredProject[]> {
  if (projects.length === 0) {
    const pageResult = await api<ProjectPage>("/app/api/projects?limit=100");
    projects = pageResult.projects;
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

function emptyState(title: string, description: string): HTMLElement {
  const state = el("section", "empty-state");
  state.append(el("span", "empty-mark", "—"), el("h2", undefined, title), el("p", undefined, description));
  return state;
}

async function renderCandidates(): Promise<void> {
  loadingPage("Candidates");
  const main = page(
    "Release candidates",
    "PROJECT-SCOPED WORK",
    "Each lifecycle, evidence, evaluation, and attestation write is independently reviewed; successful writes reload authoritative state."
  );
  try {
    const visible = await ensureProjects();
    if (visible.length === 0) {
      main.append(emptyState("No project available", "Register a project through the established CLI/API before creating a candidate."));
      shell(main);
      return;
    }
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
      selectedProjectId = selector.value;
      resetCandidatePagination();
      void renderCandidates();
    });
    selectorWrap.append(selector);
    toolbar.append(selectorWrap);
    if (session?.principal.role === "operator") {
      const create = button("Create candidate", "button primary");
      create.addEventListener("click", () => openCandidateDialog(main, create));
      toolbar.append(create);
    } else {
      const readOnly = el("p", "muted", "Producer sessions are read-only.");
      toolbar.append(readOnly);
    }
    main.append(toolbar);

    const projectId = selectedProjectId ?? visible[0]?.project_id;
    if (projectId === undefined) return;
    selectedProjectId = projectId;
    const query = new URLSearchParams({ limit: "25" });
    if (candidateCursor !== null) query.set("after_candidate_id", candidateCursor);
    const result = await api<CandidatePage>(
      `/app/api/projects/${encodeURIComponent(projectId)}/candidates?${query.toString()}`
    );
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
      main.append(candidateTable(result.candidates, main));
    }
    main.append(candidatePager(result));
  } catch (error) {
    if (handleProtectedProblem(main, error, "Reload the candidate list and confirm the selected project scope.")) return;
  }
  shell(main);
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
  initialValues?: Record<string, string>
): void {
  const dialog = el("dialog", "review-dialog");
  dialog.setAttribute("aria-labelledby", "candidate-dialog-title");
  const form = el("form", "candidate-form");
  form.method = "dialog";
  const heading = el("h2", undefined, "Create release candidate");
  heading.id = "candidate-dialog-title";
  form.append(el("p", "eyebrow", "DRAFT REQUEST"), heading, el("p", "muted", "Client checks guide this draft. ForgeGate remains authoritative."));
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
  branch.input.value = initialValues?.source_branch ?? branch.input.value;
  track.input.value = initialValues?.release_track ?? track.input.value;
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
    renderCandidateReview(dialog, values, returnFocus);
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
  returnFocus?: HTMLElement
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
    if (workspace !== null) openCandidateDialog(workspace, returnFocus, values);
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
      const done = button("Inspect candidate", "button primary");
      done.addEventListener("click", async () => {
        dialog.close();
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
        body: JSON.stringify(mutation.body)
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
      showProblem(status, new RequestProblem(413, "DASHBOARD_IMPORT_TOO_LARGE", "The selected JSON document leaves insufficient room inside the 4 MiB request envelope.", "browser-side", null), "Choose a JSON document no larger than 3,900,000 bytes.");
      return;
    }
    review.disabled = true;
    status.replaceChildren(el("p", "muted", "Parsing and fingerprinting the selected local document…"));
    try {
      const bytes = await file.arrayBuffer();
      const parsed: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
      if (!isJsonObject(parsed)) throw new Error("The JSON root must be an object.");
      const fingerprint = await sha256Hex(bytes);
      const mutation = kind === "evidence"
        ? evidenceImportMutation(candidate, parsed, file, fingerprint)
        : policyImportMutation(candidate, parsed, file, fingerprint);
      renderReviewedMutation(dialog, candidate, mutation);
    } catch (error) {
      const message = error instanceof Error ? error.message : "The selected file is not valid UTF-8 JSON.";
      showProblem(status, new RequestProblem(422, "DASHBOARD_IMPORT_INVALID", message, "browser-side", null), "Choose the exact versioned JSON document and review it again.");
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
      main.append(summary, columns, ruleTable);
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
