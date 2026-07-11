from app.ai.brain import Brain
from app.ai.cognitive_engine import CognitiveEngine
from app.ai.system_state import SystemState


class JarvisCore:

    def __init__(self):
        self.brain = Brain()
        self.cognitive = CognitiveEngine()
        self.system_state = SystemState()

    def process(self, command: str):
        thought = self.brain.think(command)

        if not thought.get("can_execute"):
            return {
                "thought": thought,
                "response": "Nie potrafię jeszcze wykonać tej akcji."
            }

        response = self.brain.execute(thought)

        self.cognitive.remember_interaction(
            command,
            response
        )

        return {
            "thought": thought,
            "response": response
        }

    def status(self):
        return {
            "system": self.system_state.as_dict(),
            "cognitive": self.cognitive.summary()
        }