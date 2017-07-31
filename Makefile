
SMC_JAR ?= Smc.jar
PUBLIC_SOURCES := satori/rtm/client.py satori/rtm/connection.py satori/rtm/auth.py satori/rtm/__init__.py satori/rtm/logger.py
GENERATED_SOURCES := satori/rtm/generated/client_sm.py satori/rtm/generated/subscription_sm.py

.PHONY: lint
lint: $(GENERATED_SOURCES)
	python -mflake8 cli satori tutorials test --exclude generated --max-line-length=80
	python -mflake8 --max-line-length=80 --ignore=F841 examples
	python -mpylint --reports=no --disable=R,C,broad-except,no-member,fixme,import-error satori/**/*.py
	python -mpylint --reports=no --disable=R,C,broad-except,no-member,relative-import miniws4py/**/*.py
	python -mpylint --reports=no --disable=R,C,broad-except,no-member,fixme,import-error cli/*.py
	python -mpylint --reports=no --disable=R,C,broad-except,redefined-builtin,fixme cli/satori-rtm-cli
	@echo 'Linters are happy'

.PHONY: clean
clean:
	-@find . -name '*.pyc' -delete
	-@find . -name '__pycache__' -delete
	-@rm doc/*.html || true

.PHONY: clean-generated
clean-generated:
	-@rm satori/rtm/generated/*_sm.py || true

.PHONY: doc
doc: doc/index.html

doc/index.html: $(PUBLIC_SOURCES) $(GENERATED_SOURCES) doc/generate.py
	cd doc && PYTHONPATH=.. python3 ./generate.py ".." > index.html

.PHONY: run-examples
run-examples: $(GENERATED_SOURCES)
	PYTHONPATH=. python examples/run_all_examples.py
	PYTHONPATH=. python examples/chat/bot.py bender `python -c 'import binascii; import os; print(binascii.hexlify(os.urandom(10)))'` 1

.PHONY: test
test: $(GENERATED_SOURCES)
	PYTHONPATH=. python test/run_all_tests.py
	$(MAKE) -C cli test

.PHONY: test-cli
test-cli:
	$(MAKE) -C cli test

.PHONY: test-coverage
test-coverage: $(GENERATED_SOURCES)
	PYTHONPATH=. coverage run --branch --concurrency=thread test/run_all_tests.py
	PYTHONPATH=. coverage report --omit '*venv*','*.tox*','*test*','*generated/statemap.py'
	PYTHONPATH=. coverage html --omit '*venv*','*.tox*','*test*','*generated/statemap.py'

.PHONY: combined-coverage
combined-coverage:
	tox -e py27-coverage && mv .coverage .coverage.27 && tox -e py36-coverage && mv .coverage .coverage.36 && coverage combine && coverage html --omit '*venv*','*.tox*','*test*','*generated/statemap.py'

.PHONY: bench
bench: $(GENERATED_SOURCES)
	PYTHONPATH=. python bench/bench_publish.py

.PHONY: stress
stress: $(GENERATED_SOURCES)
	PYTHONPATH=. python test/stress/pathologic.py
	PYTHONPATH=. python test/stress/threads.py

$(GENERATED_SOURCES): satori/rtm/generated/%_sm.py: state_machines/%.sm
	java -Xmx512m -jar $(SMC_JAR) -python -d . $<
	perl -pe 's/import statemap/import satori.rtm.generated.statemap as statemap/g;s/^#$$//g' $*_sm.py > $*_sm_.py
	pyflakes $*_sm_.py
	rm $*_sm.py
	mv $*_sm_.py $@

.PHONY: auto-%
auto-%:
	sos --pattern 'tutorials/.*\.py$$'\
		--pattern 'doc/.*\.py$$'\
		--pattern 'test/.*\.py$$'\
		--pattern 'examples/.*\.py$$'\
		--pattern 'satori/.*\.py$$'\
		--pattern 'miniws4py/.*\.py$$'\
		--pattern 'cli/.*\.py$$'\
		--command '$(MAKE) $*'

.PHONY: sdist
sdist: $(GENERATED_SOURCES)
	python setup.py sdist

.PHONY: bdist_wheel
bdist_wheel: $(GENERATED_SOURCES)
	python3 setup.py bdist_wheel

.PHONY: upload-test
upload-test: sdist bdist_wheel
	twine upload dist/* -r testpypi

.PHONY: upload-prod
upload-prod: sdist bdist_wheel
	twine upload dist/* -r pypi