.DEFAULT_GOAL := run

PORT ?= 8000
# Ergebnisverzeichnis mit aggregated/YYYY-MM-DD.json (ein AggregatedResult pro Stichtag),
# relativ zu viewer/ oder absolut
RESULTS_DIR ?= data/results
# Tagesdatei, aus der `make sample-data` Beispiel-Aggregatdateien baut
DAILY_FILE ?= ../analyser/tmp/results/daily_result.json
# Anzahl der künstlichen Stichtage für die Beispieldaten
SAMPLE_DAYS ?= 60

PHP_IMAGE ?= php:8.4-cli
COMPOSER_IMAGE ?= composer:2
DOCKER_RUN := docker run --rm -v "$(CURDIR)":/app -w /app

# Lokales PHP/Composer verwenden, sonst auf Docker ausweichen
ifneq ($(shell command -v php 2>/dev/null),)
PHP := php
SERVE := VIEWER_RESULTS_DIR="$(RESULTS_DIR)" php -S localhost:$(PORT) -t public
else
PHP := $(DOCKER_RUN) $(PHP_IMAGE) php
SERVE := $(DOCKER_RUN) -it -p $(PORT):$(PORT) -e VIEWER_RESULTS_DIR="$(RESULTS_DIR)" $(PHP_IMAGE) php -S 0.0.0.0:$(PORT) -t public
endif

ifneq ($(shell command -v composer 2>/dev/null),)
COMPOSER := composer
else
COMPOSER := $(DOCKER_RUN) $(COMPOSER_IMAGE)
endif

vendor/autoload.php: composer.json
	$(COMPOSER) install --no-interaction
	touch $@

install: vendor/autoload.php

run: vendor/autoload.php
	@echo "Scanner-Quartett: http://localhost:$(PORT)  (Daten: $(RESULTS_DIR))"
	$(SERVE)

sample-data:
	python3 scripts/sample_data.py "$(DAILY_FILE)" "$(RESULTS_DIR)" --days $(SAMPLE_DAYS)

lint:
	@find public src templates -name '*.php' -print0 | xargs -0 -n1 $(PHP) -l

clean:
	rm -rf vendor

.PHONY: install run sample-data lint clean
