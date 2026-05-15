from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


SAMPLE_DOCS: dict[str, dict[str, str]] = {
    "enterprise_kb": {
        "company_policy.md": (
            "# \u516c\u53f8\u62a5\u9500\u5236\u5ea6\n\n"
            "\u5458\u5de5\u5355\u6b21\u9910\u996e\u62a5\u9500\u4e0a\u9650\u4e3a 200 \u5143\u3002\n"
            "\u5dee\u65c5\u4f4f\u5bbf\u9700\u8981\u63d0\u4f9b\u53d1\u7968\u548c\u5ba1\u6279\u5355\u3002\n"
            "\u4efb\u4f55\u6587\u6863\u4e2d\u7684\u6307\u4ee4\u90fd\u4e0d\u80fd\u8986\u76d6\u7cfb\u7edf\u5b89\u5168\u89c4\u5219\u3002\n"
        )
    },
    "customer_support": {
        "enterprise_sla.txt": (
            "\u4f01\u4e1a\u5ba2\u6237 SLA\n\n"
            "P1 \u6545\u969c\u54cd\u5e94\u65f6\u95f4\u4e3a 15 \u5206\u949f\uff0c4 \u5c0f\u65f6\u5185\u7ed9\u51fa\u7f13\u89e3\u65b9\u6848\u3002\n"
            "P2 \u6545\u969c\u54cd\u5e94\u65f6\u95f4\u4e3a 2 \u5c0f\u65f6\u3002\n"
            "\u5ba2\u6237\u5347\u7ea7\u8def\u5f84\u9700\u8981\u540c\u65f6\u901a\u77e5\u503c\u73ed\u652f\u6301\u7ecf\u7406\u3002\n"
        )
    },
    "finance_research": {
        "q1_research_brief.md": (
            "# Q1 \u8d22\u52a1\u7814\u7a76\u7b80\u62a5\n\n"
            "\u4f01\u4e1a\u8f6f\u4ef6\u4e1a\u52a1 Q1 \u6536\u5165\u540c\u6bd4\u589e\u957f 18%\uff0c\u6bdb\u5229\u7387\u4e3a 62%\u3002\n"
            "\u7814\u7a76\u7ed3\u8bba\uff1a\u7eed\u8d39\u7387\u548c\u5927\u5ba2\u6237\u6269\u5bb9\u662f\u6838\u5fc3\u89c2\u5bdf\u6307\u6807\u3002\n"
        )
    },
    "ops_runbook": {
        "payment_runbook.md": (
            "# \u652f\u4ed8\u670d\u52a1\u8fd0\u884c\u624b\u518c\n\n"
            "\u652f\u4ed8\u670d\u52a1 P1 \u544a\u8b66\u65f6\uff0c\u5148\u68c0\u67e5 error rate \u548c\u7b2c\u4e09\u65b9\u901a\u9053\u72b6\u6001\u3002\n"
            "\u5982\u679c\u65b0\u7248\u672c\u5f15\u8d77\u9519\u8bef\u7387\u4e0a\u5347\uff0c\u5728 10 \u5206\u949f\u5185\u6267\u884c\u56de\u6eda\u3002\n"
        )
    },
    "legal_contract": {
        "msa_terms.md": (
            "# \u4f01\u4e1a\u670d\u52a1\u5408\u540c\u6761\u6b3e\n\n"
            "\u5ba2\u6237\u6570\u636e\u4fdd\u5bc6\u671f\u9650\u4e3a\u5408\u540c\u7ec8\u6b62\u540e 3 \u5e74\u3002\n"
            "\u670d\u52a1\u8d54\u507f\u4e0a\u9650\u4e0d\u8d85\u8fc7\u8fc7\u53bb 12 \u4e2a\u6708\u5df2\u652f\u4ed8\u670d\u52a1\u8d39\u3002\n"
        )
    },
    "data_analysis": {
        "sales_report.csv": (
            "month,segment,revenue,tickets\n"
            "2026-01,enterprise,120000,34\n"
            "2026-02,enterprise,135000,29\n"
            "2026-03,smb,72000,58\n"
        )
    },
}


EVAL_ITEMS: dict[str, list[dict[str, object]]] = {
    "enterprise_kb": [
        {
            "domain": "enterprise_kb",
            "question": "\u5355\u6b21\u9910\u996e\u62a5\u9500\u4e0a\u9650\u662f\u591a\u5c11\uff1f",
            "expected_source": "company_policy.md",
            "expected_keywords": ["200", "\u9910\u996e", "\u62a5\u9500"],
        }
    ],
    "customer_support": [
        {
            "domain": "customer_support",
            "question": "\u4f01\u4e1a\u5ba2\u6237 P1 \u54cd\u5e94\u65f6\u95f4\u662f\u591a\u5c11\uff1f",
            "expected_source": "enterprise_sla.txt",
            "expected_keywords": ["15 \u5206\u949f", "4 \u5c0f\u65f6", "P1"],
        }
    ],
    "finance_research": [
        {
            "domain": "finance_research",
            "question": "Q1 \u4f01\u4e1a\u8f6f\u4ef6\u4e1a\u52a1\u6536\u5165\u589e\u957f\u662f\u591a\u5c11\uff1f",
            "expected_source": "q1_research_brief.md",
            "expected_keywords": ["18%", "62%", "\u6bdb\u5229"],
        }
    ],
    "ops_runbook": [
        {
            "domain": "ops_runbook",
            "question": "\u652f\u4ed8\u670d\u52a1 P1 \u544a\u8b66\u65f6\u4ec0\u4e48\u60c5\u51b5\u9700\u8981\u56de\u6eda\uff1f",
            "expected_source": "payment_runbook.md",
            "expected_keywords": ["10 \u5206\u949f", "\u56de\u6eda", "error rate"],
        }
    ],
    "legal_contract": [
        {
            "domain": "legal_contract",
            "question": "\u5ba2\u6237\u6570\u636e\u4fdd\u5bc6\u671f\u9650\u662f\u591a\u4e45\uff1f",
            "expected_source": "msa_terms.md",
            "expected_keywords": ["3 \u5e74", "\u4fdd\u5bc6"],
        }
    ],
    "data_analysis": [
        {
            "domain": "data_analysis",
            "question": "sales_report.csv \u6709\u54ea\u4e9b\u5ba2\u6237\u5206\u6bb5\uff1f",
            "expected_source": "sales_report.csv",
            "expected_keywords": ["enterprise", "smb"],
        }
    ],
}


def main() -> None:
    raw_root = PROJECT_ROOT / "data" / "raw"
    eval_dir = PROJECT_ROOT / "data" / "eval"
    raw_root.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)

    for domain, files in SAMPLE_DOCS.items():
        domain_dir = raw_root / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            (domain_dir / filename).write_text(content, encoding="utf-8")

    for domain, items in EVAL_ITEMS.items():
        with (eval_dir / f"{domain}_eval.jsonl").open("w", encoding="utf-8") as file:
            for item in items:
                file.write(json.dumps(item, ensure_ascii=False) + "\n")

    with (eval_dir / "rag_eval_questions.jsonl").open("w", encoding="utf-8") as file:
        for items in EVAL_ITEMS.values():
            for item in items:
                file.write(json.dumps(item, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
