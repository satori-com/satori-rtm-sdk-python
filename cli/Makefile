
.PHONY: test
test:
	PYTHONPATH=.:.. python test_cli.py

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
