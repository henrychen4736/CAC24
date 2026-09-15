#!/usr/bin/env python3
"""One-command setup for Henry Tennis (CAC24) on Windows, macOS, and Linux.

What it does, in order:
  1. checks for Python 3.11/3.12 and Flutter >= 3.47.3 (plus optional tools)
  2. backend: creates backend/.venv, installs the tennis_ai package, downloads the pose model
  3. trained stroke model: installs it (--models-from) or trains it (--train)
  4. app: flutter pub get
  5. optional: runs the tests (--test), deploys Firestore rules (--deploy-rules),
     starts the server and launches the app on a phone or emulator (--run)

Usage:
  python bootstrap.py              set up the backend and the app
  python bootstrap.py --run        set up, then start the server and launch the app
  python bootstrap.py --check      only report which tools are installed
  python bootstrap.py --help       every option

Wrappers that find Python for you: `sh setup.sh` (macOS/Linux) and `setup.cmd` (Windows).
Safe to re-run: finished steps are skipped or refreshed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / ".venv"
MODELS = BACKEND / "models"

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
SUPPORTED_PYTHONS = ((3, 12), (3, 11))  # MediaPipe has no wheels for newer versions yet
MIN_FLUTTER = (3, 47, 3)
API_PORT = 8000
MODEL_FILES = ("stroke_model.onnx", "stroke_model.json", "reference_calibrated.json")
FIREBASE_PROJECT = "henry-tennis-q8mkn"

# ---------------------------------------------------------------------------- output

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
if IS_WIN:
    os.system("")  # enables ANSI colours in Windows 10+ consoles
_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _paint(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def step(msg: str) -> None:
    print("\n" + _paint("1;36", f"==> {msg}"), flush=True)


def ok(msg: str) -> None:
    print(_paint("32", "  ✓ ") + msg, flush=True)


def warn(msg: str) -> None:
    print(_paint("33", "  ! ") + msg, flush=True)


def info(msg: str) -> None:
    print("    " + msg, flush=True)


class SetupError(Exception):
    """A step failed in a way the user has to fix; the message says how."""


def run(cmd, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [str(c) for c in cmd]
    print(_paint("2", "  $ " + " ".join(cmd)), flush=True)
    result = subprocess.run(cmd, cwd=cwd)
    if check and result.returncode != 0:
        raise SetupError(f"this command failed (exit code {result.returncode}):\n    {' '.join(cmd)}")
    return result


def capture(cmd, cwd: Path | None = None, timeout: float = 300) -> str | None:
    """stdout of a command, or None if it can't run or fails."""
    try:
        out = subprocess.run(
            [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def _fmt(version) -> str:
    return ".".join(str(v) for v in version) if version else "unknown"


# ---------------------------------------------------------------------------- tools


def python_info(cmd: list[str]) -> tuple[tuple[int, int], str] | None:
    """((major, minor), executable) for a Python command, or None if it doesn't run."""
    out = capture(cmd + ["-c", "import sys; print(sys.version_info[0], sys.version_info[1], sys.executable)"],
                  timeout=60)
    if not out:
        return None
    try:
        major, minor, exe = out.strip().split(" ", 2)
        return (int(major), int(minor)), exe
    except ValueError:
        return None


def find_python(explicit: str | None) -> tuple[tuple[int, int], str] | None:
    candidates: list[list[str]] = []
    if explicit:
        candidates.append([explicit])
    candidates.append([sys.executable])
    if IS_WIN and shutil.which("py"):
        candidates += [["py", "-3.12"], ["py", "-3.11"]]
    for name in ("python3.12", "python3.11", "python3", "python"):
        path = shutil.which(name)
        if path:
            candidates.append([path])
    for cmd in candidates:
        found = python_info(cmd)
        if found and found[0] in SUPPORTED_PYTHONS:
            return found
    return None


def flutter_version(exe: str) -> tuple[tuple[int, int, int] | None, str]:
    """(version, error) for a flutter executable; error explains why the version is unknown."""
    try:  # the first run of a new SDK downloads Dart, so allow a long timeout
        out = subprocess.run([exe, "--version", "--machine"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    text = out.stdout or ""
    if "{" in text:
        try:
            data = json.loads(text[text.index("{"): text.rindex("}") + 1])
            m = re.match(r"(\d+)\.(\d+)\.(\d+)", str(data.get("frameworkVersion", "")))
            if m:
                return (int(m.group(1)), int(m.group(2)), int(m.group(3))), ""
        except ValueError:
            pass
    lines = [ln.strip() for ln in (out.stderr + "\n" + text).splitlines() if ln.strip()]
    return None, lines[-1] if lines else f"exit code {out.returncode}"


def _flutter_exe(candidate: str) -> str | None:
    path = Path(candidate).expanduser()
    if path.is_dir():  # an SDK root was given
        path = path / "bin" / ("flutter.bat" if IS_WIN else "flutter")
    if path.exists():
        return str(path)
    return shutil.which(candidate)


def find_flutter(explicit: str | None) -> tuple[str | None, tuple[int, int, int] | None, str]:
    """The first Flutter that is new enough; otherwise the first one found, to report on.

    Returns (executable, version, error) where error says why the version couldn't be read.
    """
    first: tuple[str | None, tuple[int, int, int] | None, str] = (None, None, "")
    for candidate in (explicit, os.environ.get("FLUTTER"), "flutter"):
        exe = _flutter_exe(candidate) if candidate else None
        if not exe:
            continue
        version, error = flutter_version(exe)
        if version and version >= MIN_FLUTTER:
            return exe, version, ""
        if first[0] is None:
            first = (exe, version, error)
    return first


def android_sdk() -> Path | None:
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(env) and Path(os.environ[env]).is_dir():
            return Path(os.environ[env])
    home = Path.home()
    for guess in (home / "AppData/Local/Android/Sdk", home / "Library/Android/sdk", home / "Android/Sdk"):
        if guess.is_dir():
            return guess
    return None


def check_tools(args) -> dict:
    step("Checking tools")
    problems: list[str] = []
    tools: dict = {"python": None, "flutter": None, "npx": shutil.which("npx")}

    if not args.skip_backend:
        py = find_python(args.python)
        if py:
            tools["python"] = py[1]
            ok(f"Python {_fmt(py[0])} for the backend: {py[1]}")
        else:
            problems.append(
                "Python 3.11 or 3.12 is required for the backend (MediaPipe has no wheels for newer "
                "versions yet). Install Python 3.12 from https://www.python.org/downloads/ and re-run, "
                "or point to one with --python <path>."
            )

    if not args.skip_frontend:
        exe, version, flutter_error = find_flutter(args.flutter)
        if exe and version and version >= MIN_FLUTTER:
            tools["flutter"] = exe
            ok(f"Flutter {_fmt(version)}: {exe}")
        elif exe and version:
            problems.append(
                f"Flutter {_fmt(MIN_FLUTTER)} or newer is required; found {_fmt(version)} at {exe}. "
                "Run `flutter upgrade`, or point to a newer SDK with --flutter <path>."
            )
        elif exe:
            problems.append(
                f"found Flutter at {exe}, but `flutter --version` failed: {flutter_error.rstrip('.')}. "
                "Fix that (Flutter needs git on your PATH), install Flutter "
                f"{_fmt(MIN_FLUTTER)}+ for this system, or point to one with --flutter <path>."
            )
        else:
            problems.append(
                "Flutter is required for the app. Install it from "
                "https://docs.flutter.dev/get-started/install, point to it with --flutter <path>, "
                "or set up only the server with --skip-frontend."
            )

    if shutil.which("git"):
        ok("git")
    else:
        warn("git not found (only needed to clone and update the project)")
    sdk = android_sdk()
    if sdk:
        ok(f"Android SDK: {sdk}")
    elif not args.skip_frontend:
        warn("Android SDK not found; install Android Studio to run the app on Android")
    if IS_MAC:
        if shutil.which("xcodebuild"):
            ok("Xcode")
        else:
            warn("Xcode not found; install it from the App Store to run the app on iOS")
    if tools["npx"]:
        ok("Node.js (npx), for --deploy-rules")
    elif args.deploy_rules:
        problems.append("--deploy-rules needs Node.js 18+ (for npx firebase-tools): https://nodejs.org")

    if args.check:
        for p in problems:
            warn(p)
        if not problems:
            ok("everything required is installed")
        return tools
    if problems:
        raise SetupError("missing requirements:\n  - " + "\n  - ".join(problems))
    return tools


# ---------------------------------------------------------------------------- backend


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")


def setup_backend(python: str, train: bool) -> Path:
    step("Backend: Python environment (backend/.venv)")
    vpy = venv_python()
    if vpy.exists():
        found = python_info([str(vpy)])
        if not found or found[0] not in SUPPORTED_PYTHONS:
            warn("backend/.venv is broken or uses an unsupported Python; recreating it")
            shutil.rmtree(VENV, ignore_errors=True)
        else:
            ok(f"reusing backend/.venv (Python {_fmt(found[0])})")
    if not vpy.exists():
        run([python, "-m", "venv", VENV])

    run([vpy, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    extras = "dev,train" if train else "dev"
    info("installing the tennis_ai package and its dependencies (a few minutes the first time)")
    # re-running this also repairs the environment after the project folder is moved or renamed
    run([vpy, "-m", "pip", "install", "--quiet", "-e", f".[{extras}]"], cwd=BACKEND)
    ok("backend installed")

    step("Backend: MediaPipe pose model")
    run([vpy, "-m", "tennis_ai.cli", "download-models"], cwd=BACKEND)
    ok("pose model ready")
    return vpy


def install_models_from(source: str) -> None:
    MODELS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(source).expanduser()
        if source.startswith(("http://", "https://")):
            src = Path(tmp) / "models.zip"
            info(f"downloading {source}")
            try:
                urllib.request.urlretrieve(source, src)
            except (urllib.error.URLError, OSError) as e:
                raise SetupError(f"couldn't download {source}: {e}") from e
        if src.is_file() and zipfile.is_zipfile(src):
            with zipfile.ZipFile(src) as archive:
                for member in archive.namelist():
                    name = Path(member).name
                    if name in MODEL_FILES:
                        (MODELS / name).write_bytes(archive.read(member))
        elif src.is_dir():
            for name in MODEL_FILES:
                if (src / name).exists():
                    shutil.copy2(src / name, MODELS / name)
        else:
            raise SetupError(f"--models-from must be a folder, a .zip file, or a URL to a .zip: {source}")
    missing = [n for n in MODEL_FILES[:2] if not (MODELS / n).exists()]
    if missing:
        raise SetupError(f"{source} doesn't contain {', '.join(missing)}")


def ensure_models(vpy: Path, args) -> None:
    step("Backend: trained stroke model and calibrated ranges")
    if args.models_from:
        install_models_from(args.models_from)
        ok(f"installed from {args.models_from}")
    elif args.train:
        cli = [vpy, "-m", "tennis_ai.cli"]
        info("training on THETIS: ~4 GB download, then 1-2 hours of CPU time.")
        info("Pose extraction is the slow part; if interrupted, re-running resumes where it stopped.")
        run(cli + ["fetch-thetis", "--out", "data/thetis"], cwd=BACKEND)
        run(cli + ["extract", "--thetis", "data/thetis", "--out", "data/poses"], cwd=BACKEND)
        run(cli + ["train", "--poses", "data/poses", "--out", "models"], cwd=BACKEND)
        run(cli + ["calibrate", "--poses", "data/poses", "--view", "front", "--shadow",
                   "--out", "models/reference_calibrated.json"], cwd=BACKEND)

    if all((MODELS / n).exists() for n in MODEL_FILES):
        ok("found stroke_model.onnx and reference_calibrated.json; the server will use them")
    else:
        warn("not found, so the server will use the rule-based stroke classifier and coaching-default ranges")
        info("Everything works without them. For the trained model, re-run with")
        info("--models-from <folder | .zip | URL> or --train (see README section 9).")


# ---------------------------------------------------------------------------- app


def setup_frontend(flutter: str) -> None:
    step("App: Flutter packages")
    run([flutter, "pub", "get"], cwd=FRONTEND)
    ok("app dependencies installed")


def run_tests(vpy: Path | None, flutter: str | None) -> None:
    if vpy:
        step("Backend: lint and tests")
        run([vpy, "-m", "ruff", "check", "src", "tests", "scripts"], cwd=BACKEND)
        run([vpy, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=BACKEND)
        ok("backend tests passed")
    if flutter:
        step("App: analyze and tests")
        run([flutter, "analyze"], cwd=FRONTEND)
        run([flutter, "test"], cwd=FRONTEND)
        ok("app tests passed")


def deploy_rules(npx: str) -> None:
    step("Firebase: deploying Firestore security rules")
    info(f"project {FIREBASE_PROJECT}; needs a Firebase login with access to it "
         "(run `npx firebase-tools login` first)")
    run([npx, "-y", "firebase-tools@latest", "deploy", "--only", "firestore:rules"], cwd=FRONTEND)
    ok("rules deployed")


# ---------------------------------------------------------------------------- run


def health() -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{API_PORT}/v1/health", timeout=3) as resp:
            return json.load(resp)
    except (OSError, ValueError):
        return None


def start_server(vpy: Path) -> subprocess.Popen | None:
    step("Starting the analysis server")
    if health():
        ok(f"a server is already running on port {API_PORT}; using it")
        return None
    log_path = BACKEND / "server.log"
    log = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 - stays open for the server's lifetime
    proc = subprocess.Popen(
        [str(vpy), "-m", "tennis_ai.cli", "serve", "--host", "0.0.0.0", "--port", str(API_PORT)],
        cwd=BACKEND, stdout=log, stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 180
    while time.time() < deadline:
        status = health()
        if status:
            ok(f"http://localhost:{API_PORT}  (classifier: {status.get('classifier')}, "
               f"ranges: {status.get('reference')}, log: backend/server.log)")
            return proc
        if proc.poll() is not None:
            break
        time.sleep(1)
    proc.terminate()
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
    raise SetupError(f"the analysis server didn't start. End of backend/server.log:\n{tail}")


def _json_list(text: str | None) -> list:
    if not text or "[" not in text:
        return []
    try:
        return json.loads(text[text.index("["): text.rindex("]") + 1])
    except ValueError:
        return []


def mobile_devices(flutter: str) -> list[dict]:
    devices = _json_list(capture([flutter, "devices", "--machine"], timeout=180))
    return [d for d in devices
            if d.get("isSupported", True) and str(d.get("targetPlatform", "")).startswith(("android", "ios"))]


def pick_device(flutter: str, wanted: str | None) -> dict:
    step("Finding a phone or emulator")
    devices = mobile_devices(flutter)
    if wanted:
        for d in devices:
            if wanted in (d.get("id"), d.get("name")):
                return d
        raise SetupError(f"no connected device matches --device {wanted}. "
                         f"Connected: {', '.join(d.get('id', '?') for d in devices) or 'none'}")
    if devices:
        ok(f"using {devices[0].get('name')} ({devices[0].get('id')})")
        return devices[0]

    emulators = []
    for line in (capture([flutter, "emulators"], timeout=180) or "").splitlines():
        parts = [p.strip() for p in line.split("•")]
        if len(parts) >= 4 and parts[0] and parts[0].lower() != "id":
            emulators.append((parts[0], parts[1], parts[3].lower()))
    preferred = [e for e in emulators if e[2] == "android"] + [e for e in emulators if e[2] == "ios"]
    if not preferred:
        raise SetupError("no phone is connected and no emulator is set up. Plug in a phone with "
                         "USB debugging on, or create an emulator in Android Studio > Device Manager, "
                         "then re-run.")
    emu_id, emu_name, _ = preferred[0]
    # cold boot: a stale quick-boot snapshot can crash the Android emulator on start
    info(f"no device connected; starting the {emu_name} emulator (cold boot, 1-3 minutes)")
    run([flutter, "emulators", "--launch", emu_id, "--cold"], check=False)
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(5)
        devices = mobile_devices(flutter)
        if devices:
            ok(f"using {devices[0].get('name')} ({devices[0].get('id')})")
            return devices[0]
    raise SetupError("the emulator didn't come online within 5 minutes. Start it from Android Studio > "
                     "Device Manager (choose Cold Boot Now) and re-run with --run.")


def lan_ip() -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))  # picks the outbound interface; sends nothing
        ip = sock.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None
    finally:
        sock.close()


def run_app(vpy: Path, flutter: str, args) -> int:
    server = start_server(vpy)
    try:
        device = pick_device(flutter, args.device)
        cmd = [flutter, "run", "-d", device["id"]]
        api_url = args.api_url
        if not api_url and not device.get("emulator"):
            ip = lan_ip()
            api_url = f"http://{ip}:{API_PORT}" if ip else None
        if api_url:
            cmd.append(f"--dart-define=API_BASE_URL={api_url}")
        step(f"Launching the app on {device.get('name')}")
        if api_url and not args.api_url:
            info(f"physical device: the app will reach the server at {api_url}.")
            info("Keep the phone on the same Wi-Fi and allow Python through your firewall.")
        info("The first build takes a few minutes. Press r to hot reload, q to quit.")
        return run(cmd, cwd=FRONTEND, check=False).returncode
    finally:
        if server is not None:
            step("Stopping the analysis server")
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()


def print_next_steps(args) -> None:
    step("Setup complete")
    if not args.skip_backend:
        activate = r".venv\Scripts\activate" if IS_WIN else "source .venv/bin/activate"
        info("Start the analysis server:")
        info("  cd backend")
        info(f"  {activate}")
        info("  tennis-ai serve                   # http://localhost:8000")
    if not args.skip_frontend:
        info("Launch the app (in another terminal, with a phone or emulator connected):")
        info("  cd frontend")
        info("  flutter run")
    if not (args.skip_backend or args.skip_frontend):
        info("")
        info("Or do both in one go:  python bootstrap.py --run")
    info("")
    info(f"Sign-in uses Firebase project {FIREBASE_PROJECT}. If creating an account fails, the project")
    info("owner needs to enable Email/Password sign-in in the Firebase console.")


# ---------------------------------------------------------------------------- main


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bootstrap.py",
        description="One-command setup for Henry Tennis: backend, trained model, and app.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  python bootstrap.py                              set everything up
  python bootstrap.py --run                        set up, start the server, launch the app
  python bootstrap.py --test                       set up and run both test suites
  python bootstrap.py --models-from models.zip     install a trained model someone shared
  python bootstrap.py --train                      train the model yourself (~4 GB, 1-2 h)
  python bootstrap.py --skip-frontend              server only (no Flutter needed)
  python bootstrap.py --run --device emulator-5554 launch on a specific device""",
    )
    p.add_argument("--check", action="store_true", help="only report which tools are installed")
    p.add_argument("--run", action="store_true",
                   help="after setup, start the server and launch the app (boots an emulator if needed)")
    p.add_argument("--test", action="store_true", help="after setup, run the backend and app test suites")
    p.add_argument("--train", action="store_true",
                   help="train the stroke model and calibrate ranges on THETIS (~4 GB download, 1-2 h)")
    p.add_argument("--models-from", metavar="PATH_OR_URL",
                   help="install trained model files from a folder, a .zip, or a URL to a .zip")
    p.add_argument("--deploy-rules", action="store_true",
                   help="deploy frontend/firestore.rules to Firebase (needs Node.js and a Firebase login)")
    p.add_argument("--device", help="with --run: the flutter device id or name to launch on")
    p.add_argument("--api-url",
                   help="with --run: server URL the app should use (default: chosen automatically)")
    p.add_argument("--python", help="Python 3.11/3.12 executable to build backend/.venv with")
    p.add_argument("--flutter", help="flutter executable or SDK folder to use")
    p.add_argument("--skip-backend", action="store_true", help="don't set up the backend")
    p.add_argument("--skip-frontend", action="store_true", help="don't set up the app")
    args = p.parse_args(argv)
    if args.run and (args.skip_backend or args.skip_frontend):
        p.error("--run needs both the backend and the app; drop --skip-backend/--skip-frontend")
    if args.train and args.models_from:
        p.error("use either --train or --models-from, not both")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(_paint("1", "Henry Tennis setup") + f"  {ROOT}")
    try:
        tools = check_tools(args)
        if args.check:
            ready = (args.skip_backend or tools["python"]) and (args.skip_frontend or tools["flutter"])
            return 0 if ready else 1
        vpy = None
        if not args.skip_backend:
            vpy = setup_backend(tools["python"], train=args.train)
            ensure_models(vpy, args)
        if not args.skip_frontend:
            setup_frontend(tools["flutter"])
        if args.test:
            run_tests(vpy, tools["flutter"])
        if args.deploy_rules:
            deploy_rules(tools["npx"])
        if args.run:
            return run_app(vpy, tools["flutter"], args)
        print_next_steps(args)
        return 0
    except SetupError as e:
        print("\n" + _paint("1;31", "Setup stopped: ") + str(e), flush=True)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", flush=True)
        return 130


if __name__ == "__main__":
    sys.exit(main())
