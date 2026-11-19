import { CAPTURE_FLOW_CONTRACT } from "./capture_flow_contract";
import { FORM_CONTRACT } from "./form_contract";
import { RENDER_JOB_TEMPLATE } from "./render_job_template";

export interface Env {
  ASSETS: Fetcher;
  T2_MEDIA: R2Bucket;
  CLIENT_API_TOKEN: string;
  GITHUB_TOKEN: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  GITHUB_API_BASE: string;
  CALLBACK_TOKEN: string;
  PUBLIC_API_BASE: string;
}

type CaptureSlot = "S1" | "S2" | "S3" | "S4";
type JobStatus = "UPLOADING" | "READY" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";

interface MerchantPayload {
  nom: string;
  produit: string;
  prix: string;
  whatsapp: string;
  quartier: string;
  accroche: string;
}

interface CaptureMeta {
  uri: string;
  sha256: string;
  mime_type: string;
  width: number;
  height: number;
  fps: number;
  frame_count: number;
  duration_ms: number;
  source_in_ms: number;
  source_out_ms: number;
  video_codec: string;
  audio_codec: string | null;
  has_audio: boolean;
  captured_voice_usable: boolean;
}

interface StoredJob {
  status: JobStatus;
  job_id: string;
  idempotency_key: string;
  created_at: string;
  updated_at: string;
  merchant_payload: MerchantPayload;
  captures: Partial<Record<CaptureSlot, CaptureMeta>>;
  voice_mode: "registered_voice_clips" | "captured_scene_audio" | "captured_or_registered_fallback";
  job?: Record<string, unknown>;
  github?: Record<string, unknown>;
  result?: unknown;
  error?: unknown;
}

const SLOTS: CaptureSlot[] = ["S1", "S2", "S3", "S4"];
const DURATIONS: Record<CaptureSlot, number> = { S1: 6000, S2: 8000, S3: 7000, S4: 9000 };
const ALLOWED_MIME = new Set(["video/mp4", "video/webm", "video/quicktime"]);

function json(data: unknown, status = 200): Response {
  return Response.json(data, { status, headers: { "cache-control": "no-store" } });
}

function fail(status: number, code: string, message: string, retryable = false): Response {
  return json({ schema_version: "1.0.0", status: "FAILED", code, message, retryable }, status);
}

function clean(value: unknown, name: string, max: number, min = 1): string {
  if (typeof value !== "string") throw new Error(`${name} doit être une chaîne.`);
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length < min || normalized.length > max) throw new Error(`${name} doit contenir entre ${min} et ${max} caractères.`);
  return normalized;
}

function validatePayload(raw: unknown): MerchantPayload {
  if (!raw || typeof raw !== "object") throw new Error("merchant_payload est requis.");
  const value = raw as Record<string, unknown>;
  const payload: Record<string, string> = {};
  for (const field of FORM_CONTRACT.fields) {
    const rawField = value[field.id] ?? (field.required ? undefined : "");
    const normalized = clean(rawField, field.id, field.maxLength, field.minLength);
    if ("pattern" in field && field.pattern && !new RegExp(field.pattern).test(normalized)) {
      throw new Error(`${field.id} ne respecte pas le format attendu.`);
    }
    payload[field.id] = normalized;
  }
  return payload as unknown as MerchantPayload;
}

function validId(value: string): boolean {
  return /^[a-zA-Z0-9][a-zA-Z0-9._-]{7,127}$/.test(value);
}

function jobKey(jobId: string): string { return `jobs/${jobId}/state.json`; }
function idemKey(key: string): string { return `idempotency/${key}.txt`; }
function captureKey(jobId: string, slot: CaptureSlot): string { return `jobs/${jobId}/captures/${slot}.bin`; }

