# FinRAG package

The application is organized by pipeline stage so each responsibility has one clear home:

- [`ingestion/`](ingestion/): obtain and prepare SEC filings.
- [`indexing/`](indexing/): create embeddings and manage the vector index.
- [`answering/`](answering/): retrieve evidence and generate grounded answers.
- [`evaluation/`](evaluation/): validate answer quality and citations.

Project-wide runtime settings remain in [`../../config.yaml`](../../config.yaml).
