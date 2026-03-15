#!/bin/bash
set -euo pipefail

VPS_HOST="${VPS_HOST:-<VPS_IP>}"
VPS_USER="${VPS_USER:-<SSH_USER>}"
REMOTE_PROJECT_ROOT="${REMOTE_PROJECT_ROOT:-~/project-root}"

ssh "${VPS_USER}@${VPS_HOST}" "cd ${REMOTE_PROJECT_ROOT} && pwd"
