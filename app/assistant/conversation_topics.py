from __future__ import annotations

import hashlib

from app.assistant.natural_language import fold_text


class ConversationTopicBank:
    """Compact bank producing 2,000 deterministic conversation starters."""

    _TOPICS = (
        "tym, jak powinien wyglądać naprawdę pomocny asystent",
        "technologii, która realnie ułatwia codzienne życie",
        "najciekawszym pomyśle, który ostatnio przyszedł Ci do głowy",
        "nawyku, który najbardziej chciałbyś u siebie rozwinąć",
        "miejscu, które chciałbyś kiedyś odwiedzić",
        "umiejętności, której warto byłoby nauczyć się w tym roku",
        "tym, co najlepiej pomaga Ci odzyskać energię",
        "projekcie, z którego chciałbyś być naprawdę dumny",
        "filmie, grze albo książce, które zostały Ci w pamięci",
        "muzyce, do której najczęściej wracasz",
        "tym, jak wyobrażasz sobie codzienność za pięć lat",
        "rzeczy, którą można dziś uprościć zamiast odkładać",
        "małej zmianie, która mogłaby poprawić cały tydzień",
        "tym, czego sztuczna inteligencja nadal nie rozumie wystarczająco dobrze",
        "najlepszym sposobie na spokojny i produktywny dzień",
        "decyzji, którą łatwiej byłoby podjąć po uporządkowaniu argumentów",
        "czymś ciekawym, co ostatnio zauważyłeś albo odkryłeś",
        "tym, co dla Ciebie oznacza dobrze wykorzystany czas",
        "pomysłach na dalszy rozwój JARVIS OS",
        "jednej rzeczy, którą zrobiłbyś, gdyby nic Cię nie ograniczało",
    )
    _OPENINGS = (
        "Możemy spokojnie porozmawiać o {topic}.",
        "Na teraz proponuję rozmowę o {topic}.",
        "Ciekawym kierunkiem może być rozmowa o {topic}.",
        "Chętnie poznam Twoje zdanie o {topic}.",
        "Możemy na chwilę zatrzymać się przy {topic}.",
        "Dobrym tematem na swobodną rozmowę będzie coś o {topic}.",
        "Mam propozycję: porozmawiajmy o {topic}.",
        "Możemy wspólnie zastanowić się nad tym, co sądzisz o {topic}.",
        "Jeśli masz ochotę na luźny temat, pogadajmy o {topic}.",
        "Zacznijmy od rozmowy o {topic}.",
    )
    _FOLLOWUPS = (
        "Co pierwsze przychodzi Ci do głowy?",
        "Masz już na ten temat własne zdanie?",
        "Która część tego tematu najbardziej Cię ciekawi?",
        "Jak wyglądałoby to w Twoim przypadku?",
        "Od czego chciałbyś zacząć?",
        "Co byłoby w tym dla Ciebie najważniejsze?",
        "Wolisz spojrzeć na to praktycznie czy bardziej na luzie?",
        "Czy masz z tym jakieś własne doświadczenie?",
        "Co mogłoby Cię tutaj najbardziej zaskoczyć?",
        "Jaki byłby Twój idealny scenariusz?",
    )

    @property
    def variant_count(self) -> int:
        return len(self._TOPICS) * len(self._OPENINGS) * len(self._FOLLOWUPS)

    def suggestion(self, *, seed: object = "", variant: int = 0) -> str:
        folded = fold_text(seed)
        digest = hashlib.blake2s(
            folded.encode("utf-8"), digest_size=4,
        ).digest()
        offset = int.from_bytes(digest, "big")
        index = (offset + max(0, int(variant))) % self.variant_count

        topic_count = len(self._TOPICS)
        opening_count = len(self._OPENINGS)
        topic = self._TOPICS[index % topic_count]
        opening = self._OPENINGS[(index // topic_count) % opening_count]
        followup = self._FOLLOWUPS[
            (index // (topic_count * opening_count)) % len(self._FOLLOWUPS)
        ]
        return f"{opening.format(topic=topic)} {followup}"


__all__ = ["ConversationTopicBank"]
