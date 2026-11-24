test:
	python3 -m unittest discover -s tests -v

doctor:
	bin/dops doctor

dry:
	bin/dops recipe run iap-mitm --target cat-gunner --dry-run

.PHONY: test doctor dry
