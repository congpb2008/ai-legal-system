"""Retrieval Service (tasks/009-retrieval.md, module Retrieval).

The Retrieval Service discovers the most relevant legal evidence for a user query.
It returns evidence — it does NOT generate answers, summarize, or interpret legal
meaning.

The Retrieval Service bridges user intent and indexed legal knowledge.
Generation depends entirely on retrieval quality.
"""

from legal_platform.modules.retrieval.service import RetrievalService

__all__ = ["RetrievalService"]