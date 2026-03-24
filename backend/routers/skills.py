"""Skill HTTP 入口：列出已注册 Skill 并按名称/动作调用 SkillHub"""
from typing import Any, Dict

from fastapi import APIRouter, Body

from backend.services.skills import hub

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("")
def list_skills():
    return hub.list_skills()


@router.post("/{skill_name}/{action}")
def invoke_skill(
    skill_name: str,
    action: str,
    params: Dict[str, Any] = Body(default_factory=dict),
):
    return hub.invoke(skill_name, action, params)
