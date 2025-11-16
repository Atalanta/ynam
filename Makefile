.PHONY: clean reset

DB_PATH := ~/.ynam/ynam.db

clean:
	rm -f $(DB_PATH)
	@echo "Database removed"

reset: clean
	uv run ynam initdb
	uv run ynam fetch --days 90
	@echo "Database reset complete"
