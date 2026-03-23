.PHONY: setup backend ui all

setup:
	./scripts/setup_local.sh

backend:
	./scripts/run_backend.sh

ui:
	./scripts/run_ui.sh

all:
	./scripts/run_all_local.sh
