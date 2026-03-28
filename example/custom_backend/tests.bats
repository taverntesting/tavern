#!/usr/bin/env bats

setup() {
  if [ ! -d ".venv" ]; then
    uv venv
  fi
  . .venv/bin/activate
  uv pip install -e . 'tavern @ ../..'
}

@test "run tavern-ci with --tavern-extra-backends=file" {
  PYTHONPATH=. run tavern-ci \
    --tavern-extra-backends=file \
    --debug \
    tests

  [ "$status" -eq 0 ]
}

@test "run tavern-ci with --tavern-extra-backends=file=my_tavern_plugin" {
  PYTHONPATH=. run tavern-ci \
    --tavern-extra-backends=file=my_tavern_plugin \
    --debug \
    tests

  [ "$status" -eq 0 ]
}

@test "run tavern-ci with --tavern-extra-backends=file=i_dont_exist should fail" {
  PYTHONPATH=. run tavern-ci \
    --tavern-extra-backends=file=i_dont_exist \
    --debug \
    tests

  [ "$status" -ne 0 ]
}