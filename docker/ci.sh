#!/usr/bin/env bash

set -o errexit
set -o nounset

: "${CODECOV_TOKEN:=}"

ACTION="default"
for i in "$@"
do
case $i in
    --action=*)
        ACTION="${i#*=}"
    ;;
    *)
        echo "You've passed an unknown argument $i"
        exit 1
    ;;
esac
done


pyclean() {
  # Cleaning cache:
  find . | grep -E '(__pycache__|\.py[cod]$)' | xargs rm -rf
}

check_isort(){
  poetry run isort --diff --check-only --settings-path pyproject.toml app tests
}

check_black(){
  poetry run black --diff --check app tests
}

check_test_fixtures(){
  poetry run pytest --dead-fixtures --dup-fixtures -vvvv
}

lint_flake(){
  poetry run flake8 app tests
}

lint_mypy(){
  poetry run mypy app
}


lint_xenon(){
  poetry run xenon --max-absolute B --max-modules A --max-average A app
}

lint_bandit(){
  poetry run bandit -r app --exclude='*/tests/test_*.py'
}


linters() {
  lint_flake
  lint_mypy
  lint_xenon
  lint_bandit
}

formatters() {
  check_isort
  check_black
}

tests() {
  poetry run pytest -vv --durations=10
  if [ -n "$CODECOV_TOKEN" ]; then
    # Report coverage. Must be executed after pytest
    echo "Run codecov"
    poetry run codecovcli do-upload --report-type test_results --file junit.xml
    poetry run codecov
  else
    echo "Don't run codecov"
  fi
}

default() {
  check_isort
  check_black
  lint_flake
  lint_mypy
  lint_xenon
  lint_bandit
  tests
  check_test_fixtures
}
# Remove any cache before the script:
pyclean

# Clean everything up:
trap pyclean EXIT INT TERM

if [ "$ACTION" == "linters" ]; then
  linters
elif [ "$ACTION" == "formatters" ]; then
  formatters
elif [ "$ACTION" == "tests" ]; then
  tests
else
  default
fi
