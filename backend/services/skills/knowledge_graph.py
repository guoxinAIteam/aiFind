"""知识检索 Skill"""
from typing import Any, Dict, List

from backend.services.skills import BaseSkill, hub


def search_knowledge(query: str, articles: list) -> list:
    query_lower = query.lower()
    scored = []
    for a in articles:
        score = 0
        text = f"{a.get('title', '')} {a.get('tags', '')} {a.get('content', '')}".lower()
        for word in query_lower.split():
            if word in text:
                score += text.count(word)
        if score > 0:
            scored.append({**a, "_score": score})
    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:10]


def get_related_tips(query: str, articles: list) -> List[Dict[str, Any]]:
    hits = search_knowledge(query, articles)
    tips: List[Dict[str, Any]] = []
    for h in hits[:5]:
        title = h.get("title", "")
        cat = h.get("category", "")
        tips.append(
            {
                "title": title,
                "category": cat,
                "tip": f"参考《{title}》({cat}) 中的操作步骤与注意事项",
                "score": h.get("_score", 0),
            }
        )
    if not tips:
        tips.append(
            {
                "title": "",
                "category": "",
                "tip": "未匹配到知识条目，可尝试更换关键词或浏览故障排查分类",
                "score": 0,
            }
        )
    return tips


def list_entities() -> List[Dict[str, str]]:
    return [
        {"entity": "HBase", "type": "storage", "relation": "hosts"},
        {"entity": "Flink", "type": "compute", "relation": "consumes_from"},
        {"entity": "Kafka", "type": "messaging", "relation": "upstream_of"},
        {"entity": "HDFS", "type": "storage", "relation": "feeds"},
        {"entity": "MC", "type": "warehouse", "relation": "sink"},
    ]


class KnowledgeGraphSkill(BaseSkill):
    name = "knowledge_graph"
    version = "1.0"

    def list_actions(self) -> list[str]:
        return ["search", "get_tips", "list_entities"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "search":
            q = params.get("query", "")
            articles = params.get("articles") or []
            if not isinstance(articles, list):
                return {"error": "articles must be a list"}
            return {"results": search_knowledge(str(q), articles)}
        if action == "get_tips":
            q = params.get("query", "")
            articles = params.get("articles") or []
            if not isinstance(articles, list):
                return {"error": "articles must be a list"}
            return {"tips": get_related_tips(str(q), articles)}
        if action == "list_entities":
            return {"entities": list_entities()}
        return {"error": f"Unknown action: {action}"}


hub.register(KnowledgeGraphSkill())
