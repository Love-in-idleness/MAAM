#!/usr/bin/env bash
set -euo pipefail

maam_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
maam_repo="${1:-Love-in-idleness/MAAM}"
maam_visibility="${2:-private}"

if ! command -v gh >/dev/null 2>&1; then
  echo 'Install GitHub CLI and run gh auth login first. / 请先安装并登录 GitHub CLI。' >&2
  exit 1
fi
case "$maam_visibility" in
  private|public) ;;
  *) echo 'Visibility must be private or public.' >&2; exit 1 ;;
esac
if [[ ! "$maam_repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo 'Expected repository in owner/name form.' >&2
  exit 1
fi
gh auth status
maam_login="$(gh api user --jq .login)"
maam_owner="${maam_repo%%/*}"
if [[ "${maam_login,,}" != "${maam_owner,,}" ]]; then
  echo 'This helper only creates repositories in the authenticated personal account.' >&2
  exit 1
fi
if [[ -n "$(git -C "$maam_root" status --porcelain)" ]]; then
  echo 'Commit local changes before publishing. / 请先提交本地修改。' >&2
  exit 1
fi
if git -C "$maam_root" remote get-url origin >/dev/null 2>&1; then
  echo 'An origin remote already exists; this helper will not replace it.' >&2
  exit 1
fi
if gh repo view "$maam_repo" --json nameWithOwner >/dev/null 2>&1; then
  echo 'The repository already exists; this helper will not overwrite it.' >&2
  exit 1
fi
gh repo create "$maam_repo" "--$maam_visibility" \
  --description 'Mathematical-interest metrics from compression and proof structure' \
  --source "$maam_root" --remote origin --push
