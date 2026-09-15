from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from public_sources import digest, write_json

ROOT = Path(__file__).resolve().parents[1]


def container(image: str, source: Path, deps: Path, command: list[str], network: bool) -> dict:
    name = "r2s-build-" + uuid.uuid4().hex[:12]
    args = ["docker", "run", "--rm", "--name", name, "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--user=65534:65534", "--cpus=1",
            "--memory=1024m", "--pids-limit=128", "--tmpfs=/tmp:rw,exec,nosuid,size=536870912",
            "--mount", f"type=bind,src={source},dst=/source,readonly",
            "--mount", f"type=bind,src={deps},dst=/deps", "--env=HOME=/tmp",
            "--env=GOPATH=/deps", "--env=GOMODCACHE=/deps/mod", "--env=GOCACHE=/tmp/go-cache",
            "--env=CGO_ENABLED=0", "--env=GOTOOLCHAIN=local", "--env=GOPROXY=https://goproxy.cn,direct",
            "--workdir=/source"]
    if not network:
        args.append("--network=none")
    args += [image, *command]
    try:
        completed = subprocess.run(args, capture_output=True, text=True, check=False, timeout=240)
        return {"argv": command, "exit_code": completed.returncode,
                "stdout": completed.stdout[-3000:], "stderr": completed.stderr[-3000:]}
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, check=False)
        return {"argv": command, "exit_code": None, "stderr": "240 second wall timeout"}


def attempt(record: dict, work: Path, node: str, go: str) -> dict:
    source = work / "snapshots" / f"{record['id']}-{record['commit_sha']}" / "source"
    deps = work / "builds" / record["id"]
    deps.mkdir(parents=True, exist_ok=True)
    deps.chmod(0o777)
    node_repository = record["id"] in {"prettier", "eslint", "webpack"}
    image = node if node_repository else go
    if node_repository:
        write_json(deps / "package.json", json.loads((source / "package.json").read_text()))
        command = ["npm", "install", "--prefix=/deps", "--ignore-scripts", "--omit=dev",
                   "--workspaces=false", "--registry=https://registry.npmmirror.com", "--cache=/tmp/npm"]
    else:
        command = ["go", "mod", "download"]
    prepare = container(image, source, deps, command, True)
    result = {"id": record["id"], "commit_sha": record["commit_sha"], "image_id": image,
              "dependency_preparation": prepare, "status": "DEPENDENCY_FAILED"}
    if prepare["exit_code"] != 0:
        return result
    if node_repository:
        entry = {"prettier": "bin/prettier.cjs", "eslint": "bin/eslint.js", "webpack": "bin/webpack.js"}[record["id"]]
        command = ["sh", "-c", f"cp -R /source /tmp/source && ln -s /deps/node_modules /tmp/source/node_modules && node /tmp/source/{entry} --help"]
    else:
        entry = "./cmd/gh" if record["id"] == "github-cli" else "."
        command = ["go", "build", "-o", "/deps/program", entry]
    build = container(image, source, deps, command, False)
    result["offline_build_or_smoke"] = build
    result["status"] = "SMOKE_PASSED" if build["exit_code"] == 0 else "BUILD_FAILED"
    if not node_repository and build["exit_code"] == 0:
        invocation = container(image, source, deps, ["/deps/program", "--help"], False)
        result["offline_smoke"] = invocation
        result["status"] = "SMOKE_PASSED" if invocation["exit_code"] == 0 else "SMOKE_FAILED"
        result["binary_sha256"] = digest(deps / "program")
    lockfile = deps / "package-lock.json"
    if lockfile.exists():
        result["dependency_lock_sha256"] = digest(lockfile)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--go-image", required=True)
    parser.add_argument("--node-image", default="node:22-alpine")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print("Preview: dependency download with lifecycle scripts disabled, then offline build/help. Pass --execute.")
        return
    images = [json.loads(subprocess.check_output(["docker", "image", "inspect", ref]))[0]["Id"]
              for ref in (args.node_image, args.go_image)]
    records = [item for item in json.loads((ROOT / "benchmark/repository-metadata.json").read_text())["repositories"]
               if item["id"] in {"github-cli", "hugo", "fzf", "prettier", "eslint", "webpack"}]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda item: attempt(item, args.work, *images), records))
    write_json(ROOT / "benchmark/build-runtime-results.json", {
        "method": "Isolated dependency preparation with network; target build and smoke with network disabled. npm lifecycle disabled throughout.",
        "repositories": results})
    for result in results:
        print(result["id"], result["status"])


if __name__ == "__main__":
    main()
