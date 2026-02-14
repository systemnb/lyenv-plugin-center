#!/usr/bin/env bash
set -euo pipefail
# Fallback lyenv_sdk.sh (minimal). Prefer public/sdks/lyenv_sdk.sh.

LYENV_REQ_JSON=""
ly_read_request(){ LYENV_REQ_JSON="$(cat)"; [[ -n "${LYENV_REQ_JSON//[[:space:]]/}" ]] || { echo "lyenv_sdk: empty stdin" >&2; return 1; }; }
ly_log(){ :; }
ly_emit_artifact(){ :; }
ly_mutate_set(){ :; }
ly_respond_ok(){ printf '{"status":"ok","logs":[],"artifacts":[],"mutations":{"global":{},"plugin":{}}}\n'; }
ly_respond_error(){ printf '{"status":"error","message":"%s","logs":[],"artifacts":[],"mutations":{"global":{},"plugin":{}}}\n' "${1:-error}"; exit 1; }
