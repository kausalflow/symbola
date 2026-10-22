"""Where attestation runs execute.

Both the implementation and the contract's own test code are untrusted, so
an attestation run happens in a sandbox, never in the CLI process:

- `container`: Docker with no network (unless the contract declares it),
  memory, CPU and process limits, a read-only root filesystem, no
  capabilities, and an unprivileged user. This is the default whenever a
  Docker daemon is reachable.
- `process`: a separate Python process in its own user and network
  namespace (`unshare -rn`) with memory and CPU rlimits. It blocks the
  network but not the filesystem, so attestations record it as the weaker
  sandbox.

Contract and implementation are copied into a fresh directory first, and
digests are computed from those copies, so what was attested is exactly
what ran.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import symbolon

# Pinned by digest so every runner builds the same environment.
BASE_IMAGE = "python:3.13-slim@sha256:cf50a4f6ac4f026458b08d5222023d700ac806410dff5e9ca8728fa44f2b850f"
RUNTIME_PACKAGES = ["pydantic", "pydantic-core", "hypothesis"]


class SandboxError(Exception):
    pass


class SandboxUnavailable(SandboxError):
    pass


@dataclass
class Limits:
    timeout_seconds: int = 120
    memory_mb: int = 1024


@dataclass
class Workspace:
    """Private copies of what is about to run."""

    root: Path
    contract: Path
    impl: Path
    out: Path
    deps: Path

    @classmethod
    def create(cls, contract_dir: Path, impl_dir: Path) -> "Workspace":
        root = Path(tempfile.mkdtemp(prefix="symbolon-run-"))
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".*")
        ws = cls(root, root / "contract", root / "impl", root / "out", root / "deps")
        shutil.copytree(contract_dir, ws.contract, ignore=ignore)
        shutil.copytree(impl_dir, ws.impl, ignore=ignore)
        ws.out.mkdir()
        ws.deps.mkdir()
        return ws

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def package_versions() -> dict[str, str]:
    return {name: importlib.metadata.version(name) for name in RUNTIME_PACKAGES}


def environment_digest(descriptor: dict) -> str:
    """Digest of the inputs that determine behavior, not of machine-specific ids."""
    stable = {k: v for k, v in descriptor.items() if k not in {"image_id", "isolation"}}
    blob = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def _tail(proc: subprocess.CompletedProcess) -> str:
    lines = (proc.stderr or proc.stdout or "").strip().splitlines()
    return "\n".join(lines[-8:]) or f"exited with {proc.returncode}"


class Sandbox:
    kind = "abstract"

    def environment(self) -> dict:
        raise NotImplementedError

    def run(self, ws: Workspace, entrypoint: str, *, network: bool, lockfile: bool, limits: Limits) -> dict:
        raise NotImplementedError

    def isolation(self, network: bool) -> dict:
        raise NotImplementedError


class ProcessSandbox(Sandbox):
    kind = "process"

    def __init__(self) -> None:
        if shutil.which("unshare") is None:
            raise SandboxUnavailable("the process sandbox needs `unshare` (util-linux)")
        probe = subprocess.run(["unshare", "-rn", "true"], capture_output=True)
        if probe.returncode != 0:
            raise SandboxUnavailable("unprivileged user namespaces are not allowed on this machine")

    def environment(self) -> dict:
        return {
            "sandbox": self.kind,
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "os": platform.system().lower(),
            "arch": platform.machine(),
            "packages": package_versions(),
            "symbolon": symbolon.__version__,
        }

    def isolation(self, network: bool) -> dict:
        return {
            "network": "allowed (declared by contract)" if network else "none (separate network namespace)",
            "filesystem": "not isolated",
            "user": "separate user namespace",
        }

    def run(self, ws: Workspace, entrypoint: str, *, network: bool, lockfile: bool, limits: Limits) -> dict:
        if lockfile:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "--no-deps", "--no-cache-dir",
                 "--target", str(ws.deps), "-r", str(ws.impl / "requirements.lock")],
                capture_output=True, text=True, timeout=600,
            )
            if proc.returncode != 0:
                raise SandboxError("installing requirements.lock failed:\n" + _tail(proc))

        out = ws.out / "result.json"
        cmd = [sys.executable, "-I", "-m", "symbolon.worker", "test",
               str(ws.contract), str(out), str(ws.impl / entrypoint)]
        if lockfile:
            cmd += ["--deps", str(ws.deps)]
        if not network:
            cmd = ["unshare", "-rn"] + cmd

        def limit() -> None:
            mem = limits.memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            resource.setrlimit(resource.RLIMIT_CPU, (limits.timeout_seconds, limits.timeout_seconds))

        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(ws.root)}
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=limits.timeout_seconds,
                                  cwd=ws.root, env=env, preexec_fn=limit)
        except subprocess.TimeoutExpired:
            raise SandboxError(f"timed out after {limits.timeout_seconds}s") from None
        if proc.returncode != 0 or not out.exists():
            raise SandboxError(_tail(proc))
        return json.loads(out.read_text())


class ContainerSandbox(Sandbox):
    kind = "container"

    def __init__(self, docker: str = "docker") -> None:
        self.docker = shutil.which(docker)
        if self.docker is None:
            raise SandboxUnavailable("docker is not installed")
        if subprocess.run([self.docker, "info"], capture_output=True).returncode != 0:
            raise SandboxUnavailable("the docker daemon is not reachable")
        self._image_id: str | None = None

    def _dockerfile(self) -> str:
        pins = " ".join(f"{n}=={v}" for n, v in package_versions().items())
        # Behind a TLS-intercepting proxy, SYMBOLON_PIP_CERT names a CA bundle
        # used only while building. It does not change the runtime environment.
        cert = "PIP_CERT=/tmp/build-ca.pem " if os.environ.get("SYMBOLON_PIP_CERT") else ""
        return (
            f"FROM {BASE_IMAGE}\n"
            "ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1\n"
            + ("COPY build-ca.pem /tmp/build-ca.pem\n" if cert else "")
            + f"RUN {cert}pip install {pins}\n"
            + ("RUN rm /tmp/build-ca.pem\n" if cert else "") +
            "COPY symbolon /opt/symbolon/symbolon\n"
            # A .pth file keeps symbolon importable under `python -I`.
            "RUN echo /opt/symbolon > \"$(python -c 'import site; print(site.getsitepackages()[0])')/symbolon.pth\"\n"
        )

    def _package_files(self) -> list[Path]:
        pkg = Path(symbolon.__file__).parent
        return sorted(p for p in pkg.rglob("*.py") if "__pycache__" not in p.parts)

    def image(self) -> str:
        h = hashlib.sha256(self._dockerfile().encode())
        pkg = Path(symbolon.__file__).parent
        for p in self._package_files():
            h.update(p.relative_to(pkg).as_posix().encode() + b"\0" + p.read_bytes())
        tag = f"symbolon-runner:{h.hexdigest()[:16]}"
        if subprocess.run([self.docker, "image", "inspect", tag], capture_output=True).returncode != 0:
            with tempfile.TemporaryDirectory() as ctx:
                Path(ctx, "Dockerfile").write_text(self._dockerfile())
                if os.environ.get("SYMBOLON_PIP_CERT"):
                    shutil.copy(os.environ["SYMBOLON_PIP_CERT"], Path(ctx, "build-ca.pem"))
                dest = Path(ctx, "symbolon")
                for p in self._package_files():
                    target = dest / p.relative_to(pkg)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, target)
                proc = subprocess.run([self.docker, "build", "-q", "-t", tag, ctx],
                                      capture_output=True, text=True, timeout=900)
                if proc.returncode != 0:
                    raise SandboxError("building the runner image failed:\n" + _tail(proc))
        if self._image_id is None:
            self._image_id = subprocess.run(
                [self.docker, "image", "inspect", "-f", "{{.Id}}", tag], capture_output=True, text=True
            ).stdout.strip()
        return tag

    def _container_info(self, image: str) -> dict:
        probe = ("import json, platform, importlib.metadata as m; print(json.dumps({"
                 "'python': platform.python_version(), 'implementation': platform.python_implementation(), "
                 "'os': platform.system().lower(), 'arch': platform.machine()}))")
        proc = subprocess.run([self.docker, "run", "--rm", "--network", "none", image, "python", "-c", probe],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise SandboxError(_tail(proc))
        return json.loads(proc.stdout)

    def environment(self) -> dict:
        image = self.image()
        return {
            "sandbox": self.kind,
            "base_image": BASE_IMAGE,
            "image_id": self._image_id,
            **self._container_info(image),
            "packages": package_versions(),
            "symbolon": symbolon.__version__,
        }

    def isolation(self, network: bool) -> dict:
        return {
            "network": "bridge (declared by contract)" if network else "none",
            "filesystem": "read-only root, read-only inputs, 64 MB tmpfs",
            "user": "65534 (nobody), all capabilities dropped, no-new-privileges",
        }

    def _docker_run(self, args: list[str], timeout: int) -> subprocess.CompletedProcess:
        name = f"symbolon-{uuid.uuid4().hex[:12]}"
        try:
            return subprocess.run([self.docker, "run", "--rm", "--name", name] + args,
                                  capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run([self.docker, "kill", name], capture_output=True)
            raise SandboxError(f"timed out after {timeout}s") from None

    def run(self, ws: Workspace, entrypoint: str, *, network: bool, lockfile: bool, limits: Limits) -> dict:
        image = self.image()
        for path in (ws.root, ws.contract, ws.impl):
            path.chmod(0o755)
        for path in ws.root.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
        ws.out.chmod(0o777)
        ws.deps.chmod(0o777)
        common = [
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65534:65534",
            "--read-only", "--tmpfs", "/tmp:rw,size=64m", "-e", "HOME=/tmp", "-w", "/tmp",
            "--pids-limit", "256", "--memory", f"{limits.memory_mb}m",
            "--memory-swap", f"{limits.memory_mb}m", "--cpus", "1",
        ]
        if lockfile:
            cert = os.environ.get("SYMBOLON_PIP_CERT")
            cert_args = ["-v", f"{Path(cert).resolve()}:/work/build-ca.pem:ro", "-e", "PIP_CERT=/work/build-ca.pem"] if cert else []
            proc = self._docker_run(common + cert_args + [
                "--network", "bridge",
                "-v", f"{ws.impl}:/work/impl:ro", "-v", f"{ws.deps}:/work/deps",
                image, "pip", "install", "--quiet", "--no-deps", "--target", "/work/deps",
                "-r", "/work/impl/requirements.lock",
            ], timeout=600)
            if proc.returncode != 0:
                raise SandboxError("installing requirements.lock failed:\n" + _tail(proc))

        cmd = common + [
            "--network", "bridge" if network else "none",
            "-v", f"{ws.contract}:/work/contract:ro",
            "-v", f"{ws.impl}:/work/impl:ro",
            "-v", f"{ws.out}:/work/out",
        ]
        worker = ["python", "-I", "-m", "symbolon.worker", "test",
                  "/work/contract", "/work/out/result.json", f"/work/impl/{entrypoint}"]
        if lockfile:
            cmd += ["-v", f"{ws.deps}:/work/deps:ro"]
            worker += ["--deps", "/work/deps"]
        proc = self._docker_run(cmd + [image] + worker, timeout=limits.timeout_seconds)
        out = ws.out / "result.json"
        if proc.returncode != 0 or not out.exists():
            reason = _tail(proc)
            if proc.returncode == 137:
                reason = f"killed (out of memory at {limits.memory_mb} MB or timed out)"
            raise SandboxError(reason)
        return json.loads(out.read_text())


def select(kind: str = "auto") -> Sandbox:
    if kind == "container":
        return ContainerSandbox()
    if kind == "process":
        return ProcessSandbox()
    if kind != "auto":
        raise ValueError(f"unknown sandbox {kind!r}; use auto, container or process")
    try:
        return ContainerSandbox()
    except SandboxUnavailable as container_reason:
        try:
            return ProcessSandbox()
        except SandboxUnavailable as process_reason:
            raise SandboxUnavailable(
                f"no sandbox available: container ({container_reason}); process ({process_reason})"
            ) from None
