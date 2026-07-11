from app.autodev.autodev_task_seeder import AutoDevTaskSeeder


class AutoDevCycle:

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.seeder = AutoDevTaskSeeder(pipeline)

    def run(self):

        result = self.seeder.seed()

        return {
            "success": result["success"],
            "tasks_created": result["created_count"],
            "errors": result["errors"],
        }