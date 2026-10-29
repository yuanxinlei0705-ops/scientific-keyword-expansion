"""Report serialization without changing the evidence model."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


def json_text(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def _sentence(value: str) -> str:
    value = value.strip()
    return value if not value or value[-1] in ".。!?！？" else value + "."


def markdown_text(report: dict[str, Any]) -> str:
    zh = report["language"] == "chinese"
    lines = ["# 科研关键词扩展报告" if zh else "# Scientific Keyword Expansion Report", "",
             f"**{'研究主题' if zh else 'Research topic'}:** {report['topic']}",
             f"**{'研究重点' if zh else 'Focus'}:** {', '.join(report['focus']) or ('无' if zh else 'None')}",
             f"**{'模式' if zh else 'Mode'}:** {report['mode']} · **{'关键词' if zh else 'Keywords'}:** {report['generated_count']}/{report['requested_count']}", "",
             "## 科研检索摘要" if zh else "## Research Search Brief", ""]
    brief = report.get("research_search_brief") or {}
    lines.append(f"**{'研究问题' if zh else 'Research problem'}:** {brief.get('research_problem') or report['topic']}")
    lines.append(f"**{'优先关键词' if zh else 'Priority keywords'}:** {', '.join(brief.get('priority_keywords', [])) or '—'}")
    lines.append(f"**{'主要方向' if zh else 'Main directions'}:** {', '.join(brief.get('main_directions', [])) or '—'}")
    lines.append(f"**{'待验证术语' if zh else 'Terms to verify'}:** {', '.join(brief.get('terms_needing_verification', [])) or '—'}")
    lines.append(f"**{'跨领域机会' if zh else 'Transfer opportunities'}:** {', '.join(brief.get('transfer_opportunities', [])) or '—'}")
    lines.append("**优先检索式：**" if zh else "**Priority queries:**")
    for expression in brief.get("priority_queries", [])[:5]:
        lines.append(f"- `{expression.replace('`', '')}`")
    lines += ["", "## 研究领域分析" if zh else "## Research domain analysis", ""]
    analysis = report.get("domain_analysis") or {}
    if analysis:
        for key, value in analysis.items():
            rendered = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
            zh_keys = {"discipline": "学科", "research_problem": "研究问题", "research_objects": "研究对象",
                       "theories": "理论", "methods": "方法", "experiments": "实验", "adjacent_disciplines": "交叉学科"}
            label = zh_keys.get(key, key) if zh else key.replace("_", " ").title()
            lines.append(f"- **{label}:** {rendered}")
    else:
        lines.append("未提供 Agent 领域分析。" if zh else "No agent analysis supplied.")
    lines += ["", "## 检索概念拆解" if zh else "## Search concept decomposition", ""]
    for group in report.get("search_concepts", []):
        lines.append(f"- **{group['role']}**: {' OR '.join(group['terms'])}")
    if not report.get("search_concepts"):
        lines.append("未提供可用检索概念。" if zh else "No usable search concepts were supplied.")
    lines += ["", "## 关键词分类" if zh else "## Keyword taxonomy", ""]
    categories = list(dict.fromkeys(item["category"] for item in report["keywords"]))
    lines += [f"- {category}" for category in categories] or ["未提供分类。" if zh else "No categories supplied."]
    lines += ["", "## 核心关键词" if zh else "## Core keywords", ""]
    english_only = report["language"] == "english"
    chinese_first = report["language"] == "chinese"
    headers = ["ID", "Category", "Chinese", "Keyword"] if chinese_first else ["ID", "Category", "Keyword"]
    if not english_only and not chinese_first:
        headers.append("Chinese")
    headers += ["Abbreviation", "Synonyms", "Type", "Layer", "Level", "Relevance", "Verification"]
    if zh:
        translated = {"ID": "编号", "Category": "类别", "Chinese": "中文", "Keyword": "英文关键词",
                      "Abbreviation": "缩写", "Synonyms": "同义词", "Type": "术语类型", "Scope": "范围",
                      "Relevance": "相关性", "Priority": "优先级", "Verification": "验证状态", "Reason": "研究关联",
                      "Layer": "层次", "Level": "相关等级", "Score reason": "评分依据"}
        headers = [translated[header] for header in headers]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---:" if header in {"ID", "Relevance", "编号", "相关性"} else "---" for header in headers) + " |")
    for item in report["keywords"]:
        cells = [str(item["id"]), item["category"]]
        if chinese_first:
            cells.append(item["chinese"])
        cells.append(item["keyword"])
        if not english_only and not chinese_first:
            cells.append(item["chinese"])
        cells += [item["abbreviation"], ", ".join(item["synonyms"]), item["term_type"],
                  item.get("layer", ""), item.get("relevance_level", ""),
                  str(item["relevance_score"]), item["verification_status"]]
        lines.append("| " + " | ".join(cell.replace("|", "\\|").replace("\n", " ") for cell in cells) + " |")
    lines += ["", "## 研究关联与评分依据" if zh else "## Research relevance and score rationale", ""]
    for item in report["keywords"]:
        lines.append(f"- **{item['id']}. {item['keyword']}** — {item['reason']} "
                     + ("评分依据：" if zh else "Score rationale: ") + item.get("score_reason", ""))
    lines += ["", "分数为 Agent 加权估计，不代表文献数量。" if zh else
              "Scores are weighted agent estimates; no literature count is inferred from them.", "",
              "## 推荐检索式" if zh else "## Recommended search queries", ""]
    for index, query in enumerate(report["search_queries"], 1):
        kind_zh = {"overview": "领域概览", "review": "综述", "core_problem": "核心问题",
                   "method": "技术方法", "application": "特定应用", "cross_domain": "跨领域方法", "focused": "研究重点"}
        label = f"{kind_zh[query['kind']]} — {', '.join(query['concepts'])}" if zh else f"{query['kind']} — {query['objective']}"
        context = f"主要概念：{', '.join(query['concepts'])}。平台：通用布尔检索。" if zh else \
                  f"Concepts: {', '.join(query['concepts'])}. Platform: Generic Boolean."
        evaluation = query.get("live_evaluation")
        state = (evaluation["status"] if evaluation else "not executed")
        purpose = (("优先级" if zh else "Priority") + f" {query.get('priority', '—')}; "
                   + ("预期文献" if zh else "Expected papers") + f": {query.get('expected_papers', '—')}; "
                   + ("真实检索" if zh else "Live retrieval") + f": {state}.")
        lines += [f"### {index}. {label}", "", context, "", purpose, "",
                  "```text", query["expression"], "```", ""]
        acronyms = query.get("static_validation", {}).get("ambiguous_acronyms", [])
        if acronyms:
            lines.append(("- 缩写歧义待核查：" if zh else "- Review acronym ambiguity: ") + ", ".join(acronyms))
        if evaluation:
            last = evaluation["query_history"][-1]
            lines.append(f"- OpenAlex `search={last['executed_params']['search']}`; "
                         f"retrieval count: {last['retrieval_count'] if last['retrieval_count'] is not None else 'unknown'}; "
                         f"sample: {last['sample_size']}; revisions: {evaluation['revision_count']}. "
                         "Plain-text approximation; precision not estimated.")
            if evaluation.get("review_warning"):
                lines.append(f"- {evaluation['review_warning']}")
            if evaluation["status"] == "failed":
                lines.append(f"- Live query error: {last['error']}")
            if evaluation["revision_count"]:
                first = evaluation["query_history"][0]
                lines.append(f"- Revision reason: {last.get('revision_reason', 'review trigger')}; "
                             f"before count/lexical coverage: {first['retrieval_count']}/{first['query_coverage']}; "
                             f"after: {last['retrieval_count']}/{last['query_coverage']}.")
    if not report["search_queries"]:
        lines += ["检索式生成已关闭，或没有可用关键词。" if zh else "Search query generation was disabled or no keywords were available.", ""]
    lines += ["## 关键词关系" if zh else "## Keyword relationships", ""]
    for edge in report.get("relationships", [])[:15]:
        lines.append(f"- **{edge['source']}** → **{edge['target']}** ({edge['relation']}; {edge.get('semantic_status', 'unreviewed')}): {_sentence(edge.get('explanation') or ('待 Agent 解释' if zh else 'Agent explanation pending'))} "
                     + ("关系未经文献验证。" if zh else "Relationship unverified."))
    if not report.get("relationships"):
        lines.append("未提供关系。" if zh else "No relationships supplied.")
    if len(report.get("relationships", [])) > 15:
        lines.append("其余关系保存在 JSON 中。" if zh else "Remaining relationships are retained in JSON.")
    lines += [""]
    lines += ["## 跨领域机会" if zh else "## Cross-domain opportunities", ""]
    transfers = [item for item in report["keywords"] if item["scope"] == "transfer"]
    lines += [f"- **{item['keyword']}**: {item['reason']} ({'潜在迁移，目标应用未验证' if zh else 'potential transfer; application unverified'})" for item in transfers] or ["无。" if zh else "None supplied."]
    lines += ["", "## 验证说明" if zh else "## Verification notes", ""]
    if report["mode"] == "quick":
        lines.append("快速模式未查询学术数据库；全部术语和关系均未经文献验证。" if zh else
                     "Quick mode did not query academic databases. All terms and relationships remain unverified.")
    else:
        lines.append("证据是抽样元数据。精确短语表示术语出现在返回的标题或摘要中；仅检索命中的记录只算相关主题证据，不代表全库统计。" if zh else
                     "Evidence entries are sampled metadata records. Exact phrase means a phrase was found in returned title or abstract; search result hits alone are related-topic evidence. No corpus-wide counts are claimed.")
        for item in report["keywords"]:
            if item["evidence"]:
                lines.append(f"- **{item['keyword']}**: {len(item['evidence'])} {'条不重复抽样记录' if zh else 'sampled distinct records'}; {item['verification_status']}.")
                for paper in item["evidence"][:2]:
                    doi = paper.get("doi") or ""
                    doi_url = doi if doi.startswith("http") else ("https://doi.org/" + doi if doi else "")
                    safe_url = doi_url or paper.get("url", "")
                    link = f"[{'DOI' if doi else 'paper'}]({safe_url})" if safe_url.startswith("https://") else "link unavailable"
                    lines.append(f"  - {paper['title']} ({paper.get('publication_year') or 'year unknown'}), {', '.join(paper.get('sources', [paper['source']]))}, {paper['match_type']}; {link}; retrieved {paper['retrieved_at']}")
    revision = report.get("revision")
    if revision:
        lines += ["", "## 修订记录" if zh else "## Revision record", "",
                  f"- Added: {', '.join(revision['added_keywords']) or '—'}",
                  f"- Removed: {', '.join(revision['removed_keywords']) or '—'}",
                  f"- Retained: {', '.join(revision['retained_keywords']) or '—'}",
                  f"- Reason: {revision['revision_reason'] or 'not supplied'}"]
    quality = report.get("quality_checks", {})
    lines += ["", "## 质量检查" if zh else "## Quality checks", ""]
    lines.append(("通过" if quality.get("passed") else "需要 Agent 复核") if zh else
                 ("Passed" if quality.get("passed") else "Needs Agent revision"))
    for issue in quality.get("issues", []):
        lines.append(f"- {issue['severity']}: {issue['message']}")
    for warning in report["warnings"]:
        lines.append(f"- {'警告' if zh else 'Warning'}: {warning}")
    return "\n".join(lines) + "\n"


def csv_text(report: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    columns = ["id", "category", "keyword", "chinese", "abbreviation", "synonyms", "term_type",
               "layer", "scope", "term_class", "topic_relevance", "search_utility", "exploration_value",
               "assessment_basis", "relevance_level", "relevance_score", "score_basis", "score_reason",
               "reason", "priority", "verification_status", "research_status"]
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for item in report["keywords"]:
        writer.writerow({**item, "synonyms": "; ".join(item["synonyms"])})
    return "\ufeff" + output.getvalue()


def write_outputs(report: dict[str, Any], directory: str | Path, formats: tuple[str, ...] = ("markdown", "json", "csv")) -> list[Path]:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for name, filename, content in [
        ("markdown", "report.md", markdown_text(report)),
        ("json", "report.json", json_text(report)),
        ("csv", "keywords.csv", csv_text(report)),
    ]:
        if name in formats:
            target = path / filename
            target.write_text(content, encoding="utf-8", newline="")
            generated.append(target)
    return generated
