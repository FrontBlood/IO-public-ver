# services/achievement_model.py

class Achievement:
    def __init__(self, id, name, description, condition, progress, rewards=None, requires=None):
        self.id = id
        self.name = name
        self.description = description
        self.condition = condition
        self.progress = progress
        self.rewards = rewards or {}
        self.requires = requires

    def is_unlocked(self, user, context_data=None):
        return self.condition(user, context_data)

    def get_progress(self, user, context_data=None):
        return self.progress(user, context_data)
