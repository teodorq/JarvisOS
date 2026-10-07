from __future__ import annotations

import hashlib

from app.assistant.natural_language import fold_text


class ConversationTopicBank:
    """Compact bank producing 10,000 deterministic conversation starters."""

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
        "dziecięcym marzeniu, które nadal wydaje Ci się ciekawe",
        "najlepszej radzie, jaką kiedykolwiek dostałeś",
        "lekcji, której nauczyło Cię własne doświadczenie",
        "rzeczy, której chciałbyś spróbować po raz pierwszy",
        "tym, co sprawia, że miejsce zaczyna być dla Ciebie domem",
        "sposobie na zachowanie spokoju w trudnym momencie",
        "granicy między wygodą a prawdziwym odpoczynkiem",
        "wynalazku, który najbardziej zmienił codzienne życie",
        "zawodzie, którego chciałbyś spróbować przez jeden dzień",
        "idealnym miejscu do skupienia i spokojnej pracy",
        "drobnej przyjemności, która potrafi poprawić Ci dzień",
        "najbardziej niedocenianej umiejętności w codziennym życiu",
        "decyzji z przeszłości, która dużo Cię nauczyła",
        "ciekawym problemie, który chciałbyś kiedyś rozwiązać",
        "sporcie albo aktywności, które dają najwięcej satysfakcji",
        "jedzeniu, które kojarzy Ci się z dobrym wspomnieniem",
        "tradycji, którą warto byłoby zachować na przyszłość",
        "rzeczy, którą ludzie niepotrzebnie sobie komplikują",
        "sposobie na mądre korzystanie z telefonu i internetu",
        "tym, jak rozpoznać naprawdę dobry pomysł",
        "wymarzonym dniu bez żadnych obowiązków",
        "człowieku, od którego nauczyłeś się czegoś ważnego",
        "tym, jak technologia zmienia relacje między ludźmi",
        "zasadzie, której nie chciałbyś złamać nawet dla wygody",
        "tym, co najbardziej pobudza Twoją ciekawość",
        "ryzyku, które czasem warto podjąć",
        "najlepszym pomyśle na wykorzystanie wolnej godziny",
        "różnicy między byciem zajętym a robieniem postępów",
        "tym, czy przyszłość będzie prostsza dzięki automatyzacji",
        "pytaniu, na które chciałbyś kiedyś znaleźć dobrą odpowiedź",
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
        "Co najbardziej wpłynęło na Twoje obecne zdanie?",
        "Czy kiedyś myślałeś o tym inaczej niż teraz?",
        "Jak wyjaśniłbyś to komuś w jednym zdaniu?",
        "Co jest tutaj łatwe, a co najbardziej wymagające?",
        "Jaki pierwszy krok miałby w tym najwięcej sensu?",
        "Co chciałbyś w tym lepiej zrozumieć?",
        "Jaką jedną rzecz zmieniłbyś w pierwszej kolejności?",
        "Co przemawia za tym pomysłem, a co przeciw niemu?",
        "Jak wyglądałaby najbardziej realistyczna wersja?",
        "Co sprawiłoby, że ten temat stałby się dla Ciebie ważniejszy?",
    )
    _CATEGORY_INDEXES = {
        "light": (4, 8, 9, 16, 23, 28, 30, 34, 35, 40, 46),
        "deep": (10, 17, 19, 20, 21, 22, 24, 26, 32, 36, 41, 43, 45, 49),
        "practical": (3, 5, 6, 7, 11, 12, 14, 15, 25, 29, 31, 38, 39, 47),
        "creative": (2, 10, 19, 20, 23, 27, 28, 33, 40, 44, 48),
        "technology": (0, 1, 13, 18, 27, 38, 42, 48),
    }
    _CATEGORY_SIGNALS = (
        ("technology", ("technolog", "sztuczna inteligencja", " ai ")),
        ("deep", ("glebok", "powazn", "refleksyj")),
        ("practical", ("praktycz", "konkretn", "rozwojow")),
        ("creative", ("kreatywn", "nietypow", "wyobraz")),
        ("light", ("luzn", "lekki", "zabawn")),
    )

    @property
    def variant_count(self) -> int:
        return len(self._TOPICS) * len(self._OPENINGS) * len(self._FOLLOWUPS)

    @property
    def category_count(self) -> int:
        return len(self._CATEGORY_INDEXES)

    def detect_category(self, value: object) -> str:
        folded = f" {fold_text(value)} "
        for category, signals in self._CATEGORY_SIGNALS:
            if any(signal in folded for signal in signals):
                return category
        return ""

    def suggestion(
        self, *, seed: object = "", variant: int = 0, category: str = "",
    ) -> str:
        folded = fold_text(seed)
        digest = hashlib.blake2s(
            folded.encode("utf-8"), digest_size=4,
        ).digest()
        offset = int.from_bytes(digest, "big")
        indexes = self._CATEGORY_INDEXES.get(
            str(category), tuple(range(len(self._TOPICS))),
        )
        topics = tuple(self._TOPICS[index] for index in indexes)
        available_variants = (
            len(topics) * len(self._OPENINGS) * len(self._FOLLOWUPS)
        )
        index = (offset + max(0, int(variant))) % available_variants

        topic_count = len(topics)
        opening_count = len(self._OPENINGS)
        topic = topics[index % topic_count]
        opening = self._OPENINGS[(index // topic_count) % opening_count]
        followup = self._FOLLOWUPS[
            (index // (topic_count * opening_count)) % len(self._FOLLOWUPS)
        ]
        return f"{opening.format(topic=topic)} {followup}"


__all__ = ["ConversationTopicBank"]
