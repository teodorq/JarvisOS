from __future__ import annotations

import ast
from pathlib import PurePosixPath

from .feature_models import (
    FeatureBlueprint,
    FeatureFileSpec,
)


class FeatureCodeGenerator:
    """Builds a coherent, deterministic multi-file feature scaffold."""

    def generate(
        self,
        blueprint: FeatureBlueprint,
        *,
        overrides: dict[str, str] | None = None,
    ) -> dict[str, str]:
        if not isinstance(
            blueprint,
            FeatureBlueprint,
        ):
            raise TypeError(
                "blueprint musi być obiektem FeatureBlueprint."
            )

        overrides = {
            str(path).replace(
                "\\",
                "/",
            ): str(content)
            for path, content in dict(
                overrides or {}
            ).items()
        }
        file_map = blueprint.file_map()
        replacements: dict[str, str] = {}

        for file_id in blueprint.creation_order:
            spec = file_map.get(
                file_id
            )

            if spec is None:
                raise ValueError(
                    "Plan tworzenia odwołuje się do "
                    f"nieznanego pliku: {file_id}"
                )

            path = spec.relative_path.replace(
                "\\",
                "/",
            )
            content = overrides.get(
                path,
                self._content_for(
                    blueprint,
                    spec,
                ),
            )

            if not content.strip():
                raise ValueError(
                    f"Wygenerowano pusty plik: {path}"
                )

            if not content.endswith(
                "\n"
            ):
                content += "\n"

            try:
                ast.parse(
                    content,
                    filename=path,
                )
            except SyntaxError as error:
                raise ValueError(
                    "Wygenerowany plik ma błąd składni "
                    f"{path}:{error.lineno}: {error.msg}"
                ) from error

            replacements[path] = content

        unknown_overrides = sorted(
            set(overrides)
            - set(replacements)
        )

        if unknown_overrides:
            raise ValueError(
                "Overrides zawiera pliki spoza blueprintu: "
                + ", ".join(
                    unknown_overrides
                )
            )

        if len(replacements) != len(
            blueprint.files
        ):
            raise ValueError(
                "Nie wygenerowano wszystkich plików blueprintu."
            )

        return replacements

    def _content_for(
        self,
        blueprint: FeatureBlueprint,
        spec: FeatureFileSpec,
    ) -> str:
        handlers = {
            "model": self._models,
            "repository": self._repository,
            "service": self._service,
            "controller": self._controller,
            "package": self._package_init,
            "test": self._tests,
        }
        handler = handlers.get(
            spec.category.casefold(),
            self._fallback,
        )
        return handler(
            blueprint,
            spec,
        )

    @staticmethod
    def _models(
        blueprint: FeatureBlueprint,
        spec: FeatureFileSpec,
    ) -> str:
        name = blueprint.feature_name
        objective = repr(
            blueprint.objective
        )

        return f'''from __future__ import annotations

"""Modele danych dla funkcjonalności {name}."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class {name}Request:
    """Wejście funkcjonalności {name}."""

    payload: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class {name}Result:
    """Ustrukturyzowany wynik funkcjonalności {name}."""

    success: bool
    status: str
    data: dict[str, Any] = field(
        default_factory=dict
    )
    errors: list[str] = field(
        default_factory=list
    )


FEATURE_OBJECTIVE = {objective}
'''

    @staticmethod
    def _repository(
        blueprint: FeatureBlueprint,
        spec: FeatureFileSpec,
    ) -> str:
        name = blueprint.feature_name

        return f'''from __future__ import annotations

"""Repozytorium danych dla funkcjonalności {name}."""

from typing import Any


class {name}Repository:
    """Proste repozytorium możliwe do zastąpienia adapterem trwałym."""

    def __init__(self) -> None:
        self._items: dict[str, Any] = {{}}

    def save(
        self,
        key: str,
        value: Any,
    ) -> None:
        normalized = str(
            key
        ).strip()

        if not normalized:
            raise ValueError(
                "Klucz repozytorium nie może być pusty."
            )

        self._items[normalized] = value

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        return self._items.get(
            str(key),
            default,
        )

    def snapshot(self) -> dict[str, Any]:
        return dict(
            self._items
        )
'''

    @staticmethod
    def _service(
        blueprint: FeatureBlueprint,
        spec: FeatureFileSpec,
    ) -> str:
        name = blueprint.feature_name
        has_repository = (
            "repository"
            in blueprint.file_map()
        )
        repository_import = (
            f"from .repository import {name}Repository\n"
            if has_repository
            else ""
        )
        repository_argument = (
            f"repository: {name}Repository | None = None,"
            if has_repository
            else ""
        )
        repository_init = (
            f'''        self.repository = (
            repository
            or {name}Repository()
        )
'''
            if has_repository
            else ""
        )
        repository_use = (
            '''        self.repository.save(
            "last_payload",
            payload,
        )
'''
            if has_repository
            else ""
        )
        objective = repr(
            blueprint.objective
        )

        return f'''from __future__ import annotations

"""Logika biznesowa funkcjonalności {name}."""

from .models import (
    {name}Request,
    {name}Result,
)
{repository_import}

class {name}Service:
    """Realizuje cel: {blueprint.objective}"""

    def __init__(
        self,
        {repository_argument}
    ) -> None:
{repository_init or "        pass\n"}
    def execute(
        self,
        request: {name}Request,
    ) -> {name}Result:
        if not isinstance(
            request,
            {name}Request,
        ):
            return {name}Result(
                success=False,
                status="INVALID_REQUEST",
                errors=[
                    "Nieprawidłowy typ żądania.",
                ],
            )

        payload = dict(
            request.payload
        )
{repository_use}
        return {name}Result(
            success=True,
            status="COMPLETED",
            data={{
                "feature": "{name}",
                "objective": {objective},
                "payload": payload,
            }},
        )
'''

    @staticmethod
    def _controller(
        blueprint: FeatureBlueprint,
        spec: FeatureFileSpec,
    ) -> str:
        name = blueprint.feature_name
        phrase = blueprint.feature_slug.replace(
            "_",
            " ",
        )

        return f'''from __future__ import annotations

"""Kontroler wejścia dla funkcjonalności {name}."""

from typing import Any

from .models import (
    {name}Request,
    {name}Result,
)
from .service import {name}Service


class {name}Controller:
    """Waliduje polecenie i deleguje logikę do serwisu."""

    COMMAND_PHRASES = (
        "{phrase}",
        "{name.casefold()}",
    )

    def __init__(
        self,
        service: {name}Service | None = None,
    ) -> None:
        self.service = (
            service
            or {name}Service()
        )

    @classmethod
    def can_handle(
        cls,
        command: str,
    ) -> bool:
        normalized = " ".join(
            str(command).casefold().split()
        )
        return any(
            phrase in normalized
            for phrase in cls.COMMAND_PHRASES
        )

    def handle(
        self,
        command: str,
        payload: dict[str, Any] | None = None,
    ) -> {name}Result:
        if not self.can_handle(
            command
        ):
            return {name}Result(
                success=False,
                status="UNSUPPORTED_COMMAND",
                errors=[
                    "Polecenie nie pasuje do kontrolera.",
                ],
            )

        return self.service.execute(
            {name}Request(
                payload=dict(
                    payload or {{}}
                )
            )
        )
'''

    @staticmethod
    def _package_init(
        blueprint: FeatureBlueprint,
        spec: FeatureFileSpec,
    ) -> str:
        name = blueprint.feature_name
        has_repository = (
            "repository"
            in blueprint.file_map()
        )
        has_controller = (
            "controller"
            in blueprint.file_map()
        )

        imports = [
            (
                "from .models import (\n"
                f"    {name}Request,\n"
                f"    {name}Result,\n"
                ")\n"
            ),
            (
                f"from .service import {name}Service\n"
            ),
        ]
        exported = [
            f'"{name}Request"',
            f'"{name}Result"',
            f'"{name}Service"',
        ]

        if has_repository:
            imports.append(
                f"from .repository import {name}Repository\n"
            )
            exported.append(
                f'"{name}Repository"'
            )

        if has_controller:
            imports.append(
                f"from .controller import {name}Controller\n"
            )
            exported.append(
                f'"{name}Controller"'
            )

        export_lines = "\n".join(
            f"    {item},"
            for item in exported
        )

        return (
            "from __future__ import annotations\n\n"
            f'"""Publiczne API funkcjonalności {name}."""\n\n'
            + "".join(
                imports
            )
            + "\n__all__ = [\n"
            + export_lines
            + "\n]\n"
        )

    @staticmethod
    def _tests(
        blueprint: FeatureBlueprint,
        spec: FeatureFileSpec,
    ) -> str:
        name = blueprint.feature_name
        module = (
            PurePosixPath(
                blueprint.package_path
            )
            .as_posix()
            .replace(
                "/",
                ".",
            )
        )
        controller_available = (
            "controller"
            in blueprint.file_map()
        )
        controller_import = (
            f"    {name}Controller,\n"
            if controller_available
            else ""
        )
        controller_test = (
            f'''
    def test_controller_rejects_unknown_command(
        self,
    ) -> None:
        result = {name}Controller().handle(
            "nieznane polecenie"
        )

        self.assertFalse(
            result.success
        )
        self.assertEqual(
            result.status,
            "UNSUPPORTED_COMMAND",
        )
'''
            if controller_available
            else ""
        )

        return f'''from __future__ import annotations

import unittest

from {module} import (
{controller_import}    {name}Request,
    {name}Service,
)


class {name}FeatureTests(unittest.TestCase):

    def test_service_executes_request(
        self,
    ) -> None:
        result = {name}Service().execute(
            {name}Request(
                payload={{
                    "value": 1,
                }}
            )
        )

        self.assertTrue(
            result.success
        )
        self.assertEqual(
            result.status,
            "COMPLETED",
        )
        self.assertEqual(
            result.data["payload"]["value"],
            1,
        )
{controller_test}

if __name__ == "__main__":
    unittest.main()
'''

    @staticmethod
    def _fallback(
        blueprint: FeatureBlueprint,
        spec: FeatureFileSpec,
    ) -> str:
        class_name = "".join(
            part.capitalize()
            for part in PurePosixPath(
                spec.relative_path
            ).stem.split(
                "_"
            )
        ) or "GeneratedComponent"

        return f'''from __future__ import annotations

"""{spec.purpose}"""


class {class_name}:
    """Bezpieczny komponent funkcjonalności."""

    pass
'''
