#!/usr/bin/env bash
# INSTALLABLE SCRIPT: sudo install -o root -g root -m 0755 set-governor.sh /usr/local/sbin/set-governor.sh
set -euo pipefail

# Detect available governors from sysfs (preferred) or cpupower as a fallback.
detect_available_governors() {
  local govs=""
  # Try modern policy* path first
  if [[ -r /sys/devices/system/cpu/cpufreq/policy0/scaling_available_governors ]]; then
    govs="$(tr -s '[:space:]' ' ' < /sys/devices/system/cpu/cpufreq/policy0/scaling_available_governors | sed 's/^ //; s/ $//')"
  elif [[ -r /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors ]]; then
    govs="$(tr -s '[:space:]' ' ' < /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors | sed 's/^ //; s/ $//')"
  else
    # Fallback to cpupower output if available
    for CPP in /usr/bin/cpupower /usr/sbin/cpupower; do
      if [[ -x "$CPP" ]]; then
        # Example output line contains: "Available cpufreq governors: performance powersave ..."
        if govs="$("$CPP" frequency-info 2>/dev/null | awk -F: '/Available cpufreq governors/ {print $2}')"; then
          govs="$(tr -s '[:space:]' ' ' <<<"$govs" | sed 's/^ //; s/ $//')"
          break
        fi
      fi
    done
  fi

  if [[ -z "${govs:-}" ]]; then
    echo "Error: Could not detect available CPU governors (no sysfs entry and cpupower fallback failed)." >&2
    return 1
  fi

  printf '%s\n' "$govs"
}

# Return 0 if $1 is in the space-separated list $2
in_list() {
  local needle="$1"
  local haystack=" $2 "
  [[ "$haystack" == *" $needle "* ]]
}

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <governor>" >&2
  # Try to help by printing detected choices
  if govs="$(detect_available_governors 2>/dev/null)"; then
    echo "Available governors: $govs" >&2
  fi
  exit 2
fi

GOV="$1"
AVAILABLE="$(detect_available_governors)"
if ! in_list "$GOV" "$AVAILABLE"; then
  echo "Error: governor '$GOV' not available on this system." >&2
  echo "Available governors: $AVAILABLE" >&2
  exit 3
fi

# Prefer cpupower if available
if command -v /usr/bin/cpupower >/dev/null 2>&1 || command -v /usr/sbin/cpupower >/dev/null 2>&1; then
  for CPP in /usr/bin/cpupower /usr/sbin/cpupower; do
    if [[ -x "$CPP" ]]; then
      "$CPP" frequency-set -g "$GOV"
      exit 0
    fi
  done
fi

# Fallback: write to all policies/cpus via sysfs
shopt -s nullglob
targets=(/sys/devices/system/cpu/cpufreq/policy*/scaling_governor /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor)
if [[ ${#targets[@]} -eq 0 ]]; then
  echo "Error: no cpufreq sysfs entries found." >&2
  exit 4
fi
for f in "${targets[@]}"; do
  echo "$GOV" > "$f"
done
