import json


class SkillManager:
    def __init__(self):
        self.skills = {}

        try:
            with open(
                "skills/custom_skills.json"
            ) as f:
                self.skills = json.load(f)

        except:
            self.skills = {}

    def add(
        self,
        trigger,
        response
    ):
        self.skills[
            trigger
        ] = response

        self.save()

    def save(self):
        with open(
            "skills/custom_skills.json",
            "w"
        ) as f:
            json.dump(
                self.skills,
                f,
                indent=4
            )

    def get(
        self,
        command
    ):
        return self.skills.get(
            command
        )