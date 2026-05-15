import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const projectRoot = join(root, "..", "..");

function spawnLogged(command, args, options = {}) {
  const child = spawn(command, args, { stdio: "inherit", shell: false, ...options });
  return child;
}

async function isBackendReady() {
  try {
    const response = await fetch("http://127.0.0.1:8787/health");
    return response.ok;
  } catch {
    return false;
  }
}

if (!(await isBackendReady())) {
  const candidates = [
    process.env.PROMPT_AGENT_PYTHON,
    join(projectRoot, ".venv", "Scripts", "python.exe"),
    "python",
  ].filter(Boolean);
  const python = candidates.find((candidate) => candidate && (candidate === "python" || existsSync(candidate)));
  if (python) {
    spawnLogged(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8787"], { cwd: projectRoot });
  } else {
    console.log("Backend is not running. Start it with: python -m uvicorn app.main:app --host 127.0.0.1 --port 8787");
  }
}

const localTauriJs = join(root, "node_modules", "@tauri-apps", "cli", "tauri.js");
const tauriCommand = existsSync(localTauriJs) ? process.execPath : "tauri";
const tauriArgs = existsSync(localTauriJs) ? [localTauriJs, "dev"] : ["dev"];
const tauriChild = spawnLogged(tauriCommand, tauriArgs, { cwd: root });

tauriChild.on("exit", (code) => {
  process.exit(code ?? 0);
});
