from __future__ import annotations
from datetime import datetime
from pathlib import Path
import re
from typing import Any
from app.assistant.daily_work import DailyWorkService
from app.assistant.capability_guide import CapabilityGuideService
from app.assistant.natural_language import NaturalLanguageService, ResolvedCommand, fold_text
from app.assistant.project_memory import ProjectMemoryService
from app.assistant.reliable_desktop import ReliableDesktopService
from app.assistant.voice_runtime import VoiceRuntimeService
from app.assistant.weather import WeatherService
from app.assistant.status_formatter import AssistantStatusFormatter
from app.core.project_paths import resolve_project_root
from app.intelligence.controller import IntelligenceSuiteController
from app.productivity.controller import ProductivitySuiteController
from app.stability.controller import StabilitySuiteController
from app.assistant_v12.controller import AssistantV12Controller
from app.assistant_v12.conversation_engine import NaturalConversationEngineV3
from app.online_assistant.controller import OnlineAssistantController
from app.natural_actions import NaturalActionService
from app.integrations import IntegrationStatusService
from app.trading import TradingControlCenter
class PersonalAssistantController:
    """B96-B130 cohesive assistant runtime without bypassing safety gates."""
    STAGES = {
        "B96": "NATURAL_CONVERSATION_READY",
        "B97": "RELIABLE_DESKTOP_READY",
        "B98": "PROJECT_MEMORY_READY",
        "B99": "VOICE_2_READY",
        "B100": "DAILY_WORK_CENTER_READY",
        **IntelligenceSuiteController.STAGES,
        **ProductivitySuiteController.STAGES,
        **StabilitySuiteController.STAGES,
        **AssistantV12Controller.STAGES,
        **OnlineAssistantController.STAGES,
        **NaturalActionService.STAGES,
    }
    def __init__(self, project_root: str | Path | None = None, *, memory: Any | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.memory = memory
        self.conversation = NaturalLanguageService(self.project_root)
        self.capabilities = CapabilityGuideService()
        self.desktop = ReliableDesktopService(self.project_root)
        self.projects = ProjectMemoryService(self.project_root)
        self.voice = VoiceRuntimeService(self.project_root)
        self.weather = WeatherService()
        self.daily = DailyWorkService(self.project_root)
        self.intelligence = IntelligenceSuiteController(self.project_root)
        self.productivity = ProductivitySuiteController(self.project_root)
        self.stability = StabilitySuiteController(self.project_root, runtime_status=self._stability_runtime_status)
        self.assistant_v12 = AssistantV12Controller(self.project_root)
        self.online = OnlineAssistantController(self.project_root, reminders=self.productivity.reminders)
        self.natural_actions = NaturalActionService(self.project_root, online=self.online)
        self.integrations = IntegrationStatusService()
        self.trading = TradingControlCenter(self.project_root)
    @staticmethod
    def matches(command: object) -> bool:
        text = fold_text(command)
        phrases = (
            "ktora jest godzina",
            "jaka jest godzina",
            "podaj godzine",
            "powiedz mi godzine",
            "aktualna godzina",
            "pogoda", "pogode", "pogody", "weather", "forecast",
            "co potrafisz",
            "co umiesz",
            "co mozesz zrobic",
            "jakie masz funkcje",
            "pokaz pomoc",
            "pomoc jarvis",
            "jak z ciebie korzystac",
            "przyklady polecen",
            "lista polecen",
            "centrum mozliwosci",
            "status asystenta",
            "status b96",
            "status b97",
            "status b98",
            "status b99",
            "status b100",
            "status rozmowy",
            "kontekst rozmowy",
            "status sterowania pulpitem",
            "niezawodne sterowanie",
            "status pamieci projektow",
            "pamiec projektow",
            "zapamietaj projekt",
            "dodaj projekt",
            "ustaw aktywny projekt",
            "przelacz projekt",
            "zapamietaj preferencje",
            "ustaw preferencje",
            "status glosu",
            "glos 2.0",
            "voice 2.0",
            "status integracji",
            "pokaz integracje",
            "jakie integracje",
            "polaczenia zewnetrzne",
            "status revenuecat",
            "status meta ads",
            "status claude",
            "status cartesia",
            "status elevenlabs",
            "status paper tradingu", "stan paper tradingu", "status tradingu", "gotowosc tradingu", "gotowosc do tradingu", "zabezpieczenia tradingu", "audyt tradingu", "status silnika tradingowego", "status forex", "gotowosc forex", "skaner forex", "status obserwatora forex", "ile obserwacji forex", "postep obserwacji forex", "czy paper gotowy", "czy paper jest gotowy",
            "tryb ciagly glosu",
            "centrum codziennej pracy",
            "status codziennej pracy",
            "utworz zadanie wieloetapowe",
            "rozpocznij zadanie",
            "uruchom zadanie",
            "nastepny krok",
            "wykonano krok",
            "wstrzymaj zadanie",
            "wznow zadanie",
            "anuluj zadanie",
            "dodaj przypomnienie",
            "przypomnij mi",
            "eksportuj raport codziennej pracy",
            "wyczysc kontekst rozmowy",
            "kontynuuj ostatnie zadanie",
            "jeszcze raz",
            "powtorz",
            "zrob to jeszcze raz",
            "kontynuuj",
            "jedz dalej",
        )
        return (
            any(phrase in text for phrase in phrases)
            or IntelligenceSuiteController.matches(command)
            or ProductivitySuiteController.matches(command)
            or StabilitySuiteController.matches(command)
            or NaturalConversationEngineV3.matches(command)
            or OnlineAssistantController.matches(command)
            or NaturalActionService.matches(command)
        )
    def resolve_command(self, command: object) -> ResolvedCommand:
        resolved = self.conversation.resolve(command)
        if self._is_direct_core_command(resolved):
            return resolved
        if self.natural_actions.has_pending() or self.natural_actions.matches(resolved.resolved):
            return ResolvedCommand(resolved.original, resolved.resolved, "natural_action", resolved.used_context)
        return resolved
    @staticmethod
    def _is_direct_core_command(resolved: ResolvedCommand) -> bool:
        return (
            not resolved.used_context
            and resolved.intent not in {"standard", "clarification", "natural_action"}
        )
    def can_handle(self, command: object) -> bool:
        resolved = self.resolve_command(command)
        return resolved.intent != "standard" or self.matches(resolved.resolved)
    def plan(self, command: object) -> dict[str, Any]:
        resolved = self.resolve_command(command)
        if resolved.intent == "natural_action":
            return self.natural_actions.plan(resolved.resolved)
        if self.online.matches(resolved.resolved):
            thought = self.online.plan(resolved.resolved)
            thought.update({
                "original_command": resolved.original,
                "used_context": resolved.used_context,
                "clarification": resolved.clarification,
            })
            return thought
        if (
            not self._is_direct_core_command(resolved)
            and self.assistant_v12.matches(resolved.resolved)
        ):
            thought = self.assistant_v12.plan(resolved.resolved)
            thought.update({
                "original_command": resolved.original,
                "used_context": resolved.used_context or thought.get("v12_used_context", False),
                "clarification": thought.get("clarification", "") or resolved.clarification,
            })
            return thought
        if StabilitySuiteController.matches(resolved.resolved):
            thought = self.stability.plan(resolved.resolved)
            thought.update({
                "original_command": resolved.original,
                "used_context": resolved.used_context,
                "clarification": resolved.clarification,
            })
            return thought
        if ProductivitySuiteController.matches(resolved.resolved):
            thought = self.productivity.plan(resolved.resolved)
            thought.update({
                "original_command": resolved.original,
                "used_context": resolved.used_context,
                "clarification": resolved.clarification,
            })
            return thought
        if IntelligenceSuiteController.matches(resolved.resolved):
            thought = self.intelligence.plan(resolved.resolved)
            thought.update({
                "original_command": resolved.original,
                "used_context": resolved.used_context,
                "clarification": resolved.clarification,
            })
            return thought
        read_only = resolved.intent in {
            "current_time",
            "weather",
            "capability_help",
            "assistant_status",
            "conversation_status",
            "memory_status",
            "voice_status",
            "desktop_status",
            "daily_status",
            "integration_status",
            "paper_trading_status",
            "clarification",
        }
        return {
            "command": resolved.resolved,
            "original_command": resolved.original,
            "goal": "Obsłużyć polecenie przez osobistego asystenta JARVIS OS",
            "plan": [
                "Rozpoznać naturalną intencję i kontekst rozmowy",
                "Sprawdzić pamięć projektu oraz aktywne zadanie",
                "Zastosować ograniczenia bezpieczeństwa i uprawnień",
                "Wykonać operację B96–B100 albo przygotować następny krok",
                "Zapisać wynik i postęp w trwałej pamięci",
            ],
            "actions": [],
            "can_execute": True,
            "handler": "personal_assistant",
            "assistant_intent": resolved.intent,
            "read_only": read_only,
            "used_context": resolved.used_context,
            "clarification": resolved.clarification,
        }
    def handle(self, command: object) -> str:
        resolved = self.resolve_command(command)
        if resolved.clarification:
            return resolved.clarification
        intent = resolved.intent
        text = resolved.resolved
        direct_core = self._is_direct_core_command(resolved)
        natural_command = not direct_core and (
            intent == "natural_action" or self.natural_actions.has_pending()
        )
        online_command = not direct_core and self.online.matches(text)
        v12_command = not direct_core and self.assistant_v12.matches(text)
        stability_command = not direct_core and StabilitySuiteController.matches(text)
        productivity_command = not direct_core and ProductivitySuiteController.matches(text)
        suite_command = not direct_core and IntelligenceSuiteController.matches(text)
        try:
            if direct_core:
                response = self._dispatch(intent, text)
            elif natural_command:
                response = self.natural_actions.handle(text)
                intent = "natural_action"
            elif online_command:
                response = self.online.handle(text)
                intent = self.online.intent(text)
            elif v12_command:
                response = self.assistant_v12.handle(text)
                intent = self.assistant_v12.conversation.parse(text).intent
            elif stability_command:
                response = self.stability.handle(text)
                intent = self.stability.intent(text)
            elif productivity_command:
                response = self.productivity.handle(text)
                intent = self.productivity.intent(text)
            elif suite_command:
                response = self.intelligence.handle(text)
                intent = self.intelligence.intent(text)
            else:
                response = self._dispatch(intent, text)
        except (ValueError, KeyError) as error:
            response = str(error).strip("'")
        except Exception as error:
            response = f"B96–B130: operacja nie powiodła się: {type(error).__name__}: {error}"
        target = self.conversation.extract_target(text)
        if intent != "clear_context":
            self.conversation.context.update(
                command=text,
                intent=intent,
                target=target,
                response=response,
            )
        if self.memory is not None:
            try:
                self.memory.add_history(text, response)
            except Exception:
                raise RuntimeError("AutoDev: przechwycony wyjątek")
        return response
    def set_progress_callback(self, callback: Any | None) -> None:
        self.assistant_v12.set_progress_callback(callback)
        self.online.set_progress_callback(callback)
    def execute_standard_action(self, action: dict[str, Any], executor: Any) -> str:
        if self.intelligence.desktop.supports(action):
            return self.intelligence.desktop.execute_action(action, executor)
        return str(executor.execute_action(action))
    def status(self) -> dict[str, Any]:
        return {
            "status": "CORE_PRODUCT_UPGRADE_READY",
            "stages": dict(self.STAGES),
            "conversation": self._conversation_status(),
            "capabilities": self.capabilities.status(),
            "desktop": self.desktop.status(),
            "memory": self.projects.status(),
            "voice": self.voice.status(),
            "weather": self.weather.status(),
            "daily_work": self.daily.status(),
            "intelligence": self.intelligence.status(),
            "productivity": self.productivity.status(),
            "stability": self.stability.status(),
            "assistant_v12": self.assistant_v12.status(),
            "online": self.online.status(),
            "natural_actions": self.natural_actions.status(),
            "integrations": self.integrations.status(),
            "safety": {
                "auto_approve": False,
                "max_active_executions": 1,
                "remote_code_execution": False,
                "desktop_retries_max": self.desktop.max_attempts,
            },
        }
    def _dispatch(self, intent: str, command: str) -> str:
        if intent == "current_time":
            return f"Teraz jest {datetime.now().strftime('%H:%M')}."
        if intent == "weather":
            return self.weather.format_for_command(command)
        if intent == "capability_help":
            return self.capabilities.format_guide()
        if intent == "assistant_status":
            return self._format_full_status()
        if intent == "conversation_status":
            return self._format_conversation_status()
        if intent == "desktop_status":
            return self._format_desktop_status()
        if intent == "memory_status":
            return self._format_memory_status()
        if intent == "voice_status":
            return self._format_voice_status()
        if intent == "daily_status":
            return self._format_daily_status()
        if intent == "integration_status":
            return self.integrations.format_status()
        if intent == "paper_trading_status": return self.trading.format_status()
        if intent == "remember_project":
            return self._remember_project(command)
        if intent == "activate_project":
            return self._activate_project(command)
        if intent == "remember_preference":
            return self._remember_preference(command)
        if intent == "add_workflow":
            title, steps = self.daily.parse_workflow_command(command)
            workflow = self.daily.create_workflow(title, steps)
            return (
                f"B100: utworzono zadanie „{workflow['title']}” "
                f"z liczbą kroków: {len(workflow['steps'])}."
            )
        if intent == "start_workflow":
            query = re.sub(
                r"^(?:rozpocznij|uruchom)\s+zadanie\s*",
                "",
                command,
                flags=re.IGNORECASE,
            ).strip()
            workflow = self.daily.start(query)
            return self._workflow_progress(workflow, prefix="B100: uruchomiono")
        if intent == "next_step":
            workflow = self.daily.complete_current_step()
            return self._workflow_progress(workflow, prefix="B100: zapisano krok")
        if intent == "pause_workflow":
            return self._workflow_progress(self.daily.pause(), prefix="B100: wstrzymano")
        if intent == "resume_workflow":
            return self._workflow_progress(self.daily.resume(), prefix="B100: wznowiono")
        if intent == "cancel_workflow":
            return self._workflow_progress(self.daily.cancel(), prefix="B100: anulowano")
        if intent == "reminder":
            content, minutes = self.daily.parse_reminder_command(command)
            reminder = self.daily.add_reminder(content, minutes=minutes)
            return f"B100: zapisano przypomnienie na {reminder['due_at']}: {reminder['text']}"
        if intent == "clear_context":
            self.conversation.context.clear()
            return "B96: wyczyszczono ograniczony kontekst rozmowy."
        if "eksportuj raport codziennej pracy" in fold_text(command):
            report = self.daily.export_report()
            return f"B100: raport zapisany: {report['path']}"
        if "tryb ciągły głosu" in command.casefold() or "tryb ciagly glosu" in fold_text(command):
            enabled = not any(word in fold_text(command) for word in ("wylacz", "stop", "nie"))
            self.voice.update({"continuous_mode": enabled})
            return f"B99: tryb ciągły głosu {'włączony' if enabled else 'wyłączony'}."
        return self._format_full_status()
    def _remember_project(self, command: str) -> str:
        match = re.search(
            r"(?:zapamiętaj|zapamietaj|dodaj)\s+projekt\s+(.+?)(?:\s+w\s+([A-Za-z]:[\\/].+))?$",
            command,
            re.IGNORECASE,
        )
        if not match:
            raise ValueError("Użyj: Zapamiętaj projekt NAZWA w C:\\ścieżka.")
        project = self.projects.remember_project(
            match.group(1).strip(),
            path=(match.group(2) or "").strip(),
        )
        return f"B98: zapisano i aktywowano projekt „{project['name']}”."
    def _activate_project(self, command: str) -> str:
        name = re.sub(
            r"^(?:ustaw aktywny projekt|przełącz projekt|przelacz projekt)\s*",
            "",
            command,
            flags=re.IGNORECASE,
        ).strip()
        project = self.projects.activate_project(name)
        return f"B98: aktywny projekt: {project['name']}."
    def _remember_preference(self, command: str) -> str:
        content = re.sub(
            r"^(?:zapamiętaj|zapamietaj|ustaw)\s+preferencj(?:ę|e)\s*",
            "",
            command,
            flags=re.IGNORECASE,
        ).strip()
        if "=" in content:
            key, value = [part.strip() for part in content.split("=", 1)]
        elif ":" in content:
            key, value = [part.strip() for part in content.split(":", 1)]
        else:
            raise ValueError("Użyj: Zapamiętaj preferencję KLUCZ = WARTOŚĆ.")
        self.projects.set_preference(key, value)
        return f"B98: zapisano preferencję „{key}”."
    def _stability_runtime_status(self) -> dict[str, Any]:
        return {
            "conversation": self._conversation_status(),
            "intelligence": self.intelligence.status(),
            "productivity": self.productivity.status(),
            "online": self.online.status(),
            "natural_actions": self.natural_actions.status(),
            "safety": {
                "auto_approve": False,
                "remote_code_execution": False,
            },
        }
    def _conversation_status(self) -> dict[str, Any]:
        data = self.conversation.context.load()
        return {
            "status": "NATURAL_CONVERSATION_READY",
            "turn_count": len(list(data.get("turns", []) or [])),
            "last_intent": data.get("last_intent", ""),
            "last_target": data.get("last_target", ""),
            "context_limit": 50,
        }
    def _format_full_status(self) -> str:
        return AssistantStatusFormatter.full(self.status())
    def _format_conversation_status(self) -> str:
        return AssistantStatusFormatter.conversation(self._conversation_status())
    def _format_desktop_status(self) -> str:
        return AssistantStatusFormatter.desktop(self.desktop.status())
    def _format_memory_status(self) -> str:
        return AssistantStatusFormatter.memory(self.projects.status())
    def _format_voice_status(self) -> str:
        return AssistantStatusFormatter.voice(self.voice.status())
    def _format_daily_status(self) -> str:
        return AssistantStatusFormatter.daily(
            self.daily.status(), self.productivity.reminders.status(),
        )
    @staticmethod
    def _workflow_progress(workflow: dict[str, Any], *, prefix: str) -> str:
        steps = list(workflow.get("steps", []) or [])
        completed = sum(1 for step in steps if step.get("status") == "COMPLETED")
        index = int(workflow.get("current_step", 0) or 0)
        next_step = str(steps[index].get("command", "")) if index < len(steps) else "BRAK"
        return (
            f"{prefix} „{workflow.get('title', '')}”. "
            f"Status {workflow.get('status')}, postęp {completed}/{len(steps)}, "
            f"następny krok: {next_step}."
        )
