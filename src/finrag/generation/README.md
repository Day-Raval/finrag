# Generation

This package will call the Groq answer model (`openai/gpt-oss-120b`, per `config.yaml`) with the prompt in `prompts/answer_v1.md` and the retrieved filing context.

Answers must cite facts as `[company, year, section]` and return `Not found in the filings.` when the context lacks support.
