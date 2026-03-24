"""可插拔 Skill 注册与调度"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseSkill(ABC):
    name: str
    version: str = "1.0"

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def list_actions(self) -> list[str]:
        pass


class SkillHub:
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill):
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[BaseSkill]:
        return self._skills.get(name)

    def list_skills(self) -> list[dict]:
        return [
            {"name": s.name, "version": s.version, "actions": s.list_actions()}
            for s in self._skills.values()
        ]

    def invoke(self, skill_name: str, action: str, params: dict) -> dict:
        skill = self._skills.get(skill_name)
        if not skill:
            return {"error": f"Skill '{skill_name}' not found"}
        return skill.execute(action, params)


hub = SkillHub()


def _register_all_skills() -> None:
    """在 hub 就绪后导入子模块，由各模块在加载时 register，避免与 __init__ 循环依赖。"""
    from backend.services.skills import flow_orchestration  # noqa: F401
    from backend.services.skills import param_optimization  # noqa: F401
    from backend.services.skills import anomaly_rca  # noqa: F401
    from backend.services.skills import knowledge_graph  # noqa: F401
    from backend.services.skills import predictive_maintenance  # noqa: F401


_register_all_skills()

__all__ = ["BaseSkill", "SkillHub", "hub"]
