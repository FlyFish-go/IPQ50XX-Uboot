#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Run every host test registered in test/hosttests.list.
#
#   test/run_hosttests.sh [result-file]
#
# Manifest lines (blank lines and # comments ignored):
#   run  <test> [args]   run it; @SRC@ = the u-boot-2016 directory, @OUT@ = scratch dir
#   skip <test> <reason> not run here (needs private evidence the public tree lacks)
# A *_hosttest.py / *_hosttest.sh file that is not listed fails the run, so a new
# test cannot be forgotten. Exit status 1 when anything fails.
set -u
src=$(cd "$(dirname "$0")/.." && pwd)
list=$src/test/hosttests.list
result=${1:-/dev/stdout}
out=$(mktemp -d); trap 'rm -rf "$out"' EXIT
cd "$src" || exit 2
: > "$out/result"
pass=0 fail=0 skipped=0
declare -A listed
while read -r verb test args; do
  [[ -z $verb || $verb == \#* ]] && continue
  listed[$test]=1
  case $verb in
  skip) echo "SKIP $test :: $args" >> "$out/result"; skipped=$((skipped+1)); continue ;;
  run) ;;
  *) echo "FAIL $test :: bad manifest verb '$verb'" >> "$out/result"; fail=$((fail+1)); continue ;;
  esac
  args=${args//@SRC@/$src}; args=${args//@OUT@/$out/o}
  case $test in *.py) cmd=(python3 "$test") ;; *) cmd=(bash "$test") ;; esac
  # shellcheck disable=SC2206
  cmd+=($args)
  if timeout 300 "${cmd[@]}" > "$out/log" 2>&1; then
    echo "PASS $test" >> "$out/result"; pass=$((pass+1))
  else
    echo "FAIL $test :: $(tail -n 1 "$out/log" | cut -c1-160)" >> "$out/result"; fail=$((fail+1))
  fi
done < "$list"
for t in test/*_hosttest.py test/*_hosttest.sh; do
  [[ -n ${listed[$t]:-} ]] && continue
  echo "FAIL $t :: not registered in test/hosttests.list" >> "$out/result"; fail=$((fail+1))
done
echo "pass=$pass fail=$fail skip=$skipped" >> "$out/result"
cat "$out/result" > "$result"
[[ $fail == 0 ]]
