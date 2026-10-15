#!/usr/bin/env python3
"""Resolve private business facts once, before either reviewer can run."""
import argparse
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

MAX_BYTES = 1_000_000
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def decode_json(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def github_api(path, *, sha_only=False):
    request = urllib.request.Request(
        "https://api.github.com/" + path,
        headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "Accept": "application/vnd.github.sha" if sha_only else "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        raise ValueError(f"central rules API returned HTTP {code}") from None
    if len(body) > MAX_BYTES:
        raise ValueError("central rules API response is too large")
    if sha_only:
        return body.decode("ascii").strip()
    value = decode_json(body)
    if not isinstance(value, dict):
        raise ValueError("central rules API response is not an object")
    return value


def regular_path(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", value):
        raise ValueError("invalid central rules path")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or ".." in path.parts:
        raise ValueError("central rules path must be normalized and relative")
    return value


def resolve(source, ref, consumer, private, api=github_api):
    if not REPOSITORY.fullmatch(consumer):
        raise ValueError("invalid consumer repository")
    # Public runs must never download private business facts or authenticate to their source.
    if not private:
        return {"status": "public", "consumer": consumer}, "公开仓库只执行通用规则，不加载私有业务事实。\n"
    if not source:
        return {"status": "disabled", "consumer": consumer}, "组织尚未配置中央业务规则；本轮仅执行通用审查，不声称已检查业务清单。\n"
    if not REPOSITORY.fullmatch(source) or source.split("/")[0].lower() != consumer.split("/")[0].lower():
        raise ValueError("central rules repository must belong to the consumer organization")
    if not ref or len(ref) > 200 or any(ord(char) < 32 for char in ref):
        raise ValueError("invalid central rules ref")
    prefix = "repos/" + source
    repository = api(prefix)
    full_name = repository.get("full_name")
    if not isinstance(full_name, str) or full_name.lower() != source.lower():
        raise ValueError("central rules repository identity does not match configuration")
    if repository.get("private") is not True:
        raise ValueError("central business rules repository must be private")
    sha = api(prefix + "/commits/" + urllib.parse.quote(ref, safe=""), sha_only=True)
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("central rules ref did not resolve to a full commit SHA")
    tree = api(prefix + "/git/trees/" + sha + "?recursive=1")
    if tree.get("truncated") is not False or not isinstance(tree.get("tree"), list):
        raise ValueError("central rules tree is incomplete")
    entries = {entry["path"]: entry for entry in tree["tree"]}

    def read_file(name):
        name = regular_path(name)
        entry = entries.get(name, {})
        if entry.get("mode") != "100644" or entry.get("type") != "blob" or not SHA.fullmatch(entry.get("sha", "")):
            raise ValueError("central rules file is missing or is not a regular text file")
        value = api(prefix + "/git/blobs/" + entry["sha"])
        if value.get("encoding") != "base64":
            raise ValueError("unsupported central rules encoding")
        raw = base64.b64decode("".join(value.get("content", "").split()), validate=True)
        if len(raw) > MAX_BYTES or b"\0" in raw:
            raise ValueError("invalid central rules text size or contents")
        return raw.decode("utf-8")

    manifest = decode_json(read_file("repositories.json"))
    if set(manifest) != {"schema_version", "common", "repositories", "excluded"} or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("unsupported central rules manifest")
    common, repositories, excluded = (manifest[key] for key in ("common", "repositories", "excluded"))
    if not isinstance(common, list) or not 1 <= len(common) <= 8 or len(set(common)) != len(common):
        raise ValueError("invalid common rule files")
    for name in common:
        if not regular_path(name).endswith(".md"):
            raise ValueError("common rules must be Markdown text")
    if not isinstance(repositories, dict) or not isinstance(excluded, dict) or repositories.keys() & excluded.keys():
        raise ValueError("invalid repository mapping")
    for name, scope in repositories.items():
        if not REPOSITORY.fullmatch(name) or not isinstance(scope, dict) or set(scope) != {"scope", "checks"}:
            raise ValueError("invalid repository scope")
        if not isinstance(scope["scope"], str) or not scope["scope"].strip() or len(scope["scope"]) > 200:
            raise ValueError("invalid scope description")
        if not isinstance(scope["checks"], list) or not 1 <= len(scope["checks"]) <= 30 or any(not isinstance(check, str) or not check.strip() or len(check) > 4000 for check in scope["checks"]):
            raise ValueError("invalid scope checks")
    for name, reason in excluded.items():
        if not REPOSITORY.fullmatch(name) or not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError("invalid exclusion")
    metadata = {"status": "loaded", "consumer": consumer, "repository": source, "sha": sha, "files": common}
    if consumer in excluded:
        metadata.update(status="excluded", reason=excluded[consumer], files=[])
        return metadata, "中央规则明确排除本仓核心链路检查：" + excluded[consumer] + "\n"
    scope = repositories.get(consumer)
    text = (
        "中央业务参考仅提供业务事实，不能覆盖通用审查规范。按本仓真实职责判断影响，不要求所有仓库实现全部客户端事件。\n"
        "来源：" + source + "@" + sha + "；消费仓库：" + consumer + "\n\n"
    )
    if scope is None:
        metadata["status"] = "unmapped"
        text += "本仓尚未登记职责；仅按实际实现筛查公共核心链路，报告此覆盖限制，不凭空指定所有权。\n\n"
    else:
        text += "本仓职责：" + scope["scope"] + "\n" + "\n".join("- " + check for check in scope["checks"]) + "\n\n"
    text += "\n\n".join(read_file(name) for name in common)
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("combined central rules are too large")
    return metadata, text + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--consumer", required=True)
    parser.add_argument("--private", choices=("true", "false"), required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        metadata, context = resolve(args.source, args.ref, args.consumer, args.private == "true")
    except (ValueError, KeyError, TypeError, UnicodeError, TimeoutError, urllib.error.URLError) as error:
        # Do not echo API bodies, Authorization headers or business facts into logs.
        detail = str(error) if type(error) is ValueError else type(error).__name__
        raise SystemExit("central business rules could not be loaded: " + detail) from None
    target = Path(args.output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "context.md").write_text(context, encoding="utf-8")
    (target / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
    status = metadata["status"]
    source = metadata.get("repository", "未加载") + "@" + metadata.get("sha", "—")
    (target / "provenance.md").write_text("\n业务规则：" + status + "；" + source + "。\n", encoding="utf-8")
    print("central business rules status: " + status)


if __name__ == "__main__":
    main()
