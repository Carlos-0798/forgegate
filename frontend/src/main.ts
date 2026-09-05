import "./styles.css";

type Role = "operator" | "producer";
type Route = "overview" | "projects" | "candidates";

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

interface ApiProblem {
  error?: { code?: string; message?: string; request_id?: string };
}

class RequestProblem extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId: string
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
  const candidate = window.location.hash.replace(/^#\/?/, "");
  return candidate === "projects" || candidate === "candidates" ? candidate : "overview";
}

function requestId(): string {
  return `dashboard-${crypto.randomUUID()}`;
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
    const problem = payload as ApiProblem;
    throw new RequestProblem(
      response.status,
      problem.error?.code ?? "DASHBOARD_REQUEST_FAILED",
      problem.error?.message ?? "The local service rejected the request.",
      problem.error?.request_id ?? response.headers.get("X-Request-ID") ?? "unavailable"
    );
  }
  return payload as T;
}

function clearActivationTimer(): void {
  if (activationTimer !== null) window.clearTimeout(activationTimer);
  activationTimer = null;
}

function clearSessionExpiryTimer(): void {
  if (sessionExpiryTimer !== null) window.clearTimeout(sessionExpiryTimer);
  sessionExpiryTimer = null;
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

function showProblem(container: HTMLElement, error: unknown, recovery: string): void {
  const problem = error instanceof RequestProblem ? error : null;
  const panel = el("section", "problem-panel");
  panel.setAttribute("role", "alert");
  panel.append(
    el("p", "problem-code", `ERROR [${problem?.code ?? "DASHBOARD_UNEXPECTED_ERROR"}]`),
    el("h2", undefined, "The request did not complete"),
    el("p", undefined, problem?.message ?? "An unexpected browser-side error occurred."),
    el("p", "recovery", `Safe next step: ${recovery}`),
    el("p", "request-id", `Request ID: ${problem?.requestId ?? "not available"}`)
  );
  container.replaceChildren(panel);
}

function statusBadge(value: string): HTMLSpanElement {
  const normalized = value.toLowerCase();
  const tone = ["pass", "ready", "complete", "authenticated"].some((item) =>
    normalized.includes(item)
  )
    ? "positive"
    : ["fail", "error", "denied"].some((item) => normalized.includes(item))
      ? "negative"
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
  for (const [route, label, detail] of [
    ["overview", "Overview", "Service and authority"],
    ["projects", "Projects", "Immutable profiles"],
    ["candidates", "Candidates", "Release work and audit"]
  ] as const) {
    const link = el("a", currentRoute === route ? "nav-link active" : "nav-link");
    link.href = `#/${route}`;
    if (currentRoute === route) link.setAttribute("aria-current", "page");
    link.append(el("strong", undefined, label), el("span", undefined, detail));
    nav.append(link);
  }
  const planned = el("section", "planned-nav");
  planned.append(el("p", "eyebrow", "LATER GATES"));
  for (const label of ["Evidence", "Decision", "Assurance", "Plugins", "Security"]) {
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
    ["Hardware", "Not accessed"],
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
    el("p", "mono subtle", "hardware_access = NOT_PERFORMED")
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
  currentRoute = routeFromHash();
  if (currentRoute === "overview") await renderOverview();
  if (currentRoute === "projects") await renderProjects();
  if (currentRoute === "candidates") await renderCandidates();
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
  const main = page("Release candidates", "PROJECT-SCOPED WORK", "Candidate state and request completion are shown separately; collection and evaluation remain later actions.");
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

function openCandidateDialog(main: HTMLElement, returnFocus?: HTMLElement): void {
  const dialog = el("dialog", "review-dialog");
  dialog.setAttribute("aria-labelledby", "candidate-dialog-title");
  const form = el("form", "candidate-form");
  form.method = "dialog";
  const heading = el("h2", undefined, "Create release candidate");
  heading.id = "candidate-dialog-title";
  form.append(el("p", "eyebrow", "DRAFT REQUEST"), heading, el("p", "muted", "Client checks guide this draft. ForgeGate remains authoritative."));
  const version = field("Version", "version", "1.0.0", "text", true);
  const commit = field("Commit SHA", "commit", "40 or 64 lowercase hexadecimal characters", "text", true);
  commit.input.addEventListener("input", () => commit.input.setCustomValidity(""));
  const branch = field("Source branch", "branch", "main", "text", true);
  const track = field("Release track", "track", "pull-request", "text", true);
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
    if (workspace !== null) openCandidateDialog(workspace, returnFocus);
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
    } catch (error) {
      showProblem(status, error, "Return to the draft, reload current state if needed, and review before trying again.");
      back.disabled = false;
      confirm.disabled = false;
    }
  });
  controls.append(back, confirm);
  review.append(details, status, controls);
  dialog.replaceChildren(review);
  confirm.focus();
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
    content.replaceChildren(heading, details, auditSection);
    content.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    handleProtectedProblem(content, error, "Return to the candidate list and retry the inspection.");
  }
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
});
void loadSession();
