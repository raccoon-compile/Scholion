import { useCallback, useEffect, useState } from "react";

import type { UpdateActivationResult, UpdateClient, UpdateStatus } from "./api/updates";
import { type Theme, WorkspaceHeader } from "./components/WorkspaceHeader";

interface UpdatesWorkspaceProps {
  updates: UpdateClient;
  theme: Theme;
  onThemeChange: (theme: Theme) => void;
}

type TransientState =
  | "idle"
  | "checking"
  | "staging"
  | "preparing"
  | "activating"
  | "failure";

function formatBytes(value: number | undefined): string | null {
  if (value === undefined) return null;
  const units = ["B", "KB", "MB", "GB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function stateTitle(
  status: UpdateStatus | null,
  transient: TransientState,
  activation: UpdateActivationResult | null,
): string {
  if (transient === "checking") return "Checking for updates";
  if (transient === "staging") return "Verifying update package";
  if (transient === "preparing") return "Re-verifying staged update";
  if (transient === "activating") return "Handing update to the operating system";
  if (transient === "failure") return "Update action could not finish";
  if (activation?.activation_state === "handoff_started") return "Installation handoff started";
  if (!status) return "Loading update state";
  if (status.activation_state === "ready_to_install") return "Ready for installation handoff";
  switch (status.state) {
    case "off":
      return "Update checking is off";
    case "never_checked":
      return "Never checked";
    case "up_to_date":
      return "Up to date";
    case "trusted_update_available":
      return "Trusted update available";
    case "staged":
      return "Trusted update staged";
  }
}

export function UpdatesWorkspace({
  updates,
  theme,
  onThemeChange,
}: UpdatesWorkspaceProps) {
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [transient, setTransient] = useState<TransientState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [activation, setActivation] = useState<UpdateActivationResult | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await updates.status());
    } catch {
      setError("Scholion could not read the local update state.");
      setTransient("failure");
    }
  }, [updates]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  async function checkForUpdates() {
    setTransient("checking");
    setError(null);
    try {
      setStatus(await updates.check());
      setTransient("idle");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Scholion could not complete the trusted update request",
      );
      setTransient("failure");
    }
  }

  async function stageUpdate() {
    setTransient("staging");
    setError(null);
    try {
      setStatus(await updates.stage());
      setTransient("idle");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Scholion could not verify the update package",
      );
      setTransient("failure");
    }
  }

  async function prepareActivation() {
    setTransient("preparing");
    setError(null);
    setActivation(null);
    try {
      setStatus(await updates.prepareActivation());
      setTransient("idle");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Scholion could not re-verify the staged update",
      );
      setTransient("failure");
    }
  }

  async function activateUpdate() {
    setTransient("activating");
    setError(null);
    try {
      setActivation(await updates.activate());
      setTransient("idle");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Scholion could not hand the verified update to the operating system",
      );
      setTransient("failure");
    }
  }

  const busy =
    transient === "checking" ||
    transient === "staging" ||
    transient === "preparing" ||
    transient === "activating";
  const size = formatBytes(status?.download_size_bytes);

  return (
    <section className="updates-workspace">
      <WorkspaceHeader
        eyebrow="Application updates"
        title="Keep Scholion trustworthy."
        theme={theme}
        onThemeChange={onThemeChange}
      />

      <div className="updates-grid">
        <article className="updates-card" aria-labelledby="update-state-heading">
          <p className="eyebrow">Update state</p>
          <h2 id="update-state-heading">{stateTitle(status, transient, activation)}</h2>
          <p role="status" aria-live="polite">
            {transient === "checking"
              ? "Fetching a small signed release manifest and verifying it on this computer."
              : transient === "staging"
                ? "Downloading the signed release package and checking its exact size and SHA-256 before staging it."
                : transient === "preparing"
                  ? "Re-checking the signed release metadata and exact staged bytes before native installation handoff."
                  : transient === "activating"
                    ? "Passing the exact verified package to the operating system through Scholion's fixed native boundary."
                    : error ??
                      activation?.message ??
                      status?.message ??
                      "Reading local update state…"}
          </p>

          {status && (
            <dl className="updates-facts">
              <div>
                <dt>This version</dt>
                <dd>{status.current_version}</dd>
              </div>
              {status.available_version && (
                <div>
                  <dt>Trusted release</dt>
                  <dd>{status.available_version}</dd>
                </div>
              )}
              {size && (
                <div>
                  <dt>Package size</dt>
                  <dd>{size}</dd>
                </div>
              )}
            </dl>
          )}

          <div className="updates-actions">
            <button
              type="button"
              onClick={() => void checkForUpdates()}
              disabled={!status?.enabled || busy}
            >
              {transient === "checking" ? "Checking…" : "Check for updates"}
            </button>
            {status?.state === "trusted_update_available" && (
              <button
                type="button"
                className="secondary-button"
                onClick={() => void stageUpdate()}
                disabled={busy}
              >
                {transient === "staging" ? "Verifying…" : "Download and verify"}
              </button>
            )}
            {status?.state === "staged" &&
              status.activation_state !== "ready_to_install" && (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void prepareActivation()}
                  disabled={busy}
                >
                  {transient === "preparing"
                    ? "Re-verifying…"
                    : "Prepare for installation"}
                </button>
              )}
            {status?.activation_state === "ready_to_install" && !activation && (
              <button
                type="button"
                className="secondary-button"
                onClick={() => void activateUpdate()}
                disabled={busy}
              >
                {transient === "activating" ? "Handing off…" : "Continue installation"}
              </button>
            )}
          </div>
        </article>

        <aside className="updates-card updates-privacy" aria-labelledby="update-privacy-heading">
          <p className="eyebrow">Privacy and trust</p>
          <h2 id="update-privacy-heading">A version check is network activity, not telemetry.</h2>
          <p>
            Scholion asks one fixed GitHub-hosted location for signed release metadata only when
            you choose <strong>Check for updates</strong>. It does not send an installation ID,
            recording or transcript information, research state, hardware inventory, model
            inventory, or product-behavior data.
          </p>
          <p>
            GitHub and its delivery network can still see ordinary connection metadata such as
            your IP address and request time. Existing local work remains available when update
            checking is off, unavailable, or offline.
          </p>
          <p>
            Release metadata must pass Scholion&apos;s signature, expiry, and rollback checks before
            it can authorize a package. A downloaded package is staged only after its signed size
            and SHA-256 match exactly.
          </p>
        </aside>
      </div>

      {status?.state === "staged" && transient === "idle" && (
        <div className="updates-boundary-note" role="note">
          {activation?.activation_state === "handoff_started" ? (
            <>
              <strong>Operating-system handoff started.</strong> Scholion has not declared the
              update installed. Complete any operating-system replacement, approval, or restart
              step it presents.
            </>
          ) : status.activation_state === "ready_to_install" ? (
            <>
              <strong>Exact staged bytes re-verified.</strong> Continue installation asks the
              native host to hand off only this verified package. Platform security checks remain
              in force and can still refuse the update.
            </>
          ) : (
            <>
              <strong>Installation is deliberately separate.</strong> This build has verified and
              staged the package. Prepare for installation re-verifies the exact signed metadata
              and staged bytes, but does not execute anything.
            </>
          )}
        </div>
      )}
    </section>
  );
}