async function sha256Text(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function readJob(env: Env, jobId: string): Promise<StoredJob | null> {
  const object = await env.T2_MEDIA.get(jobKey(jobId));
  return object ? await object.json<StoredJob>() : null;
}

async function writeJob(env: Env, state: StoredJob): Promise<void> {
  state.updated_at = new Date().toISOString();
  await env.T2_MEDIA.put(jobKey(state.job_id), JSON.stringify(state), {
    httpMetadata: { contentType: "application/json" },
    customMetadata: { status: state.status, idempotency_key: state.idempotency_key },
  });
}

async function authorized(request: Request, secret: string): Promise<boolean> {
  const header = request.headers.get("authorization") || "";
  return secret.length > 0 && header === `Bearer ${secret}`;
}

function runtimeCaptureUri(jobId: string, slot: CaptureSlot, mime: string): string {
  const extension = mime === "video/webm" ? "webm" : mime === "video/quicktime" ? "mov" : "mp4";
  return `rushes/runtime/${jobId}/${slot}.${extension}`;
}

function buildRenderJob(state: StoredJob): Record<string, unknown> {
  const job = structuredClone(RENDER_JOB_TEMPLATE) as unknown as Record<string, any>;
  job.job_id = state.job_id;
  job.idempotency_key = state.idempotency_key;
  job.merchant_payload = state.merchant_payload;
  job.capture_manifest = `rushes/runtime/${state.job_id}/capture_manifest.json`;
  job.captures = Object.fromEntries(SLOTS.map((slot) => {
    const capture = state.captures[slot];
    if (!capture) throw new Error(`Capture ${slot} absente.`);
    return [slot, {
      uri: capture.uri,
      duration_ms: capture.duration_ms,
      source_in_ms: capture.source_in_ms,
      has_audio: capture.has_audio,
      sha256: capture.sha256,
      mime_type: capture.mime_type,
      video_codec: capture.video_codec,
      width: capture.width,
      height: capture.height,
      fps: capture.fps,
      frame_count: capture.frame_count,
      rotation_degrees: 0,
      audio_codec: capture.audio_codec,
    }];
  }));
  job.audio_contract.voice_source_mode = state.voice_mode;
  job.audio_plan.voice.mode = state.voice_mode;
  job.audio_plan.voice.fallback_policy = state.voice_mode === "registered_voice_clips"
    ? "registered_clips_are_explicitly_selected_for_this_exemplar"
    : state.voice_mode === "captured_scene_audio"
      ? "no_fallback"
      : "registered_clips_when_capture_has_no_usable_speech";
  job.provenance.control_plane = "cloudflare_worker";
  job.provenance.cloudflare_job_id = state.job_id;
  return job;
}

async function createJob(request: Request, env: Env): Promise<Response> {
  const body = await request.json<Record<string, unknown>>();
  const idempotencyKey = clean(request.headers.get("idempotency-key") || body.idempotency_key, "idempotency_key", 120);
  if (!validId(idempotencyKey)) return fail(400, "T2_INVALID_IDEMPOTENCY_KEY", "Clé d'idempotence invalide.");
  const existing = await env.T2_MEDIA.get(idemKey(idempotencyKey));
  if (existing) {
    const existingId = await existing.text();
    const state = await readJob(env, existingId);
    return json({ job_id: existingId, status: state?.status, idempotent_replay: true }, 200);
  }
  const merchant = validatePayload(body.merchant_payload);
  const mode = body.voice_mode || "captured_or_registered_fallback";
  if (!["registered_voice_clips", "captured_scene_audio", "captured_or_registered_fallback"].includes(String(mode))) {
    return fail(400, "T2_INVALID_VOICE_MODE", "Mode voix invalide.");
  }
  const seed = `${idempotencyKey}\n${JSON.stringify(merchant)}\n${Date.now()}\n${crypto.randomUUID()}`;
  const jobId = `t2-complete-${(await sha256Text(seed)).slice(0, 24)}`;
  const now = new Date().toISOString();
  const state: StoredJob = { status: "UPLOADING", job_id: jobId, idempotency_key: idempotencyKey, created_at: now, updated_at: now, merchant_payload: merchant, captures: {}, voice_mode: mode as StoredJob["voice_mode"] };
  await writeJob(env, state);
  const claim = await env.T2_MEDIA.put(idemKey(idempotencyKey), jobId, {
    onlyIf: { etagDoesNotMatch: "*" },
    httpMetadata: { contentType: "text/plain" },
  });
  if (!claim) {
    await env.T2_MEDIA.delete(jobKey(jobId));
    const winner = await env.T2_MEDIA.get(idemKey(idempotencyKey));
    if (!winner) return fail(503, "T2_IDEMPOTENCY_RACE", "La réservation idempotente doit être rejouée.", true);
    const existingId = await winner.text();
    const existingState = await readJob(env, existingId);
    return json({ job_id: existingId, status: existingState?.status, idempotent_replay: true }, 200);
  }
  return json({ job_id: jobId, status: state.status, required_captures: SLOTS, capture_contract: "/v1/contracts/capture-flow" }, 201);
}

async function uploadCapture(request: Request, env: Env, jobId: string, slot: CaptureSlot): Promise<Response> {
  const state = await readJob(env, jobId);
  if (!state) return fail(404, "T2_JOB_NOT_FOUND", "Job introuvable.");
  if (!["UPLOADING", "READY"].includes(state.status)) return fail(409, "T2_CAPTURE_PHASE_CLOSED", "Les captures ne peuvent plus être modifiées.");
  const mime = (request.headers.get("content-type") || "").split(";", 1)[0].toLowerCase();
  if (!ALLOWED_MIME.has(mime)) return fail(415, "T2_UNSUPPORTED_MEDIA", "Conteneur vidéo non pris en charge.");
  const length = Number(request.headers.get("content-length") || 0);
  if (length > 250 * 1024 * 1024) return fail(413, "T2_MEDIA_TOO_LARGE", "La capture dépasse 250 Mio.");
  const sha = (request.headers.get("x-content-sha256") || "").toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(sha)) return fail(400, "T2_MISSING_MEDIA_SHA256", "x-content-sha256 est requis.");
  const width = Number(request.headers.get("x-video-width"));
  const height = Number(request.headers.get("x-video-height"));
  const fps = Number(request.headers.get("x-video-fps"));
  const frames = Number(request.headers.get("x-video-frames"));
  const duration = Number(request.headers.get("x-video-duration-ms"));
  const hasAudio = request.headers.get("x-has-audio") === "true";
  if (![width, height, fps, frames, duration].every(Number.isFinite) || width < 320 || height < 320 || fps < 12 || fps > 120 || Math.abs(duration - DURATIONS[slot]) > 1000) {
    return fail(422, "T2_INVALID_MEDIA_METADATA", "Métadonnées vidéo incompatibles avec la scène.");
  }
  const object = await env.T2_MEDIA.put(captureKey(jobId, slot), request.body, { sha256: sha, httpMetadata: { contentType: mime }, customMetadata: { job_id: jobId, slot } });
  if (object.size > 250 * 1024 * 1024) {
    await env.T2_MEDIA.delete(captureKey(jobId, slot));
    return fail(413, "T2_MEDIA_TOO_LARGE", "La capture dépasse 250 Mio.");
  }
  if (!object.checksums.sha256) return fail(500, "T2_R2_CHECKSUM_MISSING", "R2 n'a pas confirmé le checksum.", true);
  const actualSha = [...new Uint8Array(object.checksums.sha256)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  if (actualSha !== sha) {
    await env.T2_MEDIA.delete(captureKey(jobId, slot));
    return fail(422, "T2_MEDIA_CHECKSUM_MISMATCH", "Le contenu reçu ne correspond pas à son SHA-256.");
  }
  state.captures[slot] = { uri: runtimeCaptureUri(jobId, slot, mime), sha256: sha, mime_type: mime, width, height, fps, frame_count: frames, duration_ms: DURATIONS[slot], source_in_ms: 0, source_out_ms: DURATIONS[slot], video_codec: clean(request.headers.get("x-video-codec") || "h264", "video_codec", 30), audio_codec: hasAudio ? clean(request.headers.get("x-audio-codec") || "aac", "audio_codec", 30) : null, has_audio: hasAudio, captured_voice_usable: hasAudio };
  state.status = SLOTS.every((name) => Boolean(state.captures[name])) ? "READY" : "UPLOADING";
  await writeJob(env, state);
  return json({ job_id: jobId, slot, status: state.status, sha256: actualSha }, 201);
}

async function dispatch(request: Request, env: Env, jobId: string): Promise<Response> {
  const state = await readJob(env, jobId);
  if (!state) return fail(404, "T2_JOB_NOT_FOUND", "Job introuvable.");
  if (state.status === "QUEUED" || state.status === "RUNNING" || state.status === "COMPLETED") return json({ job_id: jobId, status: state.status, idempotent_replay: true });
  const retryingDispatch = state.status === "FAILED" && record(state.error)?.code === "T2_GITHUB_DISPATCH_FAILED";
  if ((!retryingDispatch && state.status !== "READY") || !SLOTS.every((slot) => state.captures[slot])) return fail(409, "T2_CAPTURES_INCOMPLETE", "Les quatre captures acceptées sont requises.");
  state.job = buildRenderJob(state);
  state.status = "QUEUED";
  await writeJob(env, state);
  const githubApi = (env.GITHUB_API_BASE || "https://api.github.com").replace(/\/$/, "");
  let response: Response;
  try {
    response = await fetch(`${githubApi}/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/dispatches`, {
      method: "POST",
      headers: { "accept": "application/vnd.github+json", "authorization": `Bearer ${env.GITHUB_TOKEN}`, "content-type": "application/json", "user-agent": "T2-Cloudflare-Control-Plane/1.0", "x-github-api-version": "2026-03-10" },
      body: JSON.stringify({ event_type: "t2_render_job", client_payload: { job_id: jobId, api_base: env.PUBLIC_API_BASE } }),
    });
  } catch (error) {
    state.status = "FAILED";
    state.error = { code: "T2_GITHUB_DISPATCH_FAILED", message: error instanceof Error ? error.message : "network error" };
    await writeJob(env, state);
    return fail(502, "T2_GITHUB_DISPATCH_FAILED", "GitHub Actions est temporairement injoignable.", true);
  }
  if (!response.ok) {
    state.status = "FAILED";
    state.error = { code: "T2_GITHUB_DISPATCH_FAILED", status: response.status, body: (await response.text()).slice(0, 1000) };
    await writeJob(env, state);
    return fail(502, "T2_GITHUB_DISPATCH_FAILED", "GitHub Actions n'a pas accepté le job.", true);
  }
  return json({ job_id: jobId, status: state.status }, 202);
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function validateCallbackPayload(state: StoredJob, status: string, body: Record<string, unknown>): string | null {
  if (status === "COMPLETED") {
    const result = record(body.result);
    const output = record(result?.output);
    const quality = record(result?.quality);
    const inputs = record(result?.inputs);
    const job = record(state.job);
    const audioPlan = record(job?.audio_plan);
    const expectedMusic = record(audioPlan?.music);
    const expectedOutput = record(job?.output);
    if (!result || result.schema_version !== "1.0.0" || result.status !== "COMPLETED") return "RenderResult absent ou invalide.";
    if (result.job_id !== state.job_id || result.idempotency_key !== state.idempotency_key) return "RenderResult rattaché à un autre job.";
    if (!output || typeof output.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(output.sha256)) return "Empreinte de sortie RenderResult invalide.";
    if (!quality || quality.status !== "PASS") return "Le QC RenderResult n'est pas PASS.";
    if (!inputs || !expectedMusic || inputs.music_source_sha256 !== expectedMusic.source_sha256) return "La source musicale du résultat diverge du RenderJob.";
    if (!expectedOutput || output.uri !== expectedOutput.uri) return "La sortie du résultat diverge du RenderJob.";
    if (result.template_id !== job?.template_id || result.template_version !== job?.template_version || result.profile_used !== job?.execution_profile) return "Le profil du résultat diverge du RenderJob.";
    const captureSha = record(inputs.capture_sha256);
    if (!captureSha || SLOTS.some((slot) => captureSha[slot] !== state.captures[slot]?.sha256)) return "Les captures du résultat divergent du RenderJob.";
  }
  if (status === "FAILED") {
    const error = record(body.error);
    if (!error || error.schema_version !== "1.0.0" || error.status !== "FAILED") return "RenderError absent ou invalide.";
    if (error.job_id !== state.job_id || typeof error.code !== "string" || typeof error.message !== "string") return "RenderError rattaché à un autre job ou incomplet.";
  }
  return null;
}

async function callback(request: Request, env: Env, jobId: string): Promise<Response> {
  if (!(await authorized(request, env.CALLBACK_TOKEN))) return fail(401, "T2_UNAUTHORIZED", "Authentification requise.");
  const state = await readJob(env, jobId);
  if (!state) return fail(404, "T2_JOB_NOT_FOUND", "Job introuvable.");
  const body = await request.json<Record<string, unknown>>();
  const status = String(body.status);
  if (!["RUNNING", "COMPLETED", "FAILED"].includes(status)) return fail(400, "T2_INVALID_STATUS", "Statut de callback invalide.");
  if (state.status === "COMPLETED" && status !== "COMPLETED") return fail(409, "T2_TERMINAL_JOB", "Un résultat terminé ne peut pas régresser.");
  if (status === "RUNNING" && !["QUEUED", "RUNNING"].includes(state.status)) return fail(409, "T2_INVALID_STATUS_TRANSITION", `Transition ${state.status} → RUNNING interdite.`);
  if ((status === "COMPLETED" || status === "FAILED") && !["QUEUED", "RUNNING", "FAILED", "COMPLETED"].includes(state.status)) return fail(409, "T2_INVALID_STATUS_TRANSITION", `Transition ${state.status} → ${status} interdite.`);
  const invalid = validateCallbackPayload(state, status, body);
  if (invalid) return fail(422, "T2_INVALID_CALLBACK_PAYLOAD", invalid);
  state.status = status as JobStatus;
  state.github = { run_id: body.github_run_id, run_url: body.github_run_url };
  if (status === "COMPLETED") state.result = body.result;
  if (status === "FAILED") state.error = body.error;
  await writeJob(env, state);
  return json({ job_id: jobId, status: state.status });
}

async function assetResponse(request: Request, env: Env): Promise<Response> {
  const response = await env.ASSETS.fetch(request);
  const headers = new Headers(response.headers);
  headers.set("content-security-policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
  headers.set("permissions-policy", "camera=(self), microphone=(self), geolocation=()");
  headers.set("referrer-policy", "no-referrer");
  headers.set("x-content-type-options", "nosniff");
  headers.set("x-frame-options", "DENY");
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

async function handle(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const parts = url.pathname.split("/").filter(Boolean);
  if (request.method === "GET" && url.pathname === "/health") return json({ status: "ok", service: "t2-avant-apres-control-plane", render_plane: "github_actions" });
  if (request.method === "GET" && url.pathname === "/v1/contracts/capture-flow") return json(CAPTURE_FLOW_CONTRACT);
  if (request.method === "GET" && url.pathname === "/v1/contracts/form") return json(FORM_CONTRACT);
  if (request.method === "POST" && url.pathname === "/v1/jobs") {
    if (!(await authorized(request, env.CLIENT_API_TOKEN))) return fail(401, "T2_UNAUTHORIZED", "Jeton client requis.");
    return createJob(request, env);
  }
  if (parts.length >= 3 && parts[0] === "v1" && parts[1] === "jobs" && validId(parts[2])) {
    const jobId = parts[2];
    if (request.method === "GET" && parts.length === 3) {
      const state = await readJob(env, jobId);
      if (!state) return fail(404, "T2_JOB_NOT_FOUND", "Job introuvable.");
      return json({ job_id: jobId, status: state.status, created_at: state.created_at, updated_at: state.updated_at, captures: Object.keys(state.captures), github: state.github, result: state.result, error: state.error });
    }
    if (request.method === "PUT" && parts.length === 5 && parts[3] === "captures" && SLOTS.includes(parts[4] as CaptureSlot)) {
      if (!(await authorized(request, env.CLIENT_API_TOKEN))) return fail(401, "T2_UNAUTHORIZED", "Jeton client requis.");
      return uploadCapture(request, env, jobId, parts[4] as CaptureSlot);
    }
    if (request.method === "POST" && parts.length === 4 && parts[3] === "dispatch") {
      if (!(await authorized(request, env.CLIENT_API_TOKEN))) return fail(401, "T2_UNAUTHORIZED", "Jeton client requis.");
      return dispatch(request, env, jobId);
    }
    if (parts.length === 4 && parts[3] === "payload" && request.method === "GET") {
      if (!(await authorized(request, env.CALLBACK_TOKEN))) return fail(401, "T2_UNAUTHORIZED", "Authentification requise.");
      const state = await readJob(env, jobId);
      if (!state?.job) return fail(409, "T2_JOB_NOT_DISPATCHED", "RenderJob indisponible.");
      if (!["QUEUED", "RUNNING"].includes(state.status)) return fail(409, "T2_JOB_NOT_RUNNABLE", `Le job est ${state.status}.`);
      if (state.status === "QUEUED") {
        state.status = "RUNNING";
        await writeJob(env, state);
      }
      return json({ job: state.job });
    }
    if (parts.length === 5 && parts[3] === "captures" && SLOTS.includes(parts[4] as CaptureSlot) && request.method === "GET") {
      if (!(await authorized(request, env.CALLBACK_TOKEN))) return fail(401, "T2_UNAUTHORIZED", "Authentification requise.");
      const state = await readJob(env, jobId);
      const meta = state?.captures[parts[4] as CaptureSlot];
      if (!meta) return fail(404, "T2_CAPTURE_NOT_FOUND", "Capture introuvable.");
      const object = await env.T2_MEDIA.get(captureKey(jobId, parts[4] as CaptureSlot));
      if (!object) return fail(404, "T2_CAPTURE_NOT_FOUND", "Capture introuvable.");
      return new Response(object.body, { headers: { "content-type": meta.mime_type, "content-length": String(object.size), "x-content-sha256": meta.sha256, "cache-control": "no-store" } });
    }
    if (parts.length === 4 && parts[3] === "events" && request.method === "POST") return callback(request, env, jobId);
  }
  if ((request.method === "GET" || request.method === "HEAD") && !url.pathname.startsWith("/v1/")) {
    return assetResponse(request, env);
  }
  return fail(404, "T2_ROUTE_NOT_FOUND", "Route inconnue.");
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try { return await handle(request, env); }
    catch (error) {
      const message = error instanceof Error ? error.message : "Erreur inattendue.";
      return fail(400, "T2_INVALID_REQUEST", message);
    }
  },
};
