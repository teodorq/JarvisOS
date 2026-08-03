from __future__ import annotations

from collections import defaultdict, deque

from .feature_models import FeatureFileSpec


class FeatureDependencyPlanner:

    def validate(
        self,
        files: list[FeatureFileSpec],
    ) -> None:
        file_ids = {
            item.file_id
            for item in files
        }
        paths: set[str] = set()

        for item in files:
            if item.file_id in item.dependencies:
                raise ValueError(
                    "Plik nie może zależeć sam od siebie: "
                    f"{item.file_id}"
                )

            unknown = [
                dependency
                for dependency in item.dependencies
                if dependency not in file_ids
            ]

            if unknown:
                raise ValueError(
                    "Nieznane zależności dla "
                    f"{item.file_id}: {unknown}"
                )

            normalized_path = (
                item.relative_path
                .replace("\\", "/")
                .casefold()
            )

            if normalized_path in paths:
                raise ValueError(
                    "Duplikat ścieżki pliku: "
                    f"{item.relative_path}"
                )

            paths.add(
                normalized_path
            )

        self.creation_order(
            files
        )

    def creation_order(
        self,
        files: list[FeatureFileSpec],
    ) -> list[str]:
        graph: dict[str, list[str]] = defaultdict(list)
        indegree = {
            item.file_id: 0
            for item in files
        }

        for item in files:
            for dependency in item.dependencies:
                graph[dependency].append(
                    item.file_id
                )
                indegree[item.file_id] += 1

        ready = deque(
            sorted(
                file_id
                for file_id, degree
                in indegree.items()
                if degree == 0
            )
        )
        result: list[str] = []

        while ready:
            file_id = ready.popleft()
            result.append(
                file_id
            )

            for child in sorted(
                graph.get(
                    file_id,
                    [],
                )
            ):
                indegree[child] -= 1

                if indegree[child] == 0:
                    ready.append(
                        child
                    )

        if len(result) != len(files):
            raise ValueError(
                "Wykryto cykliczne zależności "
                "w planie funkcjonalności."
            )

        return result
