from __future__ import annotations
import re
from iri.gateway.identity_vault import IdentityVault
from iri.gateway.redactor import RedactionResult
from iri.gateway.types import RedactionState


# A placeholder is an uppercase kind, an underscore, and 8 hex characters.
# Anchored on purpose: this must match a WHOLE span, never a substring.
_PLACEHOLDER_PATTERN = re.compile(r"^[A-Z]+_[a-f0-9]{8}$")


def _is_placeholder(span: str) -> bool:
    """True if this span is already one of our placeholders.

    Detectors run in sequence on progressively-redacted text, so by the time NER
    runs the text is full of placeholders. Without this guard spaCy reads them as
    entities and they get redacted AGAIN -- and, worse, stored in the vault as
    though they were real identities. known_entities() feeds the outbound scan,
    so a polluted vault makes that scan report redacted text as leaking.
    """
    return bool(_PLACEHOLDER_PATTERN.match(span))


class EntityRedactor:
    """
    The real redactor. It finds sensitive spans in text and replaces each with a stable placeholder from the identity vault,
    returning a RedactionResult the gateway branches on.

    The design is based on the measurement that spaCy's en_core_web_sm model failed to detect "Cailin" in the sentence
    "Cailin at BlueCross BlueShield of Tennessee emailed me from c@bcbst.com on 555-123-4567." It returned ORG "BlueCross BlueShield"
    (truncated), GPE "Tennessee", GPE "c@bcbst.com" (an email misread as a place), and CARDINAL "555" (a fragment of a phone number).
    It missed "Cailin" entirely — the person's name, the most important entity in the sentence.

    So NER alone is NOT sufficient and must never be the only detector. Structured identifiers must be caught by deterministic
    patterns, which do not miss.
    """

    def __init__(self, vault: IdentityVault):
        self.vault = vault

    def redact(self, text: str) -> RedactionResult:
        try:
            # Detector 1: Vault-known entities
            text, vault_replacements = self._replace_vault_known_entities(text)

            # Detector 2: Structured patterns
            text, pattern_replacements = self._replace_structured_patterns(text)

            # Detector 3: Named entities via spaCy
            try:
                text, ner_replacements = self._replace_named_entities(text)
            except Exception:
                return RedactionResult(text=text, state=RedactionState.PARTIAL, replacements=0, reason="spaCy NER")

            total_replacements = vault_replacements + pattern_replacements + ner_replacements
            return RedactionResult(text=text, state=RedactionState.COMPLETE, replacements=total_replacements, reason=None)
        except Exception as e:
            return RedactionResult(text=text, state=RedactionState.FAILED, replacements=0, reason=f"deterministic detector failed: {type(e).__name__}")

    def _replace_vault_known_entities(self, text: str) -> tuple[str, int]:
        known_entities = self.vault.known_entities()
        replacements = {}
        for entity in known_entities:
            pattern = re.compile(re.escape(entity), re.IGNORECASE)
            matches = pattern.finditer(text)
            for match in matches:
                span_text = match.group()
                if span_text not in replacements:
                    replacements[span_text] = self.vault.placeholder_for(span_text, "vault_known")
        new_text = self._replace_longest_first(text, replacements)
        return new_text, len(replacements)

    def _replace_structured_patterns(self, text: str) -> tuple[str, int]:
        patterns = {
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}': 'email',
            r'\+?\d[\d -]{8,}\d': 'phone',
            r'https?://[^\s]+': 'url'
        }
        replacements = {}
        for pattern, kind in patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                span_text = match.group()
                if span_text not in replacements:
                    replacements[span_text] = self.vault.placeholder_for(span_text, kind)
        new_text = self._replace_longest_first(text, replacements)
        return new_text, len(replacements)

    def _replace_named_entities(self, text: str) -> tuple[str, int]:
        """Best-effort NER. Exceptions propagate so redact() returns PARTIAL.

        Deliberately NOT wrapped in a try/except returning a clean result: a
        swallowed spaCy failure would look like a successful redaction with a
        silent gap, which is the failure mode the gateway exists to prevent.
        """
        import spacy  # lazy: heavy, and may be absent

        nlp = spacy.load("en_core_web_sm")
        replacements: dict[str, str] = {}
        for ent in nlp(text).ents:
            if _is_placeholder(ent.text):
                continue  # already redacted; see _is_placeholder
            if ent.label_ == "PERSON":
                kind = "person"
            elif ent.label_ == "ORG":
                kind = "employer"
            else:
                continue  # GPE and CARDINAL measured as false-positive prone
            if ent.text not in replacements:
                replacements[ent.text] = self.vault.placeholder_for(ent.text, kind)
        return self._replace_longest_first(text, replacements), len(replacements)

    def _replace_longest_first(self, text: str, replacements: dict[str, str]) -> str:
        sorted_replacements = sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True)
        for span_text, placeholder in sorted_replacements:
            text = text.replace(span_text, placeholder)
        return text
