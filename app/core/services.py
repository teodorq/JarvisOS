class ServiceContainer:

    def __init__(self):
        self._services = {}

    def get(self, name, factory):
        if name not in self._services:
            self._services[name] = factory()

        return self._services[name]

    def clear(self):
        self._services.clear()


services = ServiceContainer()