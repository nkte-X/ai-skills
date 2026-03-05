#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "${SCRIPT_DIR}")"

mkdir -p "${PARENT_DIR}/scripts"
cp "${SCRIPT_DIR}/script/git_tracker.py" "${PARENT_DIR}/scripts/"

cp -r "${SCRIPT_DIR}/git_tracker" "${PARENT_DIR}/"

if [ -z "${OPENCLAW_WORKSPACE_DIR}" ]; then
    echo "Error: OPENCLAW_WORKSPACE_DIR is not set"
    exit 1
fi

mkdir -p "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker"
cp -r "${SCRIPT_DIR}/git-tracker/"* "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/"

echo "Setup complete:"
echo "  - ${PARENT_DIR}/scripts/git_tracker.py"
echo "  - ${PARENT_DIR}/git_tracker/"
echo "  - ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/"
