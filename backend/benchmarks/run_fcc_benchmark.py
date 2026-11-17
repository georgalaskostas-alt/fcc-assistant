"""Local-only exploratory FCC text benchmark; screening is NOT engineering validation.

From repository root:
  .venv/bin/python backend/benchmarks/run_fcc_benchmark.py --output /tmp/fcc-benchmark.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse


DEFAULT_DATASET = Path(__file__).with_name("fcc_engineering_v1.json")
SYSTEM = (
    "You are an FCC process engineering assistant. /no_think "
    "Answer accurately in 2-4 sentences. Distinguish facts from hypotheses. "
    "If evidence is missing, explicitly say you cannot determine the answer. "
    "Never invent tag readings, alarm limits, causes or setpoint changes. "
    "Do not issue plant operating instructions."
)


def load_cases(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("Dataset must contain nonempty cases")
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Benchmark case IDs must be unique")
    for case in cases:
        for field in ("id", "area", "question", "review_note"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f"Invalid {field} in case {case.get('id')}")
        for field in ("must_include", "must_not_claim"):
            if not isinstance(case.get(field), list) or not all(
                isinstance(x, str) and x for x in case[field]
            ):
                raise ValueError(f"Invalid {field} in case {case['id']}")
    return cases


def validate_local_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Only local HTTP inference endpoints are permitted")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("Endpoint must be a local origin without credentials, path or query")
    return endpoint.rstrip("/")


def screen_answer(case: dict, answer: str, finish_reason: str) -> dict:
    lower = answer.casefold()
    missing = [term for term in case["must_include"] if term.casefold() not in lower]
    forbidden = [term for term in case["must_not_claim"] if term.casefold() in lower]
    complete = finish_reason == "stop" and bool(answer.strip())
    return {
        "complete": complete,
        "missing_keyword_fragments": missing,
        "matched_forbidden_phrases": forbidden,
        "screen_pass": complete and not missing and not forbidden,
        "engineer_review": "pending",
    }


def query(endpoint: str, model: str, question: str, max_tokens: int, timeout: float) -> dict:
    body = {
        "model": model, "stream": False, "temperature": 0, "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "/no_think\n" + question},
        ],
    }
    req = urllib.request.Request(
        endpoint + "/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def run(dataset: Path, endpoint: str, model: str, max_tokens: int, timeout: float) -> dict:
    cases = load_cases(dataset)
    results = []
    for case in cases:
        started = time.monotonic()
        result = {"id": case["id"], "area": case["area"], "question": case["question"],
                  "reference_for_human_review": case["review_note"]}
        try:
            response = query(endpoint, model, case["question"], max_tokens, timeout)
            choice = response["choices"][0]
            answer = choice["message"].get("content") or ""
            finish = str(choice.get("finish_reason") or "")
            result.update({
                "answer": answer,
                "finish_reason": finish,
                "usage": response.get("usage", {}),
                "screening": screen_answer(case, answer, finish),
            })
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError) as exc:
            result.update({"error": f"{type(exc).__name__}: {exc}",
                           "screening": {"screen_pass": False, "engineer_review": "pending"}})
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        results.append(result)
        status = "SCREEN PASS" if result["screening"]["screen_pass"] else "REVIEW"
        print(f"{case['id']}: {status} ({result['elapsed_seconds']}s)", flush=True)
    return {
        "dataset": dataset.name, "model": model, "endpoint": endpoint,
        "evaluation": "exploratory_keyword_screen_only_not_engineering_validation",
        "case_count": len(results),
        "screen_pass_count": sum(bool(x["screening"]["screen_pass"]) for x in results),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18081")
    parser.add_argument("--model", default="Qwen3-4B-Q4_K_M")
    parser.add_argument("--max-tokens", type=int, default=400)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output", type=Path, default=Path("/tmp/fcc-engineering-benchmark.json"))
    args = parser.parse_args()
    endpoint = validate_local_endpoint(args.endpoint)
    if not 1 <= args.max_tokens <= 4096 or not 1 <= args.timeout <= 600:
        parser.error("Invalid max-tokens or timeout")
    report = run(args.dataset, endpoint, args.model, args.max_tokens, args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exploratory screening: {report['screen_pass_count']}/{report['case_count']}")
    print(f"Engineer review REQUIRED. Report: {args.output}")


if __name__ == "__main__":
    main()
