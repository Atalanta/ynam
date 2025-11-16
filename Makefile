.PHONY: clean reset

DB_PATH := ~/.ynam/ynam.db
CONFIG_PATH := ~/.ynam/config.toml

clean:
	rm -f $(DB_PATH) $(CONFIG_PATH)
	@echo "Database and config removed"

reset: clean
	uv run ynam init
	@echo "Initialized. Configure sources in $(CONFIG_PATH), then run 'ynam sync <source>'"
