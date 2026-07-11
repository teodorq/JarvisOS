class SystemState:

    def __init__(self):
        self.brain_online = True
        self.vision_online = True
        self.memory_online = True
        self.voice_online = False
        self.agent_online = True

    def as_dict(self):
        return {
            "brain": self.brain_online,
            "vision": self.vision_online,
            "memory": self.memory_online,
            "voice": self.voice_online,
            "agent": self.agent_online
        }

    def summary(self):
        return (
            "SystemState:\n"
            f"Brain: {self.brain_online}\n"
            f"Vision: {self.vision_online}\n"
            f"Memory: {self.memory_online}\n"
            f"Voice: {self.voice_online}\n"
            f"Agent: {self.agent_online}"
        )