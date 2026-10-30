You are checking whether an ANSWER is supported by the CONTEXT it was generated from.
Find each factual claim in the answer (figures, facts, conclusions). A claim is supported if the context states it, or it follows by simple arithmetic from figures in the context. Do not use outside knowledge.

Return only JSON: {"claims": <number of claims>, "unsupported": ["<claim>", ...], "verdict": "faithful" | "unfaithful"}
The verdict is "faithful" only if every claim is supported.

CONTEXT:
{context}

QUESTION: {question}
ANSWER: {answer}