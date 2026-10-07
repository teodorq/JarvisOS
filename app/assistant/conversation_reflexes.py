from __future__ import annotations

import re

from app.assistant.natural_language import fold_text
from app.assistant.conversation_topics import ConversationTopicBank


class ConversationReflexService:
    """Instant, deterministic replies for common Polish conversation moments."""

    def __init__(self) -> None:
        self.topics = ConversationTopicBank()

    _RULES = (
        (
            "presence",
            ("jestes tam", "czy jestes tam", "jestes jeszcze", "slyszysz mnie", "czy mnie slyszysz"),
            "Jestem tutaj i słucham. Możemy rozmawiać albo przejść do konkretnego zadania.",
        ),
        (
            "identity",
            ("kim jestes", "jak sie nazywasz", "przedstaw sie"),
            "Jestem JARVIS OS — Twoim lokalnym asystentem do rozmowy, organizacji i bezpiecznego wykonywania poleceń.",
        ),
        (
            "humanity",
            ("czy jestes prawdziwy", "czy jestes czlowiekiem", "jestes czlowiekiem"),
            "Jestem programem, nie człowiekiem, ale staram się rozmawiać jasno i naturalnie. Gdy czegoś nie wiem, powinienem powiedzieć to wprost.",
        ),
        (
            "trust",
            ("czy moge ci zaufac", "czy dbasz o prywatnosc"),
            "Możesz oczekiwać ode mnie przejrzystości: nie powinienem udawać wykonania ani ukrywać ograniczeń. Ważne działania wymagają osobnego potwierdzenia, a rozmowa działa lokalnie.",
        ),
        (
            "apology",
            ("przepraszam", "sorki", "wybacz"),
            "Nie szkodzi. Możemy spokojnie iść dalej.",
        ),
        (
            "confusion",
            ("nie rozumiem", "nie kumam", "to jest niejasne"),
            "Wyjaśnię to prościej. Napisz, który fragment jest niejasny, a rozłożę go na krótkie kroki.",
        ),
        (
            "support",
            ("potrzebuje wsparcia", "potrzebuje otuchy", "jest mi zle", "mam zly dzien"),
            "Jestem z Tobą. Możemy najpierw nazwać to, co teraz najbardziej ciąży, a potem wybrać jeden mały krok.",
        ),
        (
            "loneliness",
            ("czuje sie samot", "jestem samot", "doskwiera mi samotnosc"),
            "To może być naprawdę trudne. Możemy chwilę porozmawiać, a potem pomyśleć o jednej osobie, do której warto dziś napisać.",
        ),
        (
            "sadness",
            ("jestem smut", "smutno mi", "czuje smutek"),
            "Przykro mi, że tak się czujesz. Nie musisz od razu wszystkiego naprawiać — możesz powiedzieć, co się wydarzyło.",
        ),
        (
            "stress",
            ("jestem zestres", "stresuje sie", "denerwuje sie", "jestem zdenerw", "czuje niepokoj"),
            "Zatrzymajmy się na chwilę: powolny wdech, dłuższy wydech i rozluźnienie ramion. Potem oddzielimy to, na co masz wpływ, od reszty.",
        ),
        (
            "anger",
            ("jestem zly", "jestem wsciek", "wkurzylem sie", "jestem wkurz"),
            "Rozumiem, że emocje są teraz mocne. Zanim podejmiesz decyzję, dajmy sobie chwilę i ustalmy, co dokładnie Cię zdenerwowało.",
        ),
        (
            "fear",
            ("boje sie", "mam strach", "odczuwam strach"),
            "Możemy przejść przez to spokojnie. Powiedz, czego konkretnie się obawiasz, a oddzielimy realne ryzyko od czarnych scenariuszy.",
        ),
        (
            "tiredness",
            ("jestem zmecz", "padam ze zmeczenia", "nie mam sily"),
            "Brzmi, jakby organizm prosił o przerwę. Zróbmy tylko najważniejszą rzecz, a resztę odłóżmy bez poczucia winy.",
        ),
        (
            "sleep",
            ("nie moge zasnac", "mam problem ze snem", "nie chce mi sie spac"),
            "Spróbuj na kilka minut odłożyć ekran, przyciemnić światło i wydłużyć wydech. Jeśli chcesz, możemy też spokojnie uporządkować myśli, które nie dają Ci zasnąć.",
        ),
        (
            "motivation_low",
            ("nie chce mi sie", "brakuje mi motywacji", "nie mam motywacji"),
            "Nie czekajmy na pełną motywację. Wybierzmy krok, który zajmie najwyżej dwie minuty — rozpoczęcie zwykle jest najtrudniejsze.",
        ),
        (
            "motivate",
            ("zmotywuj mnie", "daj mi motywacje", "potrzebuje motywacji"),
            "Nie musisz zrobić wszystkiego naraz. Zrób teraz najmniejszy konkretny krok, a potem zdecydujemy o następnym.",
        ),
        (
            "calm",
            ("pomoz mi sie uspokoic", "chce sie uspokoic", "musze sie uspokoic"),
            "Oprzyj stopy o podłogę i zrób trzy spokojne oddechy, z wydechem dłuższym niż wdech. Rozejrzyj się i nazwij trzy rzeczy, które widzisz.",
        ),
        (
            "boredom",
            ("nudzi mi sie", "jestem znudz", "nie mam co robic"),
            "Możemy wybrać coś lekkiego: krótki spacer, nowy temat do poznania albo małe ulepszenie JARVIS-a. Na co masz dziś energię?",
        ),
        (
            "uncertainty",
            ("nie wiem co robic", "nie wiem od czego zaczac", "pogubilem sie"),
            "Zacznijmy od celu na najbliższe 15 minut. Napisz, co najbardziej Cię teraz blokuje, a wybiorę pierwszy mały krok.",
        ),
        (
            "good_mood",
            ("mam dobry humor", "jestem szczesliw", "ciesze sie"),
            "To świetnie. Warto wykorzystać tę energię na coś, co da Ci satysfakcję albo po prostu chwilę się nią nacieszyć.",
        ),
        (
            "success",
            ("udalo mi sie", "mam sukces", "jestem z siebie dumn"),
            "Brawo — warto to zauważyć, nie tylko od razu biec do kolejnego zadania. Co dokładnie Ci się udało?",
        ),
        (
            "compliment",
            ("powiedz cos milego", "pochwal mnie"),
            "Masz dużą wytrwałość — wracasz do projektu i konsekwentnie go rozwijasz. To właśnie regularność buduje coś naprawdę dobrego.",
        ),
        (
            "joke",
            ("opowiedz zart", "powiedz zart", "rozsmiesz mnie"),
            "Dlaczego programista pomylił Halloween z Bożym Narodzeniem? Bo OCT 31 to DEC 25.",
        ),
        (
            "topic",
            (
                "zaproponuj temat", "o czym mozemy porozmawiac",
                "wybierz temat rozmowy", "podaj temat", "o czym pogadamy",
                "o czym porozmawiamy", "rzuc jakis temat",
                "daj temat do rozmowy", "zacznij rozmowe",
                "powiedz cos ciekawego",
            ),
            "Możemy porozmawiać o planach JARVIS-a, technologii, treningu, finansach albo czymś zupełnie luźnym. Wybierz nastrój: praktyczny, ciekawy czy zabawny?",
        ),
        (
            "activity",
            ("co robisz", "czym sie zajmujesz"),
            "Czekam na Twoją wiadomość i pilnuję kontekstu rozmowy. Teraz cała moja uwaga jest tutaj.",
        ),
        (
            "memory_explanation",
            ("czy mnie zapamietasz", "czy to zapamietasz", "jak dziala twoja pamiec"),
            "Zapamiętuję na stałe tylko to, co wyraźnie poprzedzisz słowami „zapamiętaj, że”. W każdej chwili możesz zapytać „co o mnie pamiętasz?” albo kazać mi konkretną informację zapomnieć.",
        ),
        (
            "conversation_ability",
            ("czy umiesz rozmawiac", "mozemy pogadac", "chcesz porozmawiac"),
            "Tak, możemy rozmawiać swobodnie i wracać do ostatnich wątków. O czym masz ochotę pogadać?",
        ),
    )

    _ACKNOWLEDGEMENTS = {
        "ok": "Jasne.",
        "okej": "Jasne.",
        "dobra": "Dobrze, idziemy dalej.",
        "rozumiem": "Świetnie. Jestem gotowy na następny temat.",
        "jasne": "Dobrze.",
        "super": "Super. Co robimy dalej?",
        "swietnie": "Świetnie. Co robimy dalej?",
    }

    @property
    def mode_count(self) -> int:
        return len(self._RULES) + len(self._ACKNOWLEDGEMENTS) + 4

    @property
    def conversation_variant_count(self) -> int:
        return self.topics.variant_count

    def matches(self, value: object) -> bool:
        return bool(self.reply(value))

    def intent(self, value: object) -> str:
        folded = fold_text(value).strip(" .,!?:;")
        if folded in self._ACKNOWLEDGEMENTS:
            return "acknowledgement"
        if re.fullmatch(
            r"(?:czesc|hej|hejka|witaj|dzien dobry|dobry wieczor)(?: jarvis)?",
            folded,
        ):
            return "greeting"
        if folded.startswith(("dziekuje", "dzieki")):
            return "thanks"
        if "jak sie masz" in folded or "co slychac" in folded:
            return "wellbeing"
        if folded in {"dobranoc", "do zobaczenia", "na razie", "do jutra"}:
            return "farewell"
        for intent, signals, _response in self._RULES:
            if any(signal in folded for signal in signals):
                return intent
        return ""

    def is_context_sensitive(self, value: object) -> bool:
        return self.intent(value) in {
            "acknowledgement", "confusion", "support", "loneliness", "sadness",
            "stress", "anger", "fear", "tiredness", "sleep", "motivation_low",
            "motivate", "calm", "boredom", "uncertainty", "good_mood",
            "success", "compliment",
        }

    def reply(self, value: object, *, variant: int = 0) -> str:
        folded = fold_text(value).strip(" .,!?:;")
        if not folded:
            return ""
        if re.fullmatch(
            r"(?:czesc|hej|hejka|witaj|dzien dobry|dobry wieczor)(?: jarvis)?",
            folded,
        ):
            return "Cześć Kacper. Jestem gotowy — o czym chcesz porozmawiać?"
        if folded.startswith(("dziekuje", "dzieki")):
            return "Nie ma za co. Jestem tutaj, gdy będziesz chciał porozmawiać albo coś zrobić."
        if "jak sie masz" in folded or "co slychac" in folded:
            return "Dobrze — działam i jestem gotowy do rozmowy. Co dziś chodzi Ci po głowie?"
        if folded in {"dobranoc", "do zobaczenia", "na razie", "do jutra"}:
            return "Do zobaczenia Kacper. Będę gotowy, gdy wrócisz."
        if folded in self._ACKNOWLEDGEMENTS:
            return self._ACKNOWLEDGEMENTS[folded]
        for intent, signals, response in self._RULES:
            if any(signal in folded for signal in signals):
                if intent == "topic":
                    return self.topics.suggestion(seed=folded, variant=variant)
                return response
        return ""


__all__ = ["ConversationReflexService"]
