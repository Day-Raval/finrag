# Corpus

This package will manage the filing corpus: the company and fiscal-year selection, the manifest, and the chunking of parsed 10-K sections.

It is planned to produce fixed-size chunks (512 tokens, 64-token overlap, per `config.yaml`) that keep company, fiscal year, and section metadata for citations.
