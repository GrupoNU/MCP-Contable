"""Boletin Nacional connector: tools over the Boletin Oficial de la Republica Argentina.

This connector SCRAPES the public web pages of ``boletinoficial.gob.ar``. There is no
official structured (JSON) API, so every result is grounded as :data:`SourceTier.B`:
usable, but flagged for verification against the official source because page structure
can change.

GOOD NEWS (verified against the live site, 2026-06): the substantive content of an
individual aviso (its title and full legal body text) IS present in the initial HTML
served over plain HTTP -- it is NOT rendered client-side by JavaScript. That means the
shared ``httpx``-based fetch layer can read it directly; no headless browser is needed
for ``boletin_get_aviso``.
"""

from __future__ import annotations
